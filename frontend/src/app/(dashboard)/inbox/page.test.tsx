import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/toast";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { Conversation, Message } from "@/lib/types";
import InboxPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    listConversations: vi.fn(),
    getConversation: vi.fn(),
    listMessages: vi.fn(),
  },
}));

const mockSearchParams = vi.fn(() => new URLSearchParams());
vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams(),
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

function conversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: "conv-1",
    status: "active",
    customer: { id: "cust-1", display_name: "Alice Smith", wa_phone: "+15551230000" },
    last_message_at: new Date().toISOString(),
    preview: "Are you open today?",
    has_pending_approval: false,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function message(overrides: Partial<Message> = {}): Message {
  return {
    id: "msg-1",
    direction: "inbound",
    body: "Are you open today?",
    type: "text",
    status: "received",
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

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

describe("InboxPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams.mockReturnValue(new URLSearchParams());
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0 },
    });
  });

  it("shows the empty state when there are no conversations", async () => {
    renderWithProviders(<InboxPage />);
    expect(await screen.findByText("No conversations yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Try Demo Chat" })).toHaveAttribute(
      "href",
      "/demo",
    );
  });

  it("shows an error state with retry when the list fails to load", async () => {
    vi.mocked(api.listConversations).mockReset();
    vi.mocked(api.listConversations).mockRejectedValue(new Error("Network error"));

    renderWithProviders(<InboxPage />);

    expect(await screen.findByText("Couldn't load conversations")).toBeInTheDocument();
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });

  it("renders a conversation with its status and pending badges", async () => {
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [conversation({ has_pending_approval: true })],
      meta: { total: 1, limit: 20, offset: 0 },
    });

    renderWithProviders(<InboxPage />);

    expect(await screen.findByText("Alice Smith")).toBeInTheDocument();
    expect(screen.getByText("Are you open today?")).toBeInTheDocument();
    // Both "Open" and "Pending" also label filter chips — the badge is the
    // second match in each case.
    expect(screen.getAllByText("Open")).toHaveLength(2);
    expect(screen.getAllByText("Pending")).toHaveLength(2);
    expect(screen.getByText("WhatsApp")).toBeInTheDocument();
  });

  it("debounces search input, then calls the API with the search term", async () => {
    const user = userEvent.setup();
    renderWithProviders(<InboxPage />);
    await screen.findByText("No conversations yet");

    await user.type(screen.getByPlaceholderText(/search conversations/i), "alice");

    await waitFor(
      () =>
        expect(api.listConversations).toHaveBeenCalledWith(
          expect.any(Function),
          expect.objectContaining({ search: "alice" }),
        ),
      { timeout: 1000 },
    );
  });

  it("calls the API with the selected status filter", async () => {
    const user = userEvent.setup();
    renderWithProviders(<InboxPage />);
    await screen.findByText("No conversations yet");

    await user.click(screen.getByRole("button", { name: "Pending" }));

    await waitFor(() =>
      expect(api.listConversations).toHaveBeenCalledWith(
        expect.any(Function),
        expect.objectContaining({ status: "pending" }),
      ),
    );
  });

  it("loads and displays the message thread when a conversation is selected", async () => {
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [conversation()],
      meta: { total: 1, limit: 20, offset: 0 },
    });
    vi.mocked(api.getConversation).mockResolvedValue(conversation());
    vi.mocked(api.listMessages).mockResolvedValue({
      data: [
        message({ id: "m1", direction: "inbound", body: "Are you open today?" }),
        message({
          id: "m2",
          direction: "outbound",
          body: "Yes, 9-5!",
          status: "pending_approval",
        }),
      ],
      meta: { total: 2, limit: 50, offset: 0 },
    });
    const user = userEvent.setup();

    renderWithProviders(<InboxPage />);
    await user.click(await screen.findByText("Alice Smith"));

    expect(await screen.findByText("Yes, 9-5!")).toBeInTheDocument();
    // PR5: a pending_approval AI reply now renders the review experience
    // (ReviewReplyCard) in the thread, not a plain bubble + "Pending approval"
    // badge. Other message types are unchanged (see the next test).
    expect(screen.getByRole("group", { name: /ai reply pending your review/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve & send/i })).toBeInTheDocument();
    expect(api.getConversation).toHaveBeenCalledWith(expect.any(Function), "conv-1");
    expect(api.listMessages).toHaveBeenCalledWith(expect.any(Function), "conv-1");
    // WhatsApp badge appears in both the list row and the detail header.
    expect(screen.getAllByText("WhatsApp")).toHaveLength(2);
  });

  it("shows a badge for escalated, rejected, and sending outbound messages, not a bare bubble", async () => {
    // Sprint 77, Objective D: Message["status"] had no badge mapping for
    // these three, so the honest-fallback/escalation messages Objective A/D
    // now create rendered with no visible signal anything went wrong.
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [conversation()],
      meta: { total: 1, limit: 20, offset: 0 },
    });
    vi.mocked(api.getConversation).mockResolvedValue(conversation());
    vi.mocked(api.listMessages).mockResolvedValue({
      data: [
        message({ id: "m1", direction: "outbound", body: "Flagged for follow-up.", status: "escalated" }),
        message({ id: "m2", direction: "outbound", body: "Rejected draft.", status: "rejected" }),
        message({ id: "m3", direction: "outbound", body: "Sending now…", status: "sending" }),
      ],
      meta: { total: 3, limit: 50, offset: 0 },
    });
    const user = userEvent.setup();

    renderWithProviders(<InboxPage />);
    await user.click(await screen.findByText("Alice Smith"));

    await screen.findByText("Flagged for follow-up.");
    expect(screen.getByText("Escalated")).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();
    expect(screen.getByText("Sending…")).toBeInTheDocument();
  });

  it("returns to the conversation list from the back button", async () => {
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [conversation()],
      meta: { total: 1, limit: 20, offset: 0 },
    });
    vi.mocked(api.getConversation).mockResolvedValue(conversation());
    vi.mocked(api.listMessages).mockResolvedValue({
      data: [message()],
      meta: { total: 1, limit: 50, offset: 0 },
    });
    const user = userEvent.setup();

    renderWithProviders(<InboxPage />);
    await user.click(await screen.findByText("Alice Smith"));
    await screen.findByRole("button", { name: /back to conversations/i });

    await user.click(screen.getByRole("button", { name: /back to conversations/i }));

    expect(
      await screen.findByText("Select a conversation to view its message timeline."),
    ).toBeInTheDocument();
  });

  it("auto-selects the conversation named in a ?conversation= deep link (e.g. from Escalations)", async () => {
    mockSearchParams.mockReturnValue(new URLSearchParams("conversation=conv-1"));
    vi.mocked(api.getConversation).mockResolvedValue(conversation());
    vi.mocked(api.listMessages).mockResolvedValue({
      data: [message()],
      meta: { total: 1, limit: 50, offset: 0 },
    });

    renderWithProviders(<InboxPage />);

    await waitFor(() =>
      expect(api.getConversation).toHaveBeenCalledWith(expect.any(Function), "conv-1"),
    );
    expect(await screen.findByText("Are you open today?")).toBeInTheDocument();
  });
});
