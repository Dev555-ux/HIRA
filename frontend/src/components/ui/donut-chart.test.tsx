import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DonutChart } from "./donut-chart";

const segments = [
  { key: "booked", label: "Booked", value: 14, state: "success" as const },
  { key: "rescheduled", label: "Rescheduled", value: 2, state: "waiting" as const },
  { key: "cancelled", label: "Cancelled", value: 3, state: "error" as const },
];

describe("DonutChart", () => {
  it("renders an accessible summary with per-segment percentages", () => {
    render(<DonutChart title="Appointments by status" segments={segments} />);
    expect(
      screen.getByRole("img", { name: /Appointments by status: Booked 14 \(74%\)/ }),
    ).toBeInTheDocument();
  });

  it("provides a real data-table fallback, not just a visual chart", () => {
    render(<DonutChart title="Appointments by status" segments={segments} />);
    expect(screen.getByText("View as table")).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(table.textContent).toContain("Booked");
    expect(table.textContent).toContain("14");
  });

  it("shows the real total in the center, not a fabricated one", () => {
    render(<DonutChart title="Appointments by status" segments={segments} />);
    expect(screen.getByText("19")).toBeInTheDocument();
  });

  it("handles an empty series honestly, without crashing", () => {
    render(<DonutChart title="Leads by status" segments={[]} />);
    expect(screen.getByRole("img", { name: /Leads by status: no data/i })).toBeInTheDocument();
  });
});
