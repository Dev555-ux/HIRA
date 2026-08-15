import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ExecutiveSummary } from "./analytics-executive-summary";
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
      conversations: [1, 2, 3, 4, 5, 6, 7].map((count, i) => ({
        date: `2026-08-0${i + 1}`,
        count,
      })),
      messages: [],
      leads: [],
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

describe("ExecutiveSummary", () => {
  it("shows the real conversation count and AI-handled percentage", () => {
    render(<ExecutiveSummary data={makeData()} />);
    expect(screen.getByText("20", { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/AI handled 90% without a human/)).toBeInTheDocument();
  });

  it("shows all-clear when there are no alerts", () => {
    render(<ExecutiveSummary data={makeData()} />);
    expect(screen.getByText(/All clear/)).toBeInTheDocument();
  });

  it("links each real alert to where it gets fixed", () => {
    render(
      <ExecutiveSummary
        data={makeData({
          business_health: {
            ...makeData().business_health,
            alerts: ["missing_knowledge_base"],
          },
        })}
      />,
    );
    const link = screen.getByRole("link", { name: /No Knowledge Base/ });
    expect(link).toHaveAttribute("href", "/knowledge-base");
  });

  it("shows the real estimated hours saved, not a fabricated one", () => {
    render(<ExecutiveSummary data={makeData()} />);
    expect(screen.getByText("≈4h")).toBeInTheDocument();
  });

  it("never claims a delta it can't back with real data", () => {
    // Only 7 trend points — periodTrendPct requires at least 4, so this one
    // legitimately does compute; verify a too-short series shows no delta.
    render(
      <ExecutiveSummary
        data={makeData({
          trends: { conversations: [{ date: "2026-08-01", count: 5 }], messages: [], leads: [], appointments: [] },
        })}
      />,
    );
    expect(screen.queryByText(/↑|↓/)).not.toBeInTheDocument();
  });
});
