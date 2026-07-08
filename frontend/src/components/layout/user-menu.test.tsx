import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import { UserMenu } from "./user-menu";

function renderWithAuth(overrides: Partial<AuthContextValue> = {}) {
  const auth: AuthContextValue = {
    getToken: async () => "test-token",
    user: { name: "Dev User", email: "dev@hira.local", imageUrl: null },
    isLoaded: true,
    mocked: false,
    signOut: vi.fn(),
    openProfile: vi.fn(),
    ...overrides,
  };
  render(
    <AuthContext.Provider value={auth}>
      <UserMenu />
    </AuthContext.Provider>,
  );
  return auth;
}

describe("UserMenu", () => {
  it("calls signOut when Sign out is clicked", async () => {
    const user = userEvent.setup();
    const signOut = vi.fn();
    renderWithAuth({ signOut });

    await user.click(screen.getByRole("button", { name: /open user menu/i }));
    await user.click(await screen.findByText("Sign out"));

    expect(signOut).toHaveBeenCalledTimes(1);
  });

  it("calls openProfile when Profile is clicked", async () => {
    const user = userEvent.setup();
    const openProfile = vi.fn();
    renderWithAuth({ openProfile });

    await user.click(screen.getByRole("button", { name: /open user menu/i }));
    await user.click(await screen.findByText("Profile"));

    expect(openProfile).toHaveBeenCalledTimes(1);
  });

  it("labels sign out for mock auth", async () => {
    const user = userEvent.setup();
    renderWithAuth({ mocked: true });

    await user.click(screen.getByRole("button", { name: /open user menu/i }));

    expect(await screen.findByText("Sign out (mock)")).toBeInTheDocument();
  });
});
