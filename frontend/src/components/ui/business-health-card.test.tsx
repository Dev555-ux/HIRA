import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BusinessHealthCard } from "./business-health-card";
import type { AnalyticsBusinessHealth } from "@/lib/types";

const health: AnalyticsBusinessHealth = {
  onboarding_status: "live",
  trial_ends_at: null,
  created_at: "2026-07-01T00:00:00Z",
  whatsapp: { status: "connected", display_phone_number: "+91 90000 00000" },
  knowledge_base: { published_count: 5, draft_count: 2, last_updated_at: null },
  alerts: [],
  conversations_by_status: {},
  leads_by_stage: {},
  leads_by_source: {},
  appointments_by_status: {},
};

describe("BusinessHealthCard", () => {
  it("renders WhatsApp, onboarding, and knowledge base signals", () => {
    render(<BusinessHealthCard health={health} />);
    expect(screen.getByText("WhatsApp Connected")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByText(/5 published, 2 draft/)).toBeInTheDocument();
    expect(screen.getByText("No alerts")).toBeInTheDocument();
  });

  it("omits the explanatory sentence by default (Analytics keeps its original presentation)", () => {
    render(<BusinessHealthCard health={health} />);
    expect(screen.queryByText("Excellent.")).not.toBeInTheDocument();
  });

  it("explains, rather than merely reports, when explain is on (Home only) and everything is clear", () => {
    render(<BusinessHealthCard health={health} explain />);
    expect(screen.getByText("Excellent.")).toBeInTheDocument();
    expect(screen.getByText("Your business is running normally.")).toBeInTheDocument();
  });

  it("names the real issue by reusing the backend's own alert list — never a fabricated score", () => {
    render(
      <BusinessHealthCard health={{ ...health, alerts: ["whatsapp_disconnected"] }} explain />,
    );
    expect(screen.getByText("Good.")).toBeInTheDocument();
    expect(
      screen.getByText(/the only issue today is whatsapp disconnected/i),
    ).toBeInTheDocument();
  });

  it("names every real issue when there is more than one", () => {
    render(
      <BusinessHealthCard
        health={{ ...health, alerts: ["whatsapp_disconnected", "ai_failures"] }}
        explain
      />,
    );
    expect(screen.getByText("Needs a look.")).toBeInTheDocument();
    expect(
      screen.getByText(/2 things need a look: WhatsApp disconnected, AI failures/i),
    ).toBeInTheDocument();
  });
});
