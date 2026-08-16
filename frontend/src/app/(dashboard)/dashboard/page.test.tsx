import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/toast";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { Appointment, AnalyticsDashboard, OnboardingStatus } from "@/lib/types";
import DashboardPage from "./page";

const routerPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush }),
}));

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    listPending: vi.fn(),
    getOnboardingStatus: vi.fn(),
    listActivity: vi.fn(),
    listLeads: vi.fn(),
    listAppointments: vi.fn(),
    listEscalations: vi.fn(),
    getAnalyticsDashboard: vi.fn(),
    listKbEntries: vi.fn(),
    listCustomers: vi.fn(),
    approveMessage: vi.fn(),
    rejectMessage: vi.fn(),
    updateDraft: vi.fn(),
  },
}));

import { api } from "@/lib/api";

// Mirrors analytics/page.test.tsx's own EMPTY_DASHBOARD fixture.
const EMPTY_ANALYTICS_DASHBOARD: AnalyticsDashboard = {
  range: "30d",
  overview: {
    total_conversations: 0,
    messages_today: 0,
    ai_responses_today: 0,
    failed_responses_today: 0,
    avg_response_time_seconds: null,
  },
  business_health: {
    onboarding_status: "created",
    trial_ends_at: null,
    created_at: "2026-07-01T00:00:00Z",
    whatsapp: { status: "not_connected", display_phone_number: null },
    knowledge_base: { published_count: 0, draft_count: 0, last_updated_at: null },
    alerts: [],
    conversations_by_status: {},
    leads_by_stage: {},
    leads_by_source: {},
    appointments_by_status: {},
  },
  trends: { conversations: [], messages: [], leads: [], appointments: [] },
  ai_impact: {
    conversations_handled: 0,
    human_escalations: 0,
    leads_created: 0,
    appointments_booked: 0,
    kb_grounded_replies: 0,
    ai_responses: 0,
    estimated_hours_saved: 0,
  },
  ai_performance: {
    total_turns: 0,
    employee_utilisation: {},
    most_used_employee: null,
    most_used_tools: [],
    failed_tool_executions: 0,
    governance_blocks: 0,
    avg_plan_length: 0,
    avg_execution_time_ms: 0,
  },
};

