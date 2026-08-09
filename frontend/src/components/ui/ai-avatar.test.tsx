import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AIAvatar } from "./ai-avatar";

describe("AIAvatar", () => {
  it("renders initials from the name", () => {
    render(<AIAvatar name="Maya Rao" />);
    expect(screen.getByRole("img", { name: "Maya Rao" })).toHaveTextContent("MR");
  });

  it("shows a labeled activity dot when a state is given", () => {
    render(<AIAvatar name="Maya" state="working" />);
    expect(screen.getByRole("status", { name: "Maya is working" })).toBeInTheDocument();
  });
});
