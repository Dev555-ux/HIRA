import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { AnalyticsDashboard } from "@/lib/types";
import AnalyticsPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: { getAnalyticsDashboard: vi.fn() },
}));

import { api } from "@/lib/api";

const mockAuth: AuthContextValue = {
  getToken: async () => "test-token",
  user: { name: "Dev", email: "dev@hira.local", imageUrl: null },
  isLoaded: true,
  mocked: false,
  signOut: vi.fn(),
  openProfile: vi.fn(),
};

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={mockAuth}>{ui}</AuthContext.Provider>
    </QueryClientProvider>,
  );
}

const EMPTY_DASHBOARD: AnalyticsDashboard = {
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

const POPULATED_DASHBOARD: AnalyticsDashboard = {
  ...EMPTY_DASHBOARD,
  overview: {
    total_conversations: 128,
    messages_today: 12,
    ai_responses_today: 9,
    failed_responses_today: 1,
    avg_response_time_seconds: 84,
  },
  business_health: {
    ...EMPTY_DASHBOARD.business_health,
    onboarding_status: "live",
    whatsapp: { status: "connected", display_phone_number: "+15551230000" },
    knowledge_base: { published_count: 18, draft_count: 2, last_updated_at: "2026-07-20T00:00:00Z" },
    alerts: [],
    conversations_by_status: { active: 40, escalated: 3, closed: 85 },
    leads_by_stage: { new: 5, qualified: 3, won: 2 },
    leads_by_source: { referral: 4, website: 6 },
    appointments_by_status: { booked: 10, cancelled: 1 },
  },
  trends: {
    conversations: [
      { date: "2026-07-01", count: 3 },
      { date: "2026-07-02", count: 5 },
    ],
    messages: [
      { date: "2026-07-01", count: 10 },
      { date: "2026-07-02", count: 14 },
    ],
    leads: [
      { date: "2026-07-01", count: 1 },
      { date: "2026-07-02", count: 0 },
    ],
    appointments: [
      { date: "2026-07-01", count: 0 },
      { date: "2026-07-02", count: 2 },
    ],
  },
  ai_impact: {
    conversations_handled: 112,
    human_escalations: 16,
    leads_created: 8,
    appointments_booked: 10,
    kb_grounded_replies: 70,
    ai_responses: 118,
    estimated_hours_saved: 7.5,
  },
  ai_performance: {
    total_turns: 200,
    employee_utilisation: { scheduler: 120 },
    most_used_employee: "scheduler",
    most_used_tools: [{ tool_name: "book_appointment", count: 40 }],
    failed_tool_executions: 2,
    governance_blocks: 1,
    avg_plan_length: 1.8,
    avg_execution_time_ms: 850,
  },
};

describe("AnalyticsPage", () => {
  beforeEach(() => {
    vi.mocked(api.getAnalyticsDashboard).mockReset();
  });

  it("shows a retry action when loading fails", async () => {
    vi.mocked(api.getAnalyticsDashboard).mockRejectedValue(new Error("network down"));
    renderWithProviders(<AnalyticsPage />);

    expect(await screen.findByText("Couldn't load analytics")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows an honest empty state for a brand-new business, no fake tiles", async () => {
    vi.mocked(api.getAnalyticsDashboard).mockResolvedValue(EMPTY_DASHBOARD);
    renderWithProviders(<AnalyticsPage />);

    expect(
      await screen.findByText("Analytics unlock as conversations come in"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Total conversations")).not.toBeInTheDocument();
  });

  it("never renders placeholder or 'coming soon' text", async () => {
    vi.mocked(api.getAnalyticsDashboard).mockResolvedValue(POPULATED_DASHBOARD);
    renderWithProviders(<AnalyticsPage />);

    await screen.findByText("This period, at a glance");
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/placeholder/i)).not.toBeInTheDocument();
  });

  it("renders real KPI values from the overview section", async () => {
    vi.mocked(api.getAnalyticsDashboard).mockResolvedValue(POPULATED_DASHBOARD);
    renderWithProviders(<AnalyticsPage />);

    // "128" legitimately also appears in the conversations-by-status donut's
    // center total (its segments sum to the same real number) — scope to
    // the KPI stat card specifically rather than asserting it's unique
    // page-wide.
    const label = await screen.findByText("Total conversations");
    const statCard = label.closest<HTMLElement>(".rounded-2xl")!;
    expect(within(statCard).getByText("128")).toBeInTheDocument();
    // Avg response time (84s) renders as "1m" in the KPI strip; Response
    // Health phrases the same real value in its own sentence rather than
    // repeating the bare "1m" a second time on the page (Sprint 85).
    expect(screen.getByText("1m")).toBeInTheDocument();
    expect(screen.getByText(/Responding in 1m on average/)).toBeInTheDocument();
  });

  it("shows Executive Health Score signals derived from real business health fields", async () => {
    vi.mocked(api.getAnalyticsDashboard).mockResolvedValue(POPULATED_DASHBOARD);
    renderWithProviders(<AnalyticsPage />);

    const list = await screen.findByRole("list", { name: /business health signals/i });
    expect(within(list).getByText("Onboarding Live")).toBeInTheDocument();
    expect(within(list).getByText("WhatsApp Connected")).toBeInTheDocument();
    expect(within(list).getByText("Knowledge Base Healthy")).toBeInTheDocument();
  });

  it("reflects real alerts in the Executive Health Score", async () => {
    vi.mocked(api.getAnalyticsDashboard).mockResolvedValue({
      ...POPULATED_DASHBOARD,
      business_health: {
        ...POPULATED_DASHBOARD.business_health,
        alerts: ["missing_knowledge_base", "ai_failures"],
      },
    });
    renderWithProviders(<AnalyticsPage />);

    const list = await screen.findByRole("list", { name: /business health signals/i });
    expect(within(list).getByText("Knowledge Base Empty")).toBeInTheDocument();
    expect(within(list).getByText("AI Failures Today")).toBeInTheDocument();
  });

  it("shows real alert labels, each linking to where it gets fixed, in Executive Summary", async () => {
    vi.mocked(api.getAnalyticsDashboard).mockResolvedValue({
      ...POPULATED_DASHBOARD,
      business_health: {
        ...POPULATED_DASHBOARD.business_health,
        alerts: ["missing_knowledge_base", "ai_failures"],
      },
    });
    renderWithProviders(<AnalyticsPage />);

    expect(await screen.findByRole("link", { name: /No Knowledge Base/ })).toHaveAttribute(
      "href",
      "/knowledge-base",
    );
    expect(screen.getByRole("link", { name: /AI failures/ })).toHaveAttribute("href", "#ai-performance");
  });

  it("marks AI Impact with the AI-identity spine and shows real figures", async () => {
    vi.mocked(api.getAnalyticsDashboard).mockResolvedValue(POPULATED_DASHBOARD);
    renderWithProviders(<AnalyticsPage />);

    const heading = await screen.findByText(/AI Impact/);
    const card = heading.closest<HTMLElement>(".rounded-lg")!;
    expect(within(card).getByText("112")).toBeInTheDocument();
    expect(within(card).getByText("Conversations handled")).toBeInTheDocument();
    expect(within(card).getByText("≈7.5h")).toBeInTheDocument();
  });

  it("renders a trend chart per series with an accessible summary and data table", async () => {
    vi.mocked(api.getAnalyticsDashboard).mockResolvedValue(POPULATED_DASHBOARD);
    renderWithProviders(<AnalyticsPage />);

    // "Conversations over time" is the hero chart's accessible title (used
    // in its aria-label), not its visible heading — the visible card title
    // is "Conversation trend" (Sprint 85).
    await screen.findByText("Conversation trend");
    const charts = screen.getAllByRole("img", { name: /over time/i });
    expect(charts.length).toBe(4);
    // 4 trend charts + 3 donuts (AI coverage, conversation status, appointment
    // status — Sprint 85 added the AI coverage donut), each with its own
    // accessible table fallback.
    expect(screen.getAllByText("View as table").length).toBe(7);
  });

  it("renders operational/customer/appointment breakdowns from real counts", async () => {
    vi.mocked(api.getAnalyticsDashboard).mockResolvedValue(POPULATED_DASHBOARD);
    renderWithProviders(<AnalyticsPage />);

    expect(await screen.findByText("Conversations by status")).toBeInTheDocument();
    // Each donut label appears twice — once in the visible legend, once in
    // its table fallback — so these assert presence, not uniqueness.
    expect(screen.getAllByText("Escalated").length).toBeGreaterThan(0); // CONVERSATION_STATUS_BADGE label
    expect(screen.getByText("Won")).toBeInTheDocument(); // STAGE_LABEL — leads stay a bar, only rendered once
    expect(screen.getAllByText("Booked").length).toBeGreaterThan(0); // APPOINTMENT_STATUS_BADGE label
  });

  it("renders AI Performance as grouped diagnostics with real reliability figures", async () => {
    vi.mocked(api.getAnalyticsDashboard).mockResolvedValue(POPULATED_DASHBOARD);
    renderWithProviders(<AnalyticsPage />);

    expect(await screen.findByText("AI Performance")).toBeInTheDocument();
    expect(screen.getByText("Turns traced")).toBeInTheDocument();
    expect(screen.getByText("book_appointment")).toBeInTheDocument();
    // POPULATED_DASHBOARD has real failures (failed_tool_executions: 2,
    // governance_blocks: 1), so the section should say so, not "operating
    // normally".
    expect(screen.getByText("Needs a look")).toBeInTheDocument();
  });

  it("switching the range re-fetches with the new range and issues exactly one request", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getAnalyticsDashboard).mockResolvedValue(POPULATED_DASHBOARD);
    renderWithProviders(<AnalyticsPage />);

    await screen.findByText("This period, at a glance");
    expect(api.getAnalyticsDashboard).toHaveBeenCalledTimes(1);
    expect(api.getAnalyticsDashboard).toHaveBeenCalledWith(expect.any(Function), "30d");

    await user.click(screen.getByRole("button", { name: "7d" }));

    await waitFor(() =>
      expect(api.getAnalyticsDashboard).toHaveBeenCalledWith(expect.any(Function), "7d"),
    );
    expect(api.getAnalyticsDashboard).toHaveBeenCalledTimes(2);
  });
});
