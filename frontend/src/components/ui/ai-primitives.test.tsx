import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ActivityDot } from "./activity-dot";
import { AISurface, ReviewSurface } from "./ai-surface";
import { ConfidenceBadge } from "./confidence-badge";
import { EvidenceCard } from "./evidence-card";
import { StatusPill } from "./status-pill";
import { ThinkingIndicator, WorkingIndicator } from "./working-indicator";

describe("AI primitives", () => {
  it("AISurface / ReviewSurface render their children", () => {
    render(
      <>
        <AISurface>drafted reply</AISurface>
        <ReviewSurface>awaiting you</ReviewSurface>
      </>,
    );
    expect(screen.getByText("drafted reply")).toBeInTheDocument();
    expect(screen.getByText("awaiting you")).toBeInTheDocument();
  });

  it("ActivityDot exposes an accessible label per state", () => {
    render(<ActivityDot state="working" label="Maya is working" />);
    expect(screen.getByRole("status", { name: "Maya is working" })).toBeInTheDocument();
  });

  it("StatusPill pairs a state with a text label (never colour alone)", () => {
    render(<StatusPill state="waiting">Waiting on customer</StatusPill>);
    expect(screen.getByText("Waiting on customer")).toBeInTheDocument();
  });

  it("ConfidenceBadge labels its level for assistive tech", () => {
    render(<ConfidenceBadge level="high" />);
    expect(screen.getByLabelText("High confidence")).toBeInTheDocument();
  });

  it("WorkingIndicator is a polite live status; ThinkingIndicator presets it", () => {
    const { rerender } = render(<WorkingIndicator state="working" label="Working…" />);
    const region = screen.getByRole("status", { name: "Working…" });
    expect(region).toHaveAttribute("aria-live", "polite");
    rerender(<ThinkingIndicator />);
    expect(screen.getByRole("status", { name: "Thinking…" })).toBeInTheDocument();
  });

  it("EvidenceCard shows its source before any snippet", () => {
    render(<EvidenceCard source="Saturday hours: 9am–2pm">from your website</EvidenceCard>);
    expect(screen.getByText("Saturday hours: 9am–2pm")).toBeInTheDocument();
    expect(screen.getByText("from your website")).toBeInTheDocument();
  });
});
