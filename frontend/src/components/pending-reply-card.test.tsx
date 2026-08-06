import { createRef } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { PendingReply } from "@/lib/types";
import { PendingReplyCard, type PendingReplyCardHandle } from "./pending-reply-card";

const mockToast = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
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

const reply: PendingReply = {
  id: "msg-1",
  conversation_id: "conv-1",
  body: "Yes — we're open Saturday, 9am–2pm.",
  created_at: "2026-07-31T10:00:00Z",
  customer: { id: "cust-1", display_name: "Jordan Lee", wa_phone: "+15551230000" },
  conversation_preview: "Are you open Saturday?",
};

function renderCard(
  props: Partial<{ reply: PendingReply; active: boolean }> = {},
  ref?: React.Ref<PendingReplyCardHandle>,
) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={mockAuth}>
        <PendingReplyCard ref={ref} reply={props.reply ?? reply} active={props.active} />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("PendingReplyCard", () => {
  beforeEach(() => {
    vi.mocked(api.approveMessage).mockReset().mockResolvedValue({ id: "msg-1", status: "sent" });
    vi.mocked(api.rejectMessage).mockReset().mockResolvedValue({ id: "msg-1", status: "rejected" });
    vi.mocked(api.updateDraft)
      .mockReset()
      .mockResolvedValue({ id: "msg-1", body: "revised", status: "pending_approval" });
    vi.mocked(api.regenerateMessage)
      .mockReset()
      .mockResolvedValue({ id: "msg-1", body: "regenerated", status: "pending_approval" });
    vi.mocked(api.escalateMessage).mockReset().mockResolvedValue({
      id: "msg-1",
      status: "escalated",
      escalation: {
        id: "esc-1",
        conversation_id: "conv-1",
        reason: "customer_request",
        status: "open",
        created_at: "2026-07-31T10:00:00Z",
      },
    });
    mockToast.mockReset();
  });

  it("renders on the AI-identity review surface with a StatusPill, not a raw Badge", () => {
    renderCard();
    expect(screen.getByRole("group", { name: /pending reply for jordan lee/i })).toBeInTheDocument();
    expect(screen.getByText("Pending approval")).toBeInTheDocument();
    expect(screen.getByText(reply.body)).toBeInTheDocument();
  });

  it("renders the customer, conversation preview, and draft with all actions", () => {
    renderCard();
    expect(screen.getByText("Jordan Lee")).toBeInTheDocument();
    expect(screen.getByText("Are you open Saturday?")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /ai-drafted reply/i })).toHaveValue(reply.body);
    expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /regenerate/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^reject$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /escalate/i })).toBeInTheDocument();
  });

  it("falls back to the phone number when there's no display name", () => {
    renderCard({
      reply: { ...reply, customer: { id: "cust-1", display_name: null, wa_phone: "+15551230000" } },
    });
    expect(screen.getByText("+15551230000")).toBeInTheDocument();
  });

  it("shows a dirty indicator and updated character count while editing", async () => {
    const user = userEvent.setup();
    renderCard({ reply: { ...reply, body: "Hi" } });

    expect(screen.getByText("AI draft")).toBeInTheDocument();
    expect(screen.getByText("2 / 4096")).toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: /ai-drafted reply/i }), " there");

    expect(screen.getByText("Edited — not yet saved")).toBeInTheDocument();
    expect(screen.getByText("8 / 4096")).toBeInTheDocument();
  });

  it("approves directly without saving when the draft is unchanged", async () => {
    const user = userEvent.setup();
    renderCard();

    await user.click(screen.getByRole("button", { name: /approve/i }));
    await waitFor(() =>
      expect(api.approveMessage).toHaveBeenCalledWith(expect.any(Function), "msg-1"),
    );
    expect(api.updateDraft).not.toHaveBeenCalled();
  });

  it("rejects directly when there are no unsaved edits", async () => {
    const user = userEvent.setup();
    renderCard();

    await user.click(screen.getByRole("button", { name: /^reject$/i }));
    await waitFor(() =>
      expect(api.rejectMessage).toHaveBeenCalledWith(expect.any(Function), "msg-1"),
    );
    expect(screen.queryByText(/discard your edits/i)).not.toBeInTheDocument();
  });

  it("warns before discarding unsaved edits when regenerating", async () => {
    const user = userEvent.setup();
    renderCard({ reply: { ...reply, body: "Hi" } });

    await user.type(screen.getByRole("textbox", { name: /ai-drafted reply/i }), " there");
    await user.click(screen.getByRole("button", { name: /regenerate/i }));

    expect(await screen.findByText("Discard your edits?")).toBeInTheDocument();
    expect(api.regenerateMessage).not.toHaveBeenCalled();
  });

  it("disables Approve & send while the draft is empty", async () => {
    const user = userEvent.setup();
    renderCard({ reply: { ...reply, body: "Hi" } });

    await user.clear(screen.getByRole("textbox", { name: /ai-drafted reply/i }));
    expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled();
  });

  it("approve flow: dirty draft saves first, then sends", async () => {
    const user = userEvent.setup();
    renderCard();

    const box = screen.getByLabelText(/AI-drafted reply/i);
    await user.clear(box);
    await user.type(box, "Updated reply text");
    await user.click(screen.getByRole("button", { name: /approve & send/i }));

    await waitFor(() =>
      expect(api.updateDraft).toHaveBeenCalledWith(expect.any(Function), "msg-1", "Updated reply text"),
    );
    await waitFor(() =>
      expect(api.approveMessage).toHaveBeenCalledWith(expect.any(Function), "msg-1"),
    );
  });

  it("regenerate on a clean draft calls the endpoint directly, no confirm dialog", async () => {
    const user = userEvent.setup();
    renderCard();

    await user.click(screen.getByRole("button", { name: /regenerate/i }));
    await waitFor(() =>
      expect(api.regenerateMessage).toHaveBeenCalledWith(expect.any(Function), "msg-1"),
    );
    expect(screen.queryByText("Discard your edits?")).not.toBeInTheDocument();
  });

  it("reject on a dirty draft shows the discard-confirmation dialog first", async () => {
    const user = userEvent.setup();
    renderCard();

    const box = screen.getByLabelText(/AI-drafted reply/i);
    await user.type(box, " edited");
    await user.click(screen.getByRole("button", { name: /^reject$/i }));

    expect(await screen.findByText("Discard your edits?")).toBeInTheDocument();
    expect(api.rejectMessage).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /discard & reject/i }));
    await waitFor(() => expect(api.rejectMessage).toHaveBeenCalledWith(expect.any(Function), "msg-1"));
  });

  it("escalate flow calls the escalate endpoint", async () => {
    const user = userEvent.setup();
    renderCard();

    await user.click(screen.getByRole("button", { name: /escalate/i }));
    await waitFor(() =>
      expect(api.escalateMessage).toHaveBeenCalledWith(expect.any(Function), "msg-1"),
    );
  });

  it("shows a destructive toast on failure, leaving the reply reviewable", async () => {
    vi.mocked(api.approveMessage).mockRejectedValueOnce(new Error("network"));
    const user = userEvent.setup();
    renderCard();

    await user.click(screen.getByRole("button", { name: /approve & send/i }));
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ variant: "destructive" })),
    );
    expect(screen.getByRole("button", { name: /approve & send/i })).toBeEnabled();
  });

  it("shows the active ring only when active", () => {
    const { container, rerender } = renderCard({ active: false });
    const surface = container.querySelector('[role="group"]');
    expect(surface?.className).not.toMatch(/ring-2/);

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    rerender(
      <QueryClientProvider client={qc}>
        <AuthContext.Provider value={mockAuth}>
          <PendingReplyCard reply={reply} active />
        </AuthContext.Provider>
      </QueryClientProvider>,
    );
    expect(container.querySelector('[role="group"]')?.className).toMatch(/ring-2/);
  });

  describe("imperative handle (M12 keyboard queue)", () => {
    it("approve() triggers the same approve flow as the button", async () => {
      const ref = createRef<PendingReplyCardHandle>();
      renderCard({}, ref);

      ref.current?.approve();
      await waitFor(() =>
        expect(api.approveMessage).toHaveBeenCalledWith(expect.any(Function), "msg-1"),
      );
    });

    it("reject() on a clean draft rejects directly", async () => {
      const ref = createRef<PendingReplyCardHandle>();
      renderCard({}, ref);

      ref.current?.reject();
      await waitFor(() =>
        expect(api.rejectMessage).toHaveBeenCalledWith(expect.any(Function), "msg-1"),
      );
    });

    it("focusEditor() moves focus into the draft textarea", () => {
      const ref = createRef<PendingReplyCardHandle>();
      renderCard({}, ref);

      ref.current?.focusEditor();
      expect(screen.getByLabelText(/AI-drafted reply/i)).toHaveFocus();
    });
  });
});
