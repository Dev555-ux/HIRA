import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { Message } from "@/lib/types";
import { PendingReviewContainer } from "./pending-review-container";

const mockToast = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    approveMessage: vi.fn(),
    rejectMessage: vi.fn(),
    updateDraft: vi.fn(),
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

const pendingMessage: Message = {
  id: "msg-1",
  direction: "outbound",
  body: "Yes — we're open Saturday, 9am–2pm.",
  type: "text",
  status: "pending_approval",
  created_at: "2026-07-31T10:00:00Z",
};

function renderContainer(message: Message = pendingMessage) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
  const utils = render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={mockAuth}>
        <PendingReviewContainer message={message} />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
  return { ...utils, invalidateSpy };
}

describe("PendingReviewContainer (Inbox review integration)", () => {
  beforeEach(() => {
    vi.mocked(api.approveMessage).mockReset().mockResolvedValue({ id: "msg-1", status: "sent" });
    vi.mocked(api.rejectMessage).mockReset().mockResolvedValue({ id: "msg-1", status: "rejected" });
    vi.mocked(api.updateDraft)
      .mockReset()
      .mockResolvedValue({ id: "msg-1", body: "revised", status: "pending_approval" });
    mockToast.mockReset();
  });

  it("renders the pending reply inside a ReviewReplyCard", () => {
    renderContainer();
    expect(screen.getByText(pendingMessage.body)).toBeInTheDocument();
    expect(
      screen.getByRole("group", { name: /ai reply pending your review/i }),
    ).toBeInTheDocument();
  });

  it("approve flow calls the approve endpoint and invalidates the conversation cache", async () => {
    const user = userEvent.setup();
    const { invalidateSpy } = renderContainer();

    await user.click(screen.getByRole("button", { name: /approve & send/i }));

    await waitFor(() => expect(api.approveMessage).toHaveBeenCalledWith(expect.any(Function), "msg-1"));
    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["conversations"] }),
    );
  });

  it("reject flow calls the reject endpoint", async () => {
    const user = userEvent.setup();
    renderContainer();
    await user.click(screen.getByRole("button", { name: /reject/i }));
    await waitFor(() => expect(api.rejectMessage).toHaveBeenCalledWith(expect.any(Function), "msg-1"));
  });

  it("edit flow saves the revised draft via updateDraft", async () => {
    const user = userEvent.setup();
    renderContainer();

    await user.click(screen.getByRole("button", { name: /edit/i }));
    const box = screen.getByLabelText(/edit reply/i);
    await user.clear(box);
    await user.type(box, "revised");
    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() =>
      expect(api.updateDraft).toHaveBeenCalledWith(expect.any(Function), "msg-1", "revised"),
    );
  });

  it("surfaces a destructive toast when an action fails, leaving the reply reviewable", async () => {
    vi.mocked(api.approveMessage).mockRejectedValueOnce(new Error("network"));
    const user = userEvent.setup();
    renderContainer();

    await user.click(screen.getByRole("button", { name: /approve & send/i }));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ variant: "destructive" }),
      ),
    );
    // Still awaiting review — controls remain for a retry.
    expect(screen.getByRole("button", { name: /approve & send/i })).toBeEnabled();
  });

  it("maps backend review metadata into the card (confidence, grounding, generation)", () => {
    const withReview: Message = {
      ...pendingMessage,
      review: {
        reply_id: "msg-1",
        confidence: { score: 0.9, level: "high" },
        grounding: {
          retrieved_count: 1,
          sources: [{ title: "Saturday hours", type: "kb", snippet: "9am–2pm" }],
        },
        generation_status: "complete",
      },
    };
    renderContainer(withReview);

    expect(screen.getByLabelText(/high confidence/i)).toBeInTheDocument();
    expect(screen.getByText("Saturday hours")).toBeInTheDocument();
  });

  it("renders nothing extra for a payload without review metadata (backward compatible)", () => {
    renderContainer(); // pendingMessage has no `review`
    expect(screen.queryByLabelText(/confidence/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Grounded in/i)).not.toBeInTheDocument();
    // Core review experience still renders.
    expect(screen.getByText(pendingMessage.body)).toBeInTheDocument();
  });
});
