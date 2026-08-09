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
});
