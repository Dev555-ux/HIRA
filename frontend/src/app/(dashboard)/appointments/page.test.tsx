import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/toast";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { Appointment, Customer } from "@/lib/types";
import AppointmentsPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    listAppointments: vi.fn(),
    createAppointment: vi.fn(),
    rescheduleAppointment: vi.fn(),
    cancelAppointment: vi.fn(),
    listCustomers: vi.fn(),
  },
}));

import { api } from "@/lib/api";

const mockAuth: AuthContextValue = {
  getToken: async () => "test-token",
  user: null,
  isLoaded: true,
  mocked: true,
  signOut: vi.fn(),
  openProfile: vi.fn(),
};

function appointment(overrides: Partial<Appointment> = {}): Appointment {
  return {
    id: "appt-1",
    customer: { id: "cust-1", display_name: "Alex Rivera", wa_phone: "+15551230000" },
    conversation_id: null,
    starts_at: "2026-08-05T14:00:00Z",
    ends_at: "2026-08-05T15:00:00Z",
    status: "booked",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

function customer(overrides: Partial<Customer> = {}): Customer {
  return {
    id: "cust-2",
    display_name: "Sam Patel",
    company: null,
    wa_phone: "+15559998888",
    email: null,
    notes: null,
    created_at: new Date().toISOString(),
    conversation_count: 1,
    last_message_at: null,
    lead: null,
    ...overrides,
  };
}

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={mockAuth}>
        <ToastProvider>{ui}</ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("AppointmentsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 5, offset: 0 },
    });
  });

  it("shows the empty state when there are no appointments", async () => {
    vi.mocked(api.listAppointments).mockResolvedValue([]);
    renderWithProviders(<AppointmentsPage />);
    expect(await screen.findByText("No upcoming appointments")).toBeInTheDocument();
  });

  it("shows an error state with retry when the list fails to load", async () => {
    vi.mocked(api.listAppointments).mockRejectedValue(new Error("Network error"));
    renderWithProviders(<AppointmentsPage />);

    expect(await screen.findByText("Couldn't load appointments")).toBeInTheDocument();
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });

  it("renders an appointment with customer, time range, and status badge", async () => {
    vi.mocked(api.listAppointments).mockResolvedValue([appointment()]);
    renderWithProviders(<AppointmentsPage />);

    expect(await screen.findByText("Alex Rivera")).toBeInTheDocument();
    expect(screen.getByText("Booked")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reschedule/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^cancel$/i })).toBeInTheDocument();
  });

  it("hides reschedule/cancel actions for a cancelled appointment", async () => {
    vi.mocked(api.listAppointments).mockResolvedValue([appointment({ status: "cancelled" })]);
    renderWithProviders(<AppointmentsPage />);

    await screen.findByText("Alex Rivera");
    expect(screen.queryByRole("button", { name: /reschedule/i })).not.toBeInTheDocument();
  });

  it("cancels an appointment after confirming", async () => {
    vi.mocked(api.listAppointments).mockResolvedValue([appointment()]);
    vi.mocked(api.cancelAppointment).mockResolvedValue(appointment({ status: "cancelled" }));
    const user = userEvent.setup();
    renderWithProviders(<AppointmentsPage />);

    await user.click(await screen.findByRole("button", { name: /^cancel$/i }));
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /cancel appointment/i }));

    await waitFor(() =>
      expect(api.cancelAppointment).toHaveBeenCalledWith(expect.any(Function), "appt-1"),
    );
    expect(await screen.findByText("Appointment cancelled")).toBeInTheDocument();
  });

  it("reschedules an appointment via the dialog", async () => {
    vi.mocked(api.listAppointments).mockResolvedValue([appointment()]);
    vi.mocked(api.rescheduleAppointment).mockResolvedValue(
      appointment({ status: "rescheduled" }),
    );
    const user = userEvent.setup();
    renderWithProviders(<AppointmentsPage />);

    await user.click(await screen.findByRole("button", { name: /reschedule/i }));
    expect(await screen.findByText("Reschedule appointment")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^reschedule$/i }));

    await waitFor(() =>
      expect(api.rescheduleAppointment).toHaveBeenCalledWith(
        expect.any(Function),
        "appt-1",
        expect.objectContaining({
          starts_at: "2026-08-05T14:00:00.000Z",
          ends_at: "2026-08-05T15:00:00.000Z",
        }),
      ),
    );
    expect(await screen.findByText("Appointment rescheduled")).toBeInTheDocument();
  });

  it("rejects rescheduling to an end time before the start time", async () => {
    vi.mocked(api.listAppointments).mockResolvedValue([appointment()]);
    const user = userEvent.setup();
    renderWithProviders(<AppointmentsPage />);

    await user.click(await screen.findByRole("button", { name: /reschedule/i }));
    const dialog = await screen.findByText("Reschedule appointment");
    const form = dialog.closest("[role=dialog]") as HTMLElement;
    const [startInput, endInput] = form.querySelectorAll("input[type=datetime-local]");
    await user.clear(endInput as HTMLElement);
    await user.type(endInput as HTMLElement, "2026-08-05T13:00");
    await user.clear(startInput as HTMLElement);
    await user.type(startInput as HTMLElement, "2026-08-05T14:00");

    await user.click(within(form).getByRole("button", { name: /^reschedule$/i }));

    expect(await screen.findByText("End time must be after start time")).toBeInTheDocument();
    expect(api.rescheduleAppointment).not.toHaveBeenCalled();
  });

  it("opens the new-appointment dialog and searches for a customer", async () => {
    vi.mocked(api.listAppointments).mockResolvedValue([]);
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [customer()],
      meta: { total: 1, limit: 5, offset: 0 },
    });
    const user = userEvent.setup();
    renderWithProviders(<AppointmentsPage />);

    await screen.findByText("No upcoming appointments");
    await user.click(screen.getAllByRole("button", { name: /new appointment/i })[0]);
    await user.type(screen.getByPlaceholderText(/search customers/i), "Sam");

    expect(await screen.findByText("Sam Patel")).toBeInTheDocument();
  });

  it("creates an appointment once a customer is selected and the form is filled", async () => {
    vi.mocked(api.listAppointments).mockResolvedValue([]);
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [customer()],
      meta: { total: 1, limit: 5, offset: 0 },
    });
    vi.mocked(api.createAppointment).mockResolvedValue(appointment({ id: "appt-new" }));
    const user = userEvent.setup();
    renderWithProviders(<AppointmentsPage />);

    await screen.findByText("No upcoming appointments");
    await user.click(screen.getAllByRole("button", { name: /new appointment/i })[0]);
    await user.type(screen.getByPlaceholderText(/search customers/i), "Sam");
    await user.click(await screen.findByText("Sam Patel"));
    await user.type(screen.getByPlaceholderText(/dental cleaning/i), "Consultation");

    const dialog = screen.getByRole("dialog");
    const timeInputs = dialog.querySelectorAll("input[type=datetime-local]");
    await user.type(timeInputs[0] as HTMLInputElement, "2026-08-05T14:00");
    await user.type(timeInputs[1] as HTMLInputElement, "2026-08-05T15:00");

    await user.click(within(dialog).getByRole("button", { name: /book appointment/i }));

    await waitFor(() =>
      expect(api.createAppointment).toHaveBeenCalledWith(
        expect.any(Function),
        expect.objectContaining({ customer_id: "cust-2", summary: "Consultation" }),
      ),
    );
    expect(await screen.findByText("Appointment booked")).toBeInTheDocument();
  });

  it("rejects booking a new appointment with an end time before the start time", async () => {
    vi.mocked(api.listAppointments).mockResolvedValue([]);
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [customer()],
      meta: { total: 1, limit: 5, offset: 0 },
    });
    const user = userEvent.setup();
    renderWithProviders(<AppointmentsPage />);

    await screen.findByText("No upcoming appointments");
    await user.click(screen.getAllByRole("button", { name: /new appointment/i })[0]);
    await user.type(screen.getByPlaceholderText(/search customers/i), "Sam");
    await user.click(await screen.findByText("Sam Patel"));
    await user.type(screen.getByPlaceholderText(/dental cleaning/i), "Consultation");

    const dialog = screen.getByRole("dialog");
    const timeInputs = dialog.querySelectorAll("input[type=datetime-local]");
    await user.type(timeInputs[0] as HTMLInputElement, "2026-08-05T15:00");
    await user.type(timeInputs[1] as HTMLInputElement, "2026-08-05T14:00");

    await user.click(within(dialog).getByRole("button", { name: /book appointment/i }));

    expect(await screen.findByText("End time must be after start time")).toBeInTheDocument();
    expect(api.createAppointment).not.toHaveBeenCalled();
  });
});
