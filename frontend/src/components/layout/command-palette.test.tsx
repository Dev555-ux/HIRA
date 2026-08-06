import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRef } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { navGroups } from "@/lib/nav";
import { CommandPalette } from "./command-palette";

const push = vi.fn();
let mockPathname = "/dashboard";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => mockPathname,
}));

function renderPalette(open = true) {
  const onOpenChange = vi.fn();
  const triggerRef = createRef<Element | null>();
  const utils = render(
    <CommandPalette open={open} onOpenChange={onOpenChange} triggerRef={triggerRef} />,
  );
  return { onOpenChange, triggerRef, ...utils };
}

describe("CommandPalette", () => {
  beforeEach(() => {
    push.mockReset();
    mockPathname = "/dashboard";
  });

  it("shows the full grouped navigation when the query is empty", async () => {
    renderPalette();
    for (const group of navGroups) {
      if (group.label) {
        expect(await screen.findByText(group.label)).toBeInTheDocument();
      }
      for (const item of group.items) {
        expect(screen.getByRole("option", { name: new RegExp(item.label) })).toBeInTheDocument();
      }
    }
  });

  it("auto-focuses the search input on open", async () => {
    renderPalette();
    await waitFor(() => expect(screen.getByRole("combobox")).toHaveFocus());
  });

  it("fuzzy-filters results as the query changes", async () => {
    const user = userEvent.setup();
    renderPalette();

    await user.type(screen.getByRole("combobox"), "cust");
    expect(screen.getByRole("option", { name: /Customers/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Escalations/ })).not.toBeInTheDocument();
  });

  it("fuzzy-matches a natural substring query", async () => {
    const user = userEvent.setup();
    renderPalette();

    await user.type(screen.getByRole("combobox"), "appoint");
    expect(screen.getByRole("option", { name: /Appointments/ })).toBeInTheDocument();
  });

  it("shows an honest no-results state for a query matching nothing", async () => {
    const user = userEvent.setup();
    renderPalette();

    await user.type(screen.getByRole("combobox"), "xyzxyz");
    expect(screen.getByText(/No pages match/)).toBeInTheDocument();
    expect(screen.queryAllByRole("option")).toHaveLength(0);
  });

  it("arrow keys move the active selection, Enter navigates and closes", async () => {
    const user = userEvent.setup();
    const { onOpenChange } = renderPalette();

    await user.type(screen.getByRole("combobox"), "{ArrowDown}{ArrowDown}{Enter}");

    // Dashboard (index 0) -> Demo Chat (1) -> Business Knowledge (2) -> Enter
    expect(push).toHaveBeenCalledWith("/knowledge-base");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("mouse click on a result navigates and closes", async () => {
    const user = userEvent.setup();
    const { onOpenChange } = renderPalette();

    await user.click(screen.getByRole("option", { name: /Analytics/ }));

    expect(push).toHaveBeenCalledWith("/analytics");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("marks the current route with a visual indicator, distinct from the active-selection highlight", () => {
    mockPathname = "/customers";
    renderPalette();

    const option = screen.getByRole("option", { name: /Customers/ });
    expect(option.querySelector(".bg-primary")).toBeInTheDocument();
  });

  it("wires ARIA combobox/listbox relationships correctly", async () => {
    renderPalette();
    const combobox = screen.getByRole("combobox");
    const listbox = screen.getByRole("listbox");

    expect(combobox).toHaveAttribute("aria-controls", listbox.id);
    expect(combobox).toHaveAttribute("aria-expanded", "true");
    expect(combobox).toHaveAttribute("aria-activedescendant");
  });

  it("announces the result count for screen readers on filter", async () => {
    const user = userEvent.setup();
    renderPalette();

    await user.type(screen.getByRole("combobox"), "cust");
    expect(await screen.findByRole("status")).toHaveTextContent("1 result");
  });

  it("resets the query when reopened", () => {
    const triggerRef = createRef<Element | null>();
    const { rerender } = render(
      <CommandPalette open={false} onOpenChange={vi.fn()} triggerRef={triggerRef} />,
    );
    rerender(<CommandPalette open={true} onOpenChange={vi.fn()} triggerRef={triggerRef} />);
    expect(screen.getByRole("combobox")).toHaveValue("");
  });
});
