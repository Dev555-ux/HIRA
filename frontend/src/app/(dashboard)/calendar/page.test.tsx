import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/toast";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { CalendarSettings, CalendarStatus } from "@/lib/types";
import CalendarPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    getCalendarSettings: vi.fn(),
    updateCalendarSettings: vi.fn(),
    getCalendarStatus: vi.fn(),
    startCalendarConnect: vi.fn(),
    disconnectCalendar: vi.fn(),
  },
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
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

function settings(overrides: Partial<CalendarSettings> = {}): CalendarSettings {
  return { timezone: "UTC", working_hours: null, ...overrides };
}

function status(overrides: Partial<CalendarStatus> = {}): CalendarStatus {
  return { connected: false, calendar_id: null, ...overrides };
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

describe("CalendarPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getCalendarSettings).mockResolvedValue(settings());
    vi.mocked(api.getCalendarStatus).mockResolvedValue(status());
    Object.defineProperty(window, "location", {
      writable: true,
      value: { ...window.location, href: "" },
    });
  });

  it("shows 'Not connected' and a connect button when no calendar is linked", async () => {
    renderWithProviders(<CalendarPage />);
    expect(await screen.findByText("Not connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /connect google calendar/i })).toBeInTheDocument();
  });

  it("redirects the browser to Google's authorization URL on connect", async () => {
    vi.mocked(api.startCalendarConnect).mockResolvedValue({
      authorization_url: "https://accounts.google.com/o/oauth2/auth?foo=bar",
    });
    const user = userEvent.setup();
    renderWithProviders(<CalendarPage />);

    await user.click(await screen.findByRole("button", { name: /connect google calendar/i }));

    await waitFor(() =>
      expect(window.location.href).toBe("https://accounts.google.com/o/oauth2/auth?foo=bar"),
    );
  });

  it("shows 'Connected' with the calendar id and a disconnect button", async () => {
    vi.mocked(api.getCalendarStatus).mockResolvedValue(
      status({ connected: true, calendar_id: "primary" }),
    );
    renderWithProviders(<CalendarPage />);

    expect(await screen.findByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("primary")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /disconnect/i })).toBeInTheDocument();
  });

  it("disconnects after confirming", async () => {
    vi.mocked(api.getCalendarStatus).mockResolvedValue(
      status({ connected: true, calendar_id: "primary" }),
    );
    vi.mocked(api.disconnectCalendar).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithProviders(<CalendarPage />);

    await user.click(await screen.findByRole("button", { name: /disconnect/i }));
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /disconnect/i }));

    await waitFor(() => expect(api.disconnectCalendar).toHaveBeenCalledWith(expect.any(Function)));
    expect(await screen.findByText("Google Calendar disconnected")).toBeInTheDocument();
  });

  it("shows the current timezone and lets the user save a new one", async () => {
    vi.mocked(api.updateCalendarSettings).mockResolvedValue(
      settings({ timezone: "America/New_York" }),
    );
    const user = userEvent.setup();
    renderWithProviders(<CalendarPage />);

    const timezoneInput = await screen.findByPlaceholderText(/america\/new_york/i);
    expect(timezoneInput).toHaveValue("UTC");

    await user.clear(timezoneInput);
    await user.type(timezoneInput, "America/New_York");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() =>
      expect(api.updateCalendarSettings).toHaveBeenCalledWith(
        expect.any(Function),
        expect.objectContaining({ timezone: "America/New_York" }),
      ),
    );
    expect(await screen.findByText("Calendar settings saved")).toBeInTheDocument();
  });

  it("shows all seven days as closed by default", async () => {
    renderWithProviders(<CalendarPage />);
    await screen.findByText("Monday");

    expect(screen.getAllByText("Closed")).toHaveLength(7);
  });

  it("reveals open/close time inputs when a day is toggled on", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CalendarPage />);
    await screen.findByText("Monday");

    const mondayCheckbox = screen.getByRole("checkbox", { name: /monday/i });
    await user.click(mondayCheckbox);

    expect(screen.queryAllByText("Closed")).toHaveLength(6);
  });

  it("pre-fills existing working hours from the server", async () => {
    vi.mocked(api.getCalendarSettings).mockResolvedValue(
      settings({ working_hours: { mon: { open: "09:00", close: "17:00" } } }),
    );
    renderWithProviders(<CalendarPage />);

    await screen.findByText("Monday");
    expect(screen.queryAllByText("Closed")).toHaveLength(6);
  });

  it("shows a retryable error state when the connection status fails to load", async () => {
    vi.mocked(api.getCalendarStatus).mockReset();
    vi.mocked(api.getCalendarStatus).mockRejectedValue(new Error("Network error"));
    renderWithProviders(<CalendarPage />);

    expect(await screen.findByText("Couldn't load calendar status")).toBeInTheDocument();
    expect(screen.queryByText("Not connected")).not.toBeInTheDocument();
  });

  it("shows a retryable error state when calendar settings fail to load", async () => {
    vi.mocked(api.getCalendarSettings).mockReset();
    vi.mocked(api.getCalendarSettings).mockRejectedValue(new Error("Network error"));
    renderWithProviders(<CalendarPage />);

    expect(await screen.findByText("Couldn't load calendar settings")).toBeInTheDocument();
  });
});
