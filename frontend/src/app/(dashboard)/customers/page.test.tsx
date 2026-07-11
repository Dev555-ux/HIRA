import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/toast";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { Customer, CustomerDetail, TimelineItem } from "@/lib/types";
import CustomersPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    listCustomers: vi.fn(),
    getCustomer: vi.fn(),
    getCustomerTimeline: vi.fn(),
    createCustomer: vi.fn(),
    updateCustomer: vi.fn(),
    deleteCustomer: vi.fn(),
    createLead: vi.fn(),
    updateLead: vi.fn(),
    deleteLead: vi.fn(),
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

function customer(overrides: Partial<Customer> = {}): Customer {
  return {
    id: "cust-1",
    display_name: "Alice Smith",
    wa_phone: "+15551230000",
    email: null,
    notes: null,
    created_at: new Date().toISOString(),
    conversation_count: 2,
    last_message_at: new Date().toISOString(),
    lead: null,
    ...overrides,
  };
}

function customerDetail(overrides: Partial<CustomerDetail> = {}): CustomerDetail {
  return {
    id: "cust-1",
    display_name: "Alice Smith",
    wa_phone: "+15551230000",
    email: null,
    notes: null,
    created_at: new Date().toISOString(),
    conversation_count: 2,
    last_message_at: new Date().toISOString(),
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

describe("CustomersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getCustomerTimeline).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
  });

  it("shows the empty state when there are no customers", async () => {
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
    renderWithProviders(<CustomersPage />);
    expect(await screen.findByText("No customers yet")).toBeInTheDocument();
  });

  it("shows an error state with retry when the list fails to load", async () => {
    vi.mocked(api.listCustomers).mockRejectedValue(new Error("Network error"));
    renderWithProviders(<CustomersPage />);

    expect(await screen.findByText("Couldn't load customers")).toBeInTheDocument();
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });

  it("renders a customer row with conversation count and lead stage badge", async () => {
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [customer({ lead: { id: "lead-1", stage: "qualified" } })],
      meta: { total: 1, limit: 20, offset: 0 },
    });

    renderWithProviders(<CustomersPage />);

    expect(await screen.findByText("Alice Smith")).toBeInTheDocument();
    expect(screen.getByText("2 conversations")).toBeInTheDocument();
    expect(screen.getByText("Qualified")).toBeInTheDocument();
  });

  it("debounces search input, then calls the API with the search term", async () => {
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
    const user = userEvent.setup();
    renderWithProviders(<CustomersPage />);
    await screen.findByText("No customers yet");

    await user.type(screen.getByPlaceholderText(/search customers/i), "alice");

    await waitFor(
      () =>
        expect(api.listCustomers).toHaveBeenCalledWith(
          expect.any(Function),
          expect.objectContaining({ search: "alice" }),
        ),
      { timeout: 1000 },
    );
  });

  it("paginates using the Previous/Next controls", async () => {
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [customer()],
      meta: { total: 45, limit: 20, offset: 0 },
    });
    const user = userEvent.setup();
    renderWithProviders(<CustomersPage />);
    await screen.findByText("Alice Smith");

    expect(screen.getByText("1–20 of 45")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() =>
      expect(api.listCustomers).toHaveBeenCalledWith(
        expect.any(Function),
        expect.objectContaining({ offset: 20 }),
      ),
    );
  });

  it("shows a prompt to select a customer before one is chosen", async () => {
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [customer()],
      meta: { total: 1, limit: 20, offset: 0 },
    });
    renderWithProviders(<CustomersPage />);
    await screen.findByText("Alice Smith");

    expect(
      screen.getByText("Select a customer to view their profile, pipeline, and timeline."),
    ).toBeInTheDocument();
  });

  it("loads the customer detail, lead card, and timeline when selected", async () => {
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [customer()],
      meta: { total: 1, limit: 20, offset: 0 },
    });
    vi.mocked(api.getCustomer).mockResolvedValue(customerDetail());
    const timelineItems: TimelineItem[] = [
      {
        type: "message",
        id: "m1",
        created_at: new Date().toISOString(),
        direction: "inbound",
        body: "Are you open today?",
        status: "received",
      },
    ];
    vi.mocked(api.getCustomerTimeline).mockResolvedValue({
      data: timelineItems,
      meta: { total: 1, limit: 20, offset: 0 },
    });
    const user = userEvent.setup();

    renderWithProviders(<CustomersPage />);
    await user.click(await screen.findByText("Alice Smith"));

    expect(await screen.findByText("+15551230000 · 2 conversations")).toBeInTheDocument();
    expect(screen.getByText("No lead yet")).toBeInTheDocument();
    expect(screen.getByText("Are you open today?")).toBeInTheDocument();
    expect(api.getCustomer).toHaveBeenCalledWith(expect.any(Function), "cust-1");
  });

  it("creates a lead from the customer detail pane", async () => {
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [customer()],
      meta: { total: 1, limit: 20, offset: 0 },
    });
    vi.mocked(api.getCustomer).mockResolvedValue(customerDetail());
    vi.mocked(api.createLead).mockResolvedValue({
      id: "lead-1",
      customer: { id: "cust-1", display_name: "Alice Smith", wa_phone: "+15551230000" },
      stage: "new",
      source: null,
      estimated_value: null,
      notes: null,
      next_follow_up_at: null,
      assigned_to: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    const user = userEvent.setup();

    renderWithProviders(<CustomersPage />);
    await user.click(await screen.findByText("Alice Smith"));
    await user.click(await screen.findByRole("button", { name: /create lead/i }));
    await user.click(screen.getByRole("button", { name: /^create lead$/i }));

    await waitFor(() =>
      expect(api.createLead).toHaveBeenCalledWith(
        expect.any(Function),
        expect.objectContaining({ customer_id: "cust-1", stage: "new" }),
      ),
    );
    expect(await screen.findByText("Lead created")).toBeInTheDocument();
  });

  it("edits an existing lead's stage", async () => {
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [customer({ lead: { id: "lead-1", stage: "new" } })],
      meta: { total: 1, limit: 20, offset: 0 },
    });
    vi.mocked(api.getCustomer).mockResolvedValue(
      customerDetail({
        lead: {
          id: "lead-1",
          stage: "new",
          source: null,
          estimated_value: null,
          notes: null,
          next_follow_up_at: null,
          assigned_to: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      }),
    );
    vi.mocked(api.updateLead).mockResolvedValue({
      id: "lead-1",
      customer: { id: "cust-1", display_name: "Alice Smith", wa_phone: "+15551230000" },
      stage: "contacted",
      source: null,
      estimated_value: null,
      notes: null,
      next_follow_up_at: null,
      assigned_to: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    const user = userEvent.setup();

    renderWithProviders(<CustomersPage />);
    await user.click(await screen.findByText("Alice Smith"));
    await screen.findByRole("button", { name: /save changes/i });

    await user.selectOptions(screen.getByLabelText("Stage"), "contacted");
    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() =>
      expect(api.updateLead).toHaveBeenCalledWith(
        expect.any(Function),
        "lead-1",
        expect.objectContaining({ stage: "contacted" }),
      ),
    );
    expect(await screen.findByText("Lead updated")).toBeInTheDocument();
  });

  it("deletes a lead after confirming", async () => {
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [customer({ lead: { id: "lead-1", stage: "new" } })],
      meta: { total: 1, limit: 20, offset: 0 },
    });
    vi.mocked(api.getCustomer).mockResolvedValue(
      customerDetail({
        lead: {
          id: "lead-1",
          stage: "new",
          source: null,
          estimated_value: null,
          notes: null,
          next_follow_up_at: null,
          assigned_to: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      }),
    );
    vi.mocked(api.deleteLead).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithProviders(<CustomersPage />);
    await user.click(await screen.findByText("Alice Smith"));
    await user.click(await screen.findByRole("button", { name: /delete lead/i }));

    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /delete/i }));

    await waitFor(() =>
      expect(api.deleteLead).toHaveBeenCalledWith(expect.any(Function), "lead-1"),
    );
  });

  it("returns to the customer list from the back button", async () => {
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [customer()],
      meta: { total: 1, limit: 20, offset: 0 },
    });
    vi.mocked(api.getCustomer).mockResolvedValue(customerDetail());
    const user = userEvent.setup();

    renderWithProviders(<CustomersPage />);
    await user.click(await screen.findByText("Alice Smith"));
    await screen.findByRole("button", { name: /back to customers/i });

    await user.click(screen.getByRole("button", { name: /back to customers/i }));

    expect(
      await screen.findByText("Select a customer to view their profile, pipeline, and timeline."),
    ).toBeInTheDocument();
  });

  it("creates a customer via the Add Customer dialog", async () => {
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
    vi.mocked(api.createCustomer).mockResolvedValue(customerDetail({ id: "cust-new" }));
    const user = userEvent.setup();

    renderWithProviders(<CustomersPage />);
    await screen.findByText("No customers yet");

    // Two "Add Customer" buttons exist in the empty state (header action +
    // empty-state CTA) — the header one is always present regardless of list
    // state, so it's used here for a state-independent test.
    await user.click(screen.getAllByRole("button", { name: /add customer/i })[0]);
    await user.type(screen.getByLabelText("Name"), "Jordan Lee");
    await user.type(screen.getByLabelText("Phone"), "+15559876543");
    await user.type(screen.getByLabelText("Email"), "jordan@example.com");
    await user.click(screen.getByRole("button", { name: "Add customer" }));

    await waitFor(() =>
      expect(api.createCustomer).toHaveBeenCalledWith(expect.any(Function), {
        display_name: "Jordan Lee",
        wa_phone: "+15559876543",
        email: "jordan@example.com",
        notes: null,
      }),
    );
    expect(await screen.findByText("Customer added")).toBeInTheDocument();
  });

  it("rejects a blank name without calling the API", async () => {
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
    const user = userEvent.setup();

    renderWithProviders(<CustomersPage />);
    await screen.findByText("No customers yet");

    await user.click(screen.getAllByRole("button", { name: /add customer/i })[0]);
    await user.click(screen.getByRole("button", { name: "Add customer" }));

    expect(await screen.findByText("Name is required")).toBeInTheDocument();
    expect(api.createCustomer).not.toHaveBeenCalled();
  });

  it("offers Add Customer from the empty state", async () => {
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
    const user = userEvent.setup();

    renderWithProviders(<CustomersPage />);
    await screen.findByText("No customers yet");

    const emptyStateButtons = screen.getAllByRole("button", { name: /add customer/i });
    expect(emptyStateButtons.length).toBeGreaterThan(1); // header action + empty-state CTA
    await user.click(emptyStateButtons[emptyStateButtons.length - 1]);

    expect(await screen.findByRole("heading", { name: "Add customer" })).toBeInTheDocument();
  });

  it("edits a customer from the detail pane", async () => {
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [customer()],
      meta: { total: 1, limit: 20, offset: 0 },
    });
    vi.mocked(api.getCustomer).mockResolvedValue(customerDetail());
    vi.mocked(api.updateCustomer).mockResolvedValue(
      customerDetail({ display_name: "Alice Johnson" }),
    );
    const user = userEvent.setup();

    renderWithProviders(<CustomersPage />);
    await user.click(await screen.findByText("Alice Smith"));
    await user.click(await screen.findByRole("button", { name: "Edit customer" }));

    const nameInput = screen.getByLabelText("Name");
    await user.clear(nameInput);
    await user.type(nameInput, "Alice Johnson");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(api.updateCustomer).toHaveBeenCalledWith(
        expect.any(Function),
        "cust-1",
        expect.objectContaining({ display_name: "Alice Johnson" }),
      ),
    );
    expect(await screen.findByText("Customer updated")).toBeInTheDocument();
  });

  it("deletes a customer after confirming, and returns to the list", async () => {
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [customer()],
      meta: { total: 1, limit: 20, offset: 0 },
    });
    vi.mocked(api.getCustomer).mockResolvedValue(customerDetail());
    vi.mocked(api.deleteCustomer).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithProviders(<CustomersPage />);
    await user.click(await screen.findByText("Alice Smith"));
    await user.click(await screen.findByRole("button", { name: "Delete customer" }));

    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /delete/i }));

    await waitFor(() =>
      expect(api.deleteCustomer).toHaveBeenCalledWith(expect.any(Function), "cust-1"),
    );
    expect(
      await screen.findByText("Select a customer to view their profile, pipeline, and timeline."),
    ).toBeInTheDocument();
  });
});