const mockAuth: AuthContextValue = {
  getToken: async () => "test-token",
  user: { name: "Dev", email: "dev@test.com", imageUrl: null },
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
      <AuthContext.Provider value={mockAuth}>
        <ToastProvider>{ui}</ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getOnboardingStatus).mockResolvedValue(onboardingStatus);
    // Safe defaults so every test only needs to override what it cares about.
    vi.mocked(api.listPending).mockResolvedValue([]);
    vi.mocked(api.listActivity).mockResolvedValue([]);
    vi.mocked(api.listLeads).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 5, offset: 0 },
    });
    vi.mocked(api.listAppointments).mockResolvedValue([]);
    vi.mocked(api.listEscalations).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 5, offset: 0 },
    });
    vi.mocked(api.getAnalyticsDashboard).mockResolvedValue(EMPTY_ANALYTICS_DASHBOARD);
    vi.mocked(api.listKbEntries).mockResolvedValue([]);
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
    vi.mocked(api.approveMessage).mockResolvedValue({ id: "msg-1", status: "sent" });
    vi.mocked(api.rejectMessage).mockResolvedValue({ id: "msg-1", status: "rejected" });
    vi.mocked(api.updateDraft).mockResolvedValue({
      id: "msg-1",
      body: "revised",
      status: "pending_approval",
    });
  });

  it("greets the signed-in owner by name", async () => {
    renderWithProviders(<DashboardPage />);
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Dev");
  });

  it("shows a reassuring close when there's nothing pending", async () => {
    renderWithProviders(<DashboardPage />);
    expect(await screen.findByText("Nothing urgent requires you.")).toBeInTheDocument();
  });

  it("does not show the reassuring close when a reply needs review", async () => {
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
    await screen.findByText("Yes, we're open!");
    expect(screen.queryByText("Nothing urgent requires you.")).not.toBeInTheDocument();
  });

  it("shows the pending-reply count and customer name", async () => {
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
    expect(screen.getByText("Pending replies")).toBeInTheDocument();
    expect(screen.getByText("1 waiting")).toBeInTheDocument();
    expect(screen.getAllByText("Jordan Lee").length).toBeGreaterThan(0);
  });

  it("shows a retryable error instead of a misleading empty state when pending approvals fail to load", async () => {
    vi.mocked(api.listPending).mockRejectedValue(new Error("Network error"));

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("Couldn't load pending approvals")).toBeInTheDocument();
    expect(screen.queryByText("Pending replies")).not.toBeInTheDocument();
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

    await waitFor(() => expect(screen.getAllByText("Jordan Lee").length).toBeGreaterThan(0));
    expect(screen.getByText("Upcoming appointments")).toBeInTheDocument();
    expect(screen.getByText("Booked")).toBeInTheDocument();
  });

  it("shows a meaningful empty state when there are no upcoming appointments", async () => {
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("No upcoming appointments.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New appointment" })).toHaveAttribute(
      "href",
      "/appointments",
    );
  });

  it("shows a retryable error for the appointments widget when it fails to load", async () => {
    vi.mocked(api.listAppointments).mockRejectedValue(new Error("Network error"));

    renderWithProviders(<DashboardPage />);

    expect(await screen.findAllByText("Couldn't load")).not.toHaveLength(0);
  });

  it("renders each AI activity entry's real summary sentence and timestamp", async () => {
    vi.mocked(api.listActivity).mockResolvedValue([
      {
        id: "trace-1",
        conversation_id: "conv-1",
        customer: { id: "cust-3", display_name: "Sam Torres" },
        category: "action",
        outcome: "sent",
        summary: "Booked an appointment for Sam Torres",
        created_at: new Date().toISOString(),
      },
    ]);

    renderWithProviders(<DashboardPage />);

    const feed = await screen.findByTestId("activity-feed");
    expect(within(feed).getByText("Booked an appointment for Sam Torres")).toBeInTheDocument();
  });

  it("shows a meaningful empty state when there is no AI activity yet", async () => {
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("Waiting for your first customer")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Try Demo Chat" })).toHaveAttribute(
      "href",
      "/demo",
    );
  });

  it("shows a retryable error instead of a misleading empty state when AI activity fails to load", async () => {
    vi.mocked(api.listActivity).mockRejectedValue(new Error("Network error"));

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("Couldn't load activity")).toBeInTheDocument();
    vi.mocked(api.listActivity).mockClear();
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(api.listActivity).toHaveBeenCalled();
  });

  it("surfaces a real WhatsApp connection problem via the Health Score strip", async () => {
    vi.mocked(api.getAnalyticsDashboard).mockResolvedValue({
      ...EMPTY_ANALYTICS_DASHBOARD,
      business_health: {
        ...EMPTY_ANALYTICS_DASHBOARD.business_health,
        alerts: ["whatsapp_disconnected"],
      },
    });
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("WhatsApp Not connected")).toBeInTheDocument();
    expect(
      screen.queryByText(/groq|llama|claude|embedding|ai provider|knowledge search/i),
    ).not.toBeInTheDocument();
  });

  it("refreshes every dashboard data source when Refresh is clicked", async () => {
    renderWithProviders(<DashboardPage />);
    await screen.findByText("Nothing urgent requires you.");
    vi.mocked(api.listPending).mockClear();
    vi.mocked(api.getOnboardingStatus).mockClear();
    vi.mocked(api.listActivity).mockClear();
    vi.mocked(api.listLeads).mockClear();
    vi.mocked(api.listAppointments).mockClear();
    vi.mocked(api.listEscalations).mockClear();
    vi.mocked(api.getAnalyticsDashboard).mockClear();
    vi.mocked(api.listKbEntries).mockClear();
    vi.mocked(api.listCustomers).mockClear();

    await userEvent.click(screen.getByRole("button", { name: /refresh/i }));

    expect(api.listPending).toHaveBeenCalled();
    expect(api.getOnboardingStatus).toHaveBeenCalled();
    expect(api.listActivity).toHaveBeenCalled();
    expect(api.listLeads).toHaveBeenCalled();
    expect(api.listEscalations).toHaveBeenCalled();
    expect(api.getAnalyticsDashboard).toHaveBeenCalled();
    expect(api.listKbEntries).toHaveBeenCalled();
    expect(api.listAppointments).toHaveBeenCalled();
    expect(api.listCustomers).toHaveBeenCalled();
  });

  // Inline review, wired directly on the Dashboard (not via
  // PendingReviewContainer/CONVERSATIONS_KEY — see PendingReviewCard's own
  // comment) — confirms the same use-pending.ts mutations Inbox and
  // /pending already rely on behave identically when triggered from here.
  describe("inline review", () => {
    const reply = {
      id: "msg-1",
      conversation_id: "conv-1",
      body: "Yes, we're open!",
      created_at: new Date().toISOString(),
      customer: { id: "cust-1", display_name: "Jordan Lee", wa_phone: "+15551230000" },
      conversation_preview: null,
    };

    it("approve removes the card via the optimistic PENDING_KEY update", async () => {
      vi.mocked(api.listPending).mockResolvedValueOnce([reply]).mockResolvedValue([]);
      const user = userEvent.setup();
      renderWithProviders(<DashboardPage />);

      await screen.findByText("Yes, we're open!");
      await user.click(screen.getByRole("button", { name: /approve & send/i }));

      await waitFor(() => expect(screen.queryByText("Yes, we're open!")).not.toBeInTheDocument());
      expect(api.approveMessage).toHaveBeenCalledWith(expect.any(Function), "msg-1");
    });

    it("reject removes the card via the same optimistic PENDING_KEY update", async () => {
      vi.mocked(api.listPending).mockResolvedValueOnce([reply]).mockResolvedValue([]);
      const user = userEvent.setup();
      renderWithProviders(<DashboardPage />);

      await screen.findByText("Yes, we're open!");
      await user.click(screen.getByRole("button", { name: /reject/i }));

      await waitFor(() => expect(screen.queryByText("Yes, we're open!")).not.toBeInTheDocument());
      expect(api.rejectMessage).toHaveBeenCalledWith(expect.any(Function), "msg-1");
    });

    it("edit saves the revised draft in place, without removing the card", async () => {
      vi.mocked(api.listPending).mockResolvedValue([reply]);
      const user = userEvent.setup();
      renderWithProviders(<DashboardPage />);

      await screen.findByText("Yes, we're open!");
      await user.click(screen.getByRole("button", { name: /edit/i }));
      const box = screen.getByLabelText(/edit reply/i);
      await user.clear(box);
      await user.type(box, "revised");
      await user.click(screen.getByRole("button", { name: /save/i }));

      await waitFor(() =>
        expect(api.updateDraft).toHaveBeenCalledWith(expect.any(Function), "msg-1", "revised"),
      );
      // Still awaiting review, still visible — an edit doesn't remove the card.
      const section = (await screen.findByText("Pending replies")).closest<HTMLElement>(".rounded-2xl")!;
      expect(within(section).getByText("Jordan Lee")).toBeInTheDocument();
    });

    it("surfaces a destructive toast when approve fails, leaving the card reviewable", async () => {
      vi.mocked(api.listPending).mockResolvedValue([reply]);
      vi.mocked(api.approveMessage).mockRejectedValueOnce(new Error("network"));
      const user = userEvent.setup();
      renderWithProviders(<DashboardPage />);

      await screen.findByText("Yes, we're open!");
      await user.click(screen.getByRole("button", { name: /approve & send/i }));

      await waitFor(() => expect(screen.getByText("Yes, we're open!")).toBeInTheDocument());
      expect(screen.getByRole("button", { name: /approve & send/i })).toBeEnabled();
    });

    it("shows every open pending reply, not just a preview", async () => {
      const replies = Array.from({ length: 7 }, (_, i) => ({
        ...reply,
        id: `msg-${i}`,
        conversation_id: `conv-${i}`,
        body: `Reply body ${i}`,
        customer: { id: `cust-${i}`, display_name: `Customer ${i}`, wa_phone: "+15551230000" },
      }));
      vi.mocked(api.listPending).mockResolvedValue(replies);
      renderWithProviders(<DashboardPage />);

      await screen.findByText("Reply body 0");
      expect(screen.getByText("Reply body 6")).toBeInTheDocument();
      expect(screen.getByText("7 waiting")).toBeInTheDocument();
    });
  });

  describe("Needs your attention", () => {
    it("shows a positive empty state when there's nothing pending and no open escalations", async () => {
      renderWithProviders(<DashboardPage />);
      await screen.findByText("Nothing urgent requires you.");
      expect(screen.getByText("Nothing needs you right now")).toBeInTheDocument();
    });

    it("shows an open escalation, even with nothing pending", async () => {
      vi.mocked(api.listEscalations).mockResolvedValue({
        data: [
          {
            id: "esc-1",
            reason: "low_confidence",
            status: "open",
            assigned_to: null,
            resolved_by: null,
            resolved_at: null,
            created_at: new Date().toISOString(),
            conversation: {
              id: "conv-9",
              customer: { id: "cust-9", display_name: "Priya Shah", wa_phone: "+15550009999" },
            },
          },
        ],
        meta: { total: 1, limit: 5, offset: 0 },
      });

      renderWithProviders(<DashboardPage />);

      expect(await screen.findByText("Priya Shah")).toBeInTheDocument();
      expect(screen.getByText("Needs your attention")).toBeInTheDocument();
    });

    it("routes to /escalations from an escalation's Review action", async () => {
      vi.mocked(api.listEscalations).mockResolvedValue({
        data: [
          {
            id: "esc-1",
            reason: "customer_request",
            status: "open",
            assigned_to: null,
            resolved_by: null,
            resolved_at: null,
            created_at: new Date().toISOString(),
            conversation: {
              id: "conv-9",
              customer: { id: "cust-9", display_name: "Priya Shah", wa_phone: null },
            },
          },
        ],
        meta: { total: 1, limit: 5, offset: 0 },
      });
      const user = userEvent.setup();
      renderWithProviders(<DashboardPage />);

      await screen.findByText("Priya Shah");
      await user.click(screen.getByRole("button", { name: /priya shah/i }));
      expect(routerPush).toHaveBeenCalledWith("/escalations");
    });

    it("shows a retryable error instead of a misleading empty state when escalations fail to load", async () => {
      vi.mocked(api.listEscalations).mockRejectedValue(new Error("Network error"));

      renderWithProviders(<DashboardPage />);

      expect(await screen.findByText("Couldn't load escalations")).toBeInTheDocument();
    });

    it("surfaces a today-escalated conversation as a real highlight", async () => {
      vi.mocked(api.listEscalations).mockResolvedValue({
        data: [
          {
            id: "esc-1",
            reason: "other",
            status: "open",
            assigned_to: null,
            resolved_by: null,
            resolved_at: null,
            created_at: new Date().toISOString(),
            conversation: { id: "conv-9", customer: { id: "cust-9", display_name: "Priya", wa_phone: null } },
          },
        ],
        meta: { total: 1, limit: 5, offset: 0 },
      });
      renderWithProviders(<DashboardPage />);

      expect(await screen.findByText("1 conversation escalated")).toBeInTheDocument();
      expect(screen.queryByText("Nothing urgent requires you.")).not.toBeInTheDocument();
    });
  });

  describe("Learned today", () => {
    it("hides Learned today when no knowledge entry was created today", async () => {
      vi.mocked(api.listKbEntries).mockResolvedValue([
        {
          id: "kb-1",
          title: "Old FAQ",
          content: "...",
          status: "published",
          import_batch_id: null,
          created_at: "2020-01-01T00:00:00Z",
          updated_at: "2020-01-01T00:00:00Z",
        },
      ]);

      renderWithProviders(<DashboardPage />);
      await screen.findByText("Nothing urgent requires you.");
      expect(screen.queryByText("Learned today")).not.toBeInTheDocument();
    });

    it("shows Learned today with entries created today, each linking to Knowledge Base", async () => {
      vi.mocked(api.listKbEntries).mockResolvedValue([
        {
          id: "kb-1",
          title: "Weekend hours",
          content: "...",
          status: "published",
          import_batch_id: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ]);

      renderWithProviders(<DashboardPage />);

      expect(await screen.findByText("Learned today")).toBeInTheDocument();
      expect(screen.getByText("1 new entry")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Weekend hours" })).toHaveAttribute(
        "href",
        "/knowledge-base",
      );
    });
  });
});
