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
});
