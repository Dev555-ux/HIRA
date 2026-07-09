import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/toast";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { PendingReply } from "@/lib/types";
import PendingPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    listPending: vi.fn(),
    approveMessage: vi.fn(),
    updateDraft: vi.fn(),
    rejectMessage: vi.fn(),
    regenerateMessage: vi.fn(),
    escalateMessage: vi.fn(),
  },
}));

import { api } from "@/lib/api";

const mockAuth: AuthContextValue = {
  getToken: async () => "test-token",
  user: null,
  isLoaded: true,
  mocked: true,
  signOut: vi.fn(),
  openProfile: vi.fn(),
};

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={mockAuth}>
        <ToastProvider>{ui}</ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

function reply(overrides: Partial<PendingReply> = {}): PendingReply {
  return {
    id: "1",
    conversation_id: "c1",
    body: "We are open 9am to 5pm.",
    created_at: new Date().toISOString(),
    customer: { id: "cust1", display_name: "Alex Rivera", wa_phone: "+15551230000" },
    conversation_preview: "are you open today?",
    ...overrides,
  };
}

describe("PendingPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the empty state when there are no pending replies", async () => {
    vi.mocked(api.listPending).mockResolvedValue([]);
    renderWithProviders(<PendingPage />);
    await waitFor(() => expect(screen.getByText("All caught up")).toBeInTheDocument());
  });

  it("renders the customer, conversation preview, and draft with all actions", async () => {
    vi.mocked(api.listPending).mockResolvedValue([reply()]);
    renderWithProviders(<PendingPage />);

    expect(await screen.findByText("Alex Rivera")).toBeInTheDocument();
    expect(screen.getByText("are you open today?")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /ai-drafted reply/i })).toHaveValue(
      "We are open 9am to 5pm.",
    );
    expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /regenerate/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /escalate/i })).toBeInTheDocument();
  });

  it("falls back to the phone number when there's no display name", async () => {
    vi.mocked(api.listPending).mockResolvedValue([
      reply({ customer: { id: "cust1", display_name: null, wa_phone: "+15551230000" } }),
    ]);
    renderWithProviders(<PendingPage />);
    expect(await screen.findByText("+15551230000")).toBeInTheDocument();
  });

  it("shows a dirty indicator and updated character count while editing", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listPending).mockResolvedValue([reply({ body: "Hi" })]);
    renderWithProviders(<PendingPage />);

    const textarea = await screen.findByRole("textbox", { name: /ai-drafted reply/i });
    expect(screen.getByText("AI draft")).toBeInTheDocument();
    expect(screen.getByText("2 / 4096")).toBeInTheDocument();

    await user.type(textarea, " there");

    expect(screen.getByText("Edited — not yet saved")).toBeInTheDocument();
    expect(screen.getByText("8 / 4096")).toBeInTheDocument();
  });

  it("saves the edited draft then approves on Approve & send", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listPending).mockResolvedValue([reply({ id: "1", body: "Hi" })]);
    vi.mocked(api.updateDraft).mockResolvedValue({ id: "1", body: "Hi there", status: "pending_approval" });
    vi.mocked(api.approveMessage).mockResolvedValue({ id: "1", status: "sent" });
    renderWithProviders(<PendingPage />);

    const textarea = await screen.findByRole("textbox", { name: /ai-drafted reply/i });
    await user.type(textarea, " there");
    await user.click(screen.getByRole("button", { name: /approve/i }));

    await waitFor(() => expect(api.updateDraft).toHaveBeenCalledWith(expect.any(Function), "1", "Hi there"));
    expect(api.approveMessage).toHaveBeenCalledWith(expect.any(Function), "1");
  });

  it("approves directly without editing when the draft is unchanged", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listPending).mockResolvedValue([reply({ id: "1" })]);
    vi.mocked(api.approveMessage).mockResolvedValue({ id: "1", status: "sent" });
    renderWithProviders(<PendingPage />);

    await user.click(await screen.findByRole("button", { name: /approve/i }));

    await waitFor(() => expect(api.approveMessage).toHaveBeenCalledWith(expect.any(Function), "1"));
    expect(api.updateDraft).not.toHaveBeenCalled();
  });

  it("optimistically removes the card once approved", async () => {
    const user = userEvent.setup();
    // Background refetch (triggered by the mutation's onSettled) should see the
    // reply gone server-side too, so the optimistic removal never reverts.
    vi.mocked(api.listPending)
      .mockResolvedValueOnce([reply({ id: "1" })])
      .mockResolvedValue([]);
    vi.mocked(api.approveMessage).mockResolvedValue({ id: "1", status: "sent" });
    renderWithProviders(<PendingPage />);

    await user.click(await screen.findByRole("button", { name: /approve/i }));

    await waitFor(() => expect(screen.queryByText("Alex Rivera")).not.toBeInTheDocument());
  });

  it("rejects directly when there are no unsaved edits", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listPending).mockResolvedValue([reply({ id: "1" })]);
    vi.mocked(api.rejectMessage).mockResolvedValue({ id: "1", status: "rejected" });
    renderWithProviders(<PendingPage />);

    await user.click(await screen.findByRole("button", { name: /reject/i }));

    await waitFor(() => expect(api.rejectMessage).toHaveBeenCalledWith(expect.any(Function), "1"));
    expect(screen.queryByText(/discard your edits/i)).not.toBeInTheDocument();
  });

  it("warns before discarding unsaved edits when rejecting", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listPending).mockResolvedValue([reply({ id: "1", body: "Hi" })]);
    vi.mocked(api.rejectMessage).mockResolvedValue({ id: "1", status: "rejected" });
    renderWithProviders(<PendingPage />);

    const textarea = await screen.findByRole("textbox", { name: /ai-drafted reply/i });
    await user.type(textarea, " there");
    await user.click(screen.getByRole("button", { name: /^reject$/i }));

    expect(await screen.findByText("Discard your edits?")).toBeInTheDocument();
    expect(api.rejectMessage).not.toHaveBeenCalled();

    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /discard & reject/i }));

    await waitFor(() => expect(api.rejectMessage).toHaveBeenCalledWith(expect.any(Function), "1"));
  });

  it("regenerates the draft and replaces the textarea contents", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listPending).mockResolvedValue([reply({ id: "1", body: "Hi" })]);
    vi.mocked(api.regenerateMessage).mockResolvedValue({
      id: "1",
      body: "A brand new AI draft.",
      status: "pending_approval",
    });
    renderWithProviders(<PendingPage />);

    await user.click(await screen.findByRole("button", { name: /regenerate/i }));

    await waitFor(() => expect(api.regenerateMessage).toHaveBeenCalledWith(expect.any(Function), "1"));
    expect(await screen.findByDisplayValue("A brand new AI draft.")).toBeInTheDocument();
  });

  it("warns before discarding unsaved edits when regenerating", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listPending).mockResolvedValue([reply({ id: "1", body: "Hi" })]);
    vi.mocked(api.regenerateMessage).mockResolvedValue({
      id: "1",
      body: "regenerated",
      status: "pending_approval",
    });
    renderWithProviders(<PendingPage />);

    const textarea = await screen.findByRole("textbox", { name: /ai-drafted reply/i });
    await user.type(textarea, " there");
    await user.click(screen.getByRole("button", { name: /regenerate/i }));

    expect(await screen.findByText("Discard your edits?")).toBeInTheDocument();
    expect(api.regenerateMessage).not.toHaveBeenCalled();
  });

  it("escalates and removes the card from the queue", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listPending)
      .mockResolvedValueOnce([reply({ id: "1" })])
      .mockResolvedValue([]);
    vi.mocked(api.escalateMessage).mockResolvedValue({
      id: "1",
      status: "escalated",
      escalation: { id: "e1", conversation_id: "c1", reason: "other", status: "open", created_at: new Date().toISOString() },
    });
    renderWithProviders(<PendingPage />);

    await user.click(await screen.findByRole("button", { name: /escalate/i }));

    await waitFor(() => expect(api.escalateMessage).toHaveBeenCalledWith(expect.any(Function), "1"));
    await waitFor(() => expect(screen.queryByText("Alex Rivera")).not.toBeInTheDocument());
  });

  it("shows an error toast and keeps the card when approve fails", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listPending).mockResolvedValue([reply({ id: "1" })]);
    vi.mocked(api.approveMessage).mockRejectedValue(new Error("network down"));
    renderWithProviders(<PendingPage />);

    await user.click(await screen.findByRole("button", { name: /approve/i }));

    expect(await screen.findByText("Couldn't send reply")).toBeInTheDocument();
    expect(screen.getByText("Alex Rivera")).toBeInTheDocument();
  });

  it("disables Approve & send while empty", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listPending).mockResolvedValue([reply({ id: "1", body: "Hi" })]);
    renderWithProviders(<PendingPage />);

    const textarea = await screen.findByRole("textbox", { name: /ai-drafted reply/i });
    await user.clear(textarea);

    expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled();
  });

  it("shows a retry action when loading fails", async () => {
    vi.mocked(api.listPending).mockRejectedValue(new Error("network down"));
    renderWithProviders(<PendingPage />);
    expect(await screen.findByText("Couldn't load pending replies")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
