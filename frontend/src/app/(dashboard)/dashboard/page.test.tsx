import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { Appointment, Conversation, OnboardingStatus } from "@/lib/types";
import DashboardPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    listPending: vi.fn(),
    getOnboardingStatus: vi.fn(),
    listConversations: vi.fn(),
    listCustomers: vi.fn(),
    listAppointments: vi.fn(),
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

const onboardingStatus: OnboardingStatus = {
  has_business: true,
  business: {
    id: "biz-1",
    name: "Stoneveil Dental",
    onboarding_status: "live",
    whatsapp_connection_status: "connected",
  } as OnboardingStatus["business"],
};

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={mockAuth}>{ui}</AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getOnboardingStatus).mockResolvedValue(onboardingStatus);
    // Safe defaults so every test only needs to override what it cares about.
    vi.mocked(api.listPending).mockResolvedValue([]);
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 1, offset: 0 },
    });
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 1, offset: 0 },
    });
    vi.mocked(api.listAppointments).mockResolvedValue([]);
  });

  it("shows real conversation and customer totals from existing list endpoints", async () => {
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [],
      meta: { total: 37, limit: 1, offset: 0 },
    });
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [],
      meta: { total: 12, limit: 1, offset: 0 },
    });

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("37")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(api.listConversations).toHaveBeenCalledWith(
      expect.any(Function),
      expect.objectContaining({ limit: 1 }),
    );
    expect(api.listCustomers).toHaveBeenCalledWith(
      expect.any(Function),
      expect.objectContaining({ limit: 1 }),
    );
  });

  it("shows the pending-approval count and customer name", async () => {
    vi.mocked(api.listPending).mockResolvedValue([
      {
        id: "msg-1",
        conversation_id: "conv-1",
        body: "Yes, we're open!",
        created_at: new Date().toISOString(),
        customer: { id: "cust-1", display_name: "Jordan Lee", wa_phone: "+15551230000" },
        conversation_preview: null,
      },
    ]);

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("Yes, we're open!")).toBeInTheDocument();
    expect(screen.getByText("Jordan Lee")).toBeInTheDocument();
  });

  it("shows a retryable error instead of a misleading zero when pending approvals fail to load", async () => {
    vi.mocked(api.listPending).mockRejectedValue(new Error("Network error"));

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("Couldn't load pending approvals")).toBeInTheDocument();
    expect(screen.queryByText("Nothing pending")).not.toBeInTheDocument();
    expect(screen.getAllByText("Couldn't load").length).toBeGreaterThan(0);
  });

  it("shows a dash instead of a misleading zero when conversation/customer totals fail to load", async () => {
    vi.mocked(api.listConversations).mockRejectedValue(new Error("Network error"));
    vi.mocked(api.listCustomers).mockRejectedValue(new Error("Network error"));

    renderWithProviders(<DashboardPage />);

    await screen.findByText("Nothing pending");
    expect(await screen.findAllByText("—")).toHaveLength(2);
    expect(await screen.findAllByText("Couldn't load")).toHaveLength(2);
  });

  it("shows upcoming appointments with customer name, time range, and status", async () => {
    const appointment: Appointment = {
      id: "appt-1",
      customer: { id: "cust-1", display_name: "Jordan Lee", wa_phone: "+15551230000" },
      conversation_id: null,
      starts_at: "2026-08-05T14:00:00",
      ends_at: "2026-08-05T15:00:00",
      status: "booked",
      created_at: "2026-08-01T00:00:00",
      updated_at: "2026-08-01T00:00:00",
    };
    vi.mocked(api.listAppointments).mockResolvedValue([appointment]);

    renderWithProviders(<DashboardPage />);

    // Wait for the appointment data itself to render before asserting the
    // rest — "Upcoming appointments" is static label text present from the
    // first render, so it resolves before the async data does.
    expect(await screen.findByText("Jordan Lee")).toBeInTheDocument();
    expect(screen.getAllByText("Upcoming appointments")).toHaveLength(2);
    expect(screen.getByText("Booked")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument(); // the KPI count
  });

  it("shows a meaningful empty state when there are no upcoming appointments", async () => {
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("No upcoming appointments")).toBeInTheDocument();
  });

  it("shows a retryable error for the appointments widget when it fails to load", async () => {
    vi.mocked(api.listAppointments).mockRejectedValue(new Error("Network error"));

    renderWithProviders(<DashboardPage />);

    expect(await screen.findAllByText("Couldn't load")).not.toHaveLength(0);
  });

  it("shows recent conversations with customer name, preview, and status badge", async () => {
    const conversation: Conversation = {
      id: "conv-1",
      status: "escalated",
      customer: { id: "cust-2", display_name: "Morgan Reyes", wa_phone: "+15559876543" },
      last_message_at: new Date().toISOString(),
      preview: "Can I speak to someone about a refund?",
      has_pending_approval: false,
      created_at: new Date().toISOString(),
    };
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [conversation],
      meta: { total: 1, limit: 5, offset: 0 },
    });

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("Morgan Reyes")).toBeInTheDocument();
    expect(screen.getByText("Can I speak to someone about a refund?")).toBeInTheDocument();
    expect(screen.getByText("Escalated")).toBeInTheDocument();
  });

  it("shows a meaningful empty state when there are no recent conversations", async () => {
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("No conversations yet")).toBeInTheDocument();
  });

  it("refreshes pending, conversations, and appointments when Refresh is clicked", async () => {
    renderWithProviders(<DashboardPage />);
    await screen.findByText("Nothing pending");
    vi.mocked(api.listPending).mockClear();
    vi.mocked(api.listConversations).mockClear();
    vi.mocked(api.listAppointments).mockClear();

    await userEvent.click(screen.getByRole("button", { name: /refresh/i }));

    expect(api.listPending).toHaveBeenCalled();
    expect(api.listConversations).toHaveBeenCalled();
    expect(api.listAppointments).toHaveBeenCalled();
  });
});
