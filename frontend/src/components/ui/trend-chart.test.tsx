import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TrendChart } from "./trend-chart";

const data = [
  { date: "2026-07-01", count: 3 },
  { date: "2026-07-02", count: 5 },
  { date: "2026-07-03", count: 1 },
];

describe("TrendChart", () => {
  it("renders an accessible summary on the chart itself", () => {
    render(<TrendChart title="Conversations over time" data={data} />);
    expect(
      screen.getByRole("img", { name: /Conversations over time: 9 total/ }),
    ).toBeInTheDocument();
  });

  it("provides a real data-table fallback, not just a visual chart", () => {
    render(<TrendChart title="Conversations over time" data={data} />);
    expect(screen.getByText("View as table")).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(table).toBeInTheDocument();
    expect(table.textContent).toContain("3");
    expect(table.textContent).toContain("5");
    expect(table.textContent).toContain("1");
  });

  it("handles an empty series honestly, without crashing", () => {
    render(<TrendChart title="Leads over time" data={[]} />);
    expect(screen.getByRole("img", { name: /Leads over time: no data/i })).toBeInTheDocument();
  });

  it("badges the latest point's real value, not a fabricated one", () => {
    render(<TrendChart title="Conversations over time" data={data} />);
    // The last point's count (1) is shown as a permanent badge, distinct
    // from the hover-only readout and the table fallback's own "1" cell —
    // visible without any interaction.
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(2);
  });

  it("shows a date axis spanning the real range", () => {
    render(<TrendChart title="Conversations over time" data={data} />);
    // Locale-agnostic: assert the axis text exists at all rather than
    // pinning an exact "month day" vs. "day month" order.
    const axisText = screen.getAllByText(/Jul/).map((el) => el.textContent).join(" ");
    expect(axisText).toMatch(/1/);
    expect(axisText).toMatch(/3/);
  });
});
