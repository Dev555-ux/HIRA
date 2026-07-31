import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { MouseEvent, ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

// Real next/link navigation isn't meaningful under jsdom (no app-router
// context is mounted in these tests) — swap it for a plain anchor so we can
// verify our own onClick wiring (closing the mobile drawer) without jsdom
// attempting real navigation.
vi.mock("next/link", () => ({
  default: ({
    href,
    onClick,
    children,
    ...props
  }: {
    href: string;
    onClick?: (e: MouseEvent) => void;
    children: ReactNode;
  }) => (
    <a
      href={href}
      onClick={(e: MouseEvent) => {
        onClick?.(e);
        e.preventDefault();
      }}
      {...props}
    >
      {children}
    </a>
  ),
}));

const mockAuth: AuthContextValue = {
  getToken: async () => "test-token",
  user: { name: "Dev User", email: "dev@hira.local", imageUrl: null },
  isLoaded: true,
  mocked: false,
  signOut: vi.fn(),
  openProfile: vi.fn(),
};

function renderShell() {
  return render(
    <AuthContext.Provider value={mockAuth}>
      <AppShell>
        <p>page content</p>
      </AppShell>
    </AuthContext.Provider>,
  );
}

describe("AppShell — mobile navigation", () => {
  it("is closed by default", () => {
    renderShell();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens the drawer from the hamburger button", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole("button", { name: /open navigation/i }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("closes the drawer when a nav link is clicked", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole("button", { name: /open navigation/i }));
    const dialog = await screen.findByRole("dialog");

    await user.click(within(dialog).getByRole("link", { name: /dashboard/i }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes the drawer via its own close button", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole("button", { name: /open navigation/i }));
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /close navigation/i }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("AppShell — desktop sidebar", () => {
  it("renders a skip-to-content link targeting the main region", () => {
    renderShell();
    const skip = screen.getByRole("link", { name: /skip to main content/i });
    expect(skip).toHaveAttribute("href", "#main-content");
  });

  it("collapses and expands via the toggle, updating aria-expanded", async () => {
    const user = userEvent.setup();
    renderShell();

    const toggle = screen.getByRole("button", { name: /collapse sidebar/i });
    expect(toggle).toHaveAttribute("aria-expanded", "true");

    await user.click(toggle);

    const expandToggle = screen.getByRole("button", { name: /expand sidebar/i });
    expect(expandToggle).toHaveAttribute("aria-expanded", "false");
  });

  it("keeps nav links accessible by name even when collapsed", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole("button", { name: /collapse sidebar/i }));

    // Label is visually hidden (sr-only) but stays the link's accessible name.
    expect(screen.getAllByRole("link", { name: /dashboard/i }).length).toBeGreaterThan(0);
  });
});
