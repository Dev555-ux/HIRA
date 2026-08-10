import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { FounderAiMetrics, FounderOverview } from "@/lib/types";
import FounderOpsPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
  api: { getFounderOverview: vi.fn(), getFounderAiMetrics: vi.fn() },
}));

import { ApiError, api } from "@/lib/api";

const mockAuth: AuthContextValue = {
  getToken: async () => "test-token",
  user: { name: "Founder", email: "founder@hira.test", imageUrl: null },
  isLoaded: true,
  mocked: true,
  signOut: vi.fn(),
  openProfile: vi.fn(),
};

function renderWithProviders() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={mockAuth}>
        <FounderOpsPage />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

const BASE_OVERVIEW: FounderOverview = {
  summary: {
    total_businesses: 2,
    connected_businesses: 1,
    active_businesses: 1,
    messages_today: 12,
    ai_responses_today: 5,
    failed_responses_today: 1,
    avg_response_time_seconds: 95,
  },
  businesses: [
    {
      id: "biz-1",
      name: "Bright Smile Dental",
      created_at: "2026-07-01T00:00:00Z",
      onboarding_status: "live",
      onboarding_complete: true,
      whatsapp: {
        status: "connected",
        display_phone_number: "+1 555 123 0000",
        credential_stored: true,
        last_inbound_at: "2026-07-25T12:00:00Z",
        last_outbound_at: "2026-07-25T12:01:00Z",
      },
      knowledge_base: { published_count: 12, draft_count: 0, last_updated_at: "2026-07-20T00:00:00Z" },
      ai_activity: { conversations: 8, ai_responses: 20, failed_responses: 0, avg_response_time_seconds: 45 },
      last_activity_at: "2026-07-25T12:01:00Z",
      alerts: [],
    },
    {
      id: "biz-2",
      name: "Struggling Gym",
      created_at: "2026-07-10T00:00:00Z",
      onboarding_status: "created",
      onboarding_complete: false,
      whatsapp: {
        status: "not_connected",
        display_phone_number: null,
        credential_stored: false,
        last_inbound_at: null,
        last_outbound_at: null,
      },
      knowledge_base: { published_count: 0, draft_count: 2, last_updated_at: "2026-07-11T00:00:00Z" },
      ai_activity: { conversations: 0, ai_responses: 0, failed_responses: 0, avg_response_time_seconds: null },
      last_activity_at: null,
      alerts: ["whatsapp_disconnected", "missing_knowledge_base"],
    },
  ],
};

const EMPTY_AI_METRICS: FounderAiMetrics = {
  total_turns: 0,
  employee_utilisation: {},
  most_used_employee: null,
  most_used_tools: [],
  failed_tool_executions: 0,
  governance_blocks: 0,
  avg_plan_length: 0,
  avg_execution_time_ms: 0,
};

