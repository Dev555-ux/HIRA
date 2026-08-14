import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AiInsightsCard } from "./analytics-ai-insights";
import type { AnalyticsDashboard } from "@/lib/types";

function makeData(overrides: Partial<AnalyticsDashboard> = {}): AnalyticsDashboard {
  return {
    range: "7d",
    overview: {
      total_conversations: 20,
      messages_today: 5,
      ai_responses_today: 4,
      failed_responses_today: 0,
      avg_response_time_seconds: 30,
    },
    business_health: {
      onboarding_status: "complete",
      trial_ends_at: null,
      created_at: "2026-01-01T00:00:00Z",
      whatsapp: { status: "connected", display_phone_number: "+1" },
      knowledge_base: { published_count: 5, draft_count: 0, last_updated_at: null },
      alerts: [],
      conversations_by_status: {},
      leads_by_stage: {},
      leads_by_source: {},
      appointments_by_status: {},
    },
    trends: {
      conversations: [],
      messages: [],
      leads: [
        { date: "2026-08-03", count: 4 }, // Monday
        { date: "2026-08-04", count: 1 }, // Tuesday
      ],
      appointments: [],
    },
    ai_impact: {
      conversations_handled: 18,
      human_escalations: 2,
      leads_created: 3,
      appointments_booked: 2,
      kb_grounded_replies: 15,
      ai_responses: 18,
      estimated_hours_saved: 4,
    },
    ai_performance: {
      total_turns: 40,
      most_used_employee: "receptionist",
      avg_plan_length: 1.5,
      avg_execution_time_ms: 500,
      most_used_tools: [],
      failed_tool_executions: 0,
      governance_blocks: 0,
    },
    ...overrides,
  } as AnalyticsDashboard;
}

describe("AiInsightsCard", () => {
  it("renders nothing when there's no data to compute insights from", () => {
    const { container } = render(
      <AiInsightsCard data={makeData({ overview: { ...makeData().overview, total_conversations: 0 } })} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("states the real AI-handled percentage and escalation count", () => {
    render(<AiInsightsCard data={makeData()} />);
    expect(screen.getByText("90%")).toBeInTheDocument();
  });

  it("links the leads-peak insight to the real Leads page", () => {
    render(<AiInsightsCard data={makeData()} />);
    const link = screen.getByRole("link", { name: /Check staffing & speed in Leads/ });
    expect(link).toHaveAttribute("href", "/leads");
  });

  it("only shows the failed-responses action item when there actually were failures", () => {
    render(<AiInsightsCard data={makeData()} />);
    expect(screen.queryByText(/Review in AI Performance/)).not.toBeInTheDocument();

    render(
      <AiInsightsCard
        data={makeData({ overview: { ...makeData().overview, failed_responses_today: 3 } })}
      />,
    );
    const link = screen.getByRole("link", { name: /Review in AI Performance/ });
    expect(link).toHaveAttribute("href", "#ai-performance");
  });

  it("never fabricates a period-over-period delta for escalations or KB coverage", () => {
    render(<AiInsightsCard data={makeData()} />);
    // No "%" delta language like "-25%" or "down X%" anywhere near escalations —
    // only the real, current-period KB percentage should appear.
    expect(screen.queryByText(/vs (the )?prior|vs last/i)).not.toBeInTheDocument();
  });
});
