import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { PendingReply } from "@/lib/types";
import PendingPage from "./page";

const mockToast = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    listPending: vi.fn(),
    approveMessage: vi.fn(),
    rejectMessage: vi.fn(),
    updateDraft: vi.fn(),
    regenerateMessage: vi.fn(),
    escalateMessage: vi.fn(),
  },
}));

import { api } from "@/lib/api";

const mockAuth: AuthContextValue = {
  getToken: async () => "test-token",
  user: { name: "Dev", email: "dev@hira.local", imageUrl: null },
  isLoaded: true,
  mocked: false,
  signOut: vi.fn(),
  openProfile: vi.fn(),
};

function reply(i: number): PendingReply {
  return {
    id: `msg-${i}`,
    conversation_id: `conv-${i}`,
    body: `Reply body ${i}`,
    created_at: "2026-07-31T10:00:00Z",
    customer: { id: `cust-${i}`, display_name: `Customer ${i}`, wa_phone: "+15551230000" },
    conversation_preview: null,
  };
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={mockAuth}>
        <PendingPage />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("PendingPage", () => {
  beforeEach(() => {
    vi.mocked(api.listPending).mockReset().mockResolvedValue([reply(0), reply(1), reply(2)]);
    vi.mocked(api.approveMessage).mockReset().mockResolvedValue({ id: "msg-0", status: "sent" });
    vi.mocked(api.rejectMessage).mockReset().mockResolvedValue({ id: "msg-0", status: "rejected" });
    vi.mocked(api.updateDraft)
      .mockReset()
      .mockResolvedValue({ id: "msg-0", body: "x", status: "pending_approval" });
    vi.mocked(api.regenerateMessage)
      .mockReset()
      .mockResolvedValue({ id: "msg-0", body: "x", status: "pending_approval" });
    vi.mocked(api.escalateMessage).mockReset().mockResolvedValue({
      id: "msg-0",
      status: "escalated",
      escalation: {
        id: "esc-0",
        conversation_id: "conv-0",
        reason: "customer_request",
        status: "open",
        created_at: "2026-07-31T10:00:00Z",
      },
    });
    mockToast.mockReset();
  });

  it("shows the keyboard shortcut hint once replies are loaded", async () => {
    renderPage();
    expect(await screen.findByText(/to move/i)).toBeInTheDocument();
  });

  it("shows a reassuring empty state with no shortcut hint when nothing is pending", async () => {
    vi.mocked(api.listPending).mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("All caught up")).toBeInTheDocument();
    expect(screen.queryByText(/to move/i)).not.toBeInTheDocument();
  });

  it("shows a retry action when loading fails", async () => {
    vi.mocked(api.listPending).mockRejectedValue(new Error("network down"));
    renderPage();
    expect(await screen.findByText("Couldn't load pending replies")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("optimistically removes a card from the list once approved", async () => {
    const user = userEvent.setup();
    // Background refetch (triggered by the mutation's onSettled) should see
    // the reply gone server-side too, so the optimistic removal never reverts.
    vi.mocked(api.listPending)
      .mockResolvedValueOnce([reply(0), reply(1)])
      .mockResolvedValue([reply(1)]);
    renderPage();

    await screen.findByText("Customer 0");
    await user.click(screen.getAllByRole("button", { name: /approve/i })[0]);

    await waitFor(() => expect(screen.queryByText("Customer 0")).not.toBeInTheDocument());
    expect(screen.getByText("Customer 1")).toBeInTheDocument();
  });

  it("regenerates the draft and replaces the textarea contents", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listPending).mockResolvedValue([reply(0)]);
    vi.mocked(api.regenerateMessage).mockResolvedValue({
      id: "msg-0",
      body: "A brand new AI draft.",
      status: "pending_approval",
    });
    renderPage();

    await screen.findByText("Customer 0");
    await user.click(screen.getByRole("button", { name: /regenerate/i }));

    await waitFor(() =>
      expect(api.regenerateMessage).toHaveBeenCalledWith(expect.any(Function), "msg-0"),
    );
    expect(await screen.findByDisplayValue("A brand new AI draft.")).toBeInTheDocument();
  });

  it("removes a card from the list once escalated", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listPending)
      .mockResolvedValueOnce([reply(0), reply(1)])
      .mockResolvedValue([reply(1)]);
    renderPage();

    await screen.findByText("Customer 0");
    await user.click(screen.getAllByRole("button", { name: /escalate/i })[0]);

    await waitFor(() => expect(screen.queryByText("Customer 0")).not.toBeInTheDocument());
    expect(screen.getByText("Customer 1")).toBeInTheDocument();
  });

  it("j/k move the active card without hijacking typing in a textarea", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Customer 0");

    // Card 0 starts active.
    const groups = () => screen.getAllByRole("group");
    expect(groups()[0].className).toMatch(/ring-2/);

    await user.keyboard("j");
    expect(groups()[1].className).toMatch(/ring-2/);
    expect(groups()[0].className).not.toMatch(/ring-2/);

    await user.keyboard("k");
    expect(groups()[0].className).toMatch(/ring-2/);

    // Typing "j" inside a draft textarea must not move the active card.
    const boxes = screen.getAllByRole("textbox") as HTMLTextAreaElement[];
    await user.click(boxes[0]);
    await user.keyboard("j");
    expect(boxes[0].value).toContain("j");
    expect(groups()[0].className).toMatch(/ring-2/);
  });

  it("Enter approves the active card", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Customer 0");

    await user.keyboard("{Enter}");
    await waitFor(() =>
      expect(api.approveMessage).toHaveBeenCalledWith(expect.any(Function), "msg-0"),
    );
  });

  it("x rejects the active card", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Customer 0");

    await user.keyboard("x");
    await waitFor(() =>
      expect(api.rejectMessage).toHaveBeenCalledWith(expect.any(Function), "msg-0"),
    );
  });

  it("e focuses the active card's editor", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Customer 0");

    await user.keyboard("e");
    const boxes = screen.getAllByLabelText(/AI-drafted reply/i);
    expect(boxes[0]).toHaveFocus();
  });
});