describe("FounderOpsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Sprint 76: AiMetricsSection fetches independently of the overview —
    // give it a stable, resolved default so tests focused on the overview
    // itself aren't left with a perpetually loading AI metrics card.
    vi.mocked(api.getFounderAiMetrics).mockResolvedValue(EMPTY_AI_METRICS);
  });

  it("shows the founder summary tiles from real data", async () => {
    vi.mocked(api.getFounderOverview).mockResolvedValue(BASE_OVERVIEW);
    renderWithProviders();

    expect(await screen.findByText("Founder Operations")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument(); // total businesses
    expect(screen.getByText("12")).toBeInTheDocument(); // messages today
    expect(screen.getByText("2m")).toBeInTheDocument(); // avg response time, 95s rounds to 2m
  });

  it("lists every business with its real facets, not placeholders", async () => {
    vi.mocked(api.getFounderOverview).mockResolvedValue(BASE_OVERVIEW);
    renderWithProviders();

    await screen.findByText("Founder Operations");
    const table = screen.getByRole("table");
    expect(within(table).getByText("Bright Smile Dental")).toBeInTheDocument();
    expect(within(table).getByText("Struggling Gym")).toBeInTheDocument();
    expect(within(table).getByText("+1 555 123 0000")).toBeInTheDocument();
    expect(within(table).getByText(/12 published/)).toBeInTheDocument();
    expect(within(table).getByText(/2 draft/)).toBeInTheDocument();
  });

  it("surfaces flagged businesses under Needs attention, and leaves healthy ones out", async () => {
    vi.mocked(api.getFounderOverview).mockResolvedValue(BASE_OVERVIEW);
    renderWithProviders();

    const alertsCard = (await screen.findByText("Needs attention")).closest<HTMLElement>(".rounded-2xl")!;
    expect(within(alertsCard).getByText("Struggling Gym")).toBeInTheDocument();
    expect(within(alertsCard).queryByText("Bright Smile Dental")).not.toBeInTheDocument();
    expect(within(alertsCard).getByText("WhatsApp disconnected")).toBeInTheDocument();
    expect(within(alertsCard).getByText("No Knowledge Base")).toBeInTheDocument();
  });

  it("says nothing is flagged when every business is healthy", async () => {
    vi.mocked(api.getFounderOverview).mockResolvedValue({
      ...BASE_OVERVIEW,
      businesses: [BASE_OVERVIEW.businesses[0]],
    });
    renderWithProviders();

    expect(await screen.findByText("Nothing flagged right now.")).toBeInTheDocument();
  });

  it("shows a generic not-found state for a non-founder caller, revealing nothing about the feature", async () => {
    vi.mocked(api.getFounderOverview).mockRejectedValue(new ApiError(404, "Not found"));
    renderWithProviders();

    expect(await screen.findByText("Not found")).toBeInTheDocument();
    expect(screen.queryByText("Founder Operations")).not.toBeInTheDocument();
    expect(screen.queryByText(/not authorized|forbidden|access denied|founder/i)).not.toBeInTheDocument();
  });

  it("shows a retryable error for a genuine failure, distinct from the not-found state", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getFounderOverview)
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValueOnce(BASE_OVERVIEW);
    renderWithProviders();

    expect(await screen.findByText("Couldn't load the dashboard")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /retry/i }));

    expect(await screen.findByText("Founder Operations")).toBeInTheDocument();
  });

  it("refreshes on demand", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getFounderOverview).mockResolvedValue(BASE_OVERVIEW);
    renderWithProviders();

    await screen.findByText("Founder Operations");
    await user.click(screen.getByRole("button", { name: /refresh/i }));

    expect(api.getFounderOverview).toHaveBeenCalledTimes(2);
  });

  it("shows an honest empty state when there are no businesses at all", async () => {
    vi.mocked(api.getFounderOverview).mockResolvedValue({
      summary: {
        total_businesses: 0,
        connected_businesses: 0,
        active_businesses: 0,
        messages_today: 0,
        ai_responses_today: 0,
        failed_responses_today: 0,
        avg_response_time_seconds: null,
      },
      businesses: [],
    });
    renderWithProviders();

    expect(await screen.findByText("No businesses yet")).toBeInTheDocument();
  });

  describe("AI Employee Activity (Sprint 76)", () => {
    it("shows the honest empty state when no turns have been traced yet", async () => {
      vi.mocked(api.getFounderOverview).mockResolvedValue(BASE_OVERVIEW);
      vi.mocked(api.getFounderAiMetrics).mockResolvedValue(EMPTY_AI_METRICS);
      renderWithProviders();

      expect(
        await screen.findByText(/No AI turns recorded yet/),
      ).toBeInTheDocument();
    });

    it("shows real AI metrics once turns have been traced", async () => {
      vi.mocked(api.getFounderOverview).mockResolvedValue(BASE_OVERVIEW);
      vi.mocked(api.getFounderAiMetrics).mockResolvedValue({
        total_turns: 42,
        employee_utilisation: { scheduler: 30, sales_executive: 12 },
        most_used_employee: "scheduler",
        most_used_tools: [{ tool_name: "book_appointment", count: 25 }],
        failed_tool_executions: 3,
        governance_blocks: 5,
        avg_plan_length: 1.4,
        avg_execution_time_ms: 850,
      });
      renderWithProviders();

      const card = (await screen.findByText("AI Employee Activity")).closest<HTMLElement>(
        ".rounded-2xl",
      )!;
      expect(await within(card).findByText("42")).toBeInTheDocument();
      expect(within(card).getByText("Scheduler")).toBeInTheDocument();
      expect(within(card).getByText("book_appointment")).toBeInTheDocument();
      expect(within(card).getByText("25")).toBeInTheDocument();
      expect(within(card).getByText("3")).toBeInTheDocument(); // failed tool executions
      expect(within(card).getByText("5")).toBeInTheDocument(); // governance blocks
      expect(within(card).getByText("850ms")).toBeInTheDocument();
    });

    it("fails independently of the rest of the dashboard", async () => {
      vi.mocked(api.getFounderOverview).mockResolvedValue(BASE_OVERVIEW);
      vi.mocked(api.getFounderAiMetrics).mockRejectedValue(new Error("boom"));
      renderWithProviders();

      expect(await screen.findByText("Founder Operations")).toBeInTheDocument();
      expect(await screen.findByText("Couldn't load AI metrics.")).toBeInTheDocument();
    });

    it("links to the AI execution log", async () => {
      vi.mocked(api.getFounderOverview).mockResolvedValue(BASE_OVERVIEW);
      renderWithProviders();

      const link = await screen.findByRole("link", { name: /view executions/i });
      expect(link).toHaveAttribute("href", "/ops/traces");
    });
  });
});
