import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/toast";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { KbEntry, PlaygroundHistory, PlaygroundResponse } from "@/lib/types";
import DemoChatPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    getPlaygroundHistory: vi.fn(),
    sendPlaygroundMessage: vi.fn(),
    listKbEntries: vi.fn(),
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

function kbEntry(overrides: Partial<KbEntry> = {}): KbEntry {
  return {
    id: "kb-1",
    title: "Hours",
    content: "We are open 9-5.",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

function emptyHistory(): PlaygroundHistory {
  return { conversation_id: "conv-1", messages: [] };
}

function playgroundResponse(overrides: Partial<PlaygroundResponse> = {}): PlaygroundResponse {
  return { reply: "Hello! I'm HIRA.", model: "mock-1", retrieved: [], tool: null, ...overrides };
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

describe("DemoChatPage — Sprint 56 first-time experience", () => {
  beforeEach(() => {
    vi.mocked(api.getPlaygroundHistory).mockReset();
    vi.mocked(api.sendPlaygroundMessage).mockReset();
    vi.mocked(api.listKbEntries).mockReset();
  });

  it("shows the welcome card, starters, and Demo Mode badge for a fresh business with no Business Knowledge", async () => {
    vi.mocked(api.getPlaygroundHistory).mockResolvedValue(emptyHistory());
    vi.mocked(api.listKbEntries).mockResolvedValue([]);

    renderWithProviders(<DemoChatPage />);

    expect(await screen.findByText("Welcome to HIRA")).toBeInTheDocument();
    expect(screen.getByText(/What can you do\?/)).toBeInTheDocument();
    expect(screen.getByText(/Demo Mode/)).toBeInTheDocument();
  });

  it("does not show the welcome card or Demo Mode badge once Business Knowledge exists", async () => {
    vi.mocked(api.getPlaygroundHistory).mockResolvedValue(emptyHistory());
    vi.mocked(api.listKbEntries).mockResolvedValue([kbEntry()]);

    renderWithProviders(<DemoChatPage />);

    // The pre-existing empty state (unchanged) shows instead.
    expect(await screen.findByText("Start chatting with HIRA")).toBeInTheDocument();
    expect(screen.queryByText("Welcome to HIRA")).not.toBeInTheDocument();
    expect(screen.queryByText(/Demo Mode/)).not.toBeInTheDocument();
  });

  it("does not show the welcome card when the conversation already has messages, even in Demo Mode", async () => {
    vi.mocked(api.listKbEntries).mockResolvedValue([]);
    vi.mocked(api.getPlaygroundHistory).mockResolvedValue({
      conversation_id: "conv-1",
      messages: [
        {
          id: "m1",
          direction: "inbound",
          body: "Hi",
          type: "text",
          status: "received",
          created_at: new Date().toISOString(),
        },
        {
          id: "m2",
          direction: "outbound",
          body: "Hello!",
          type: "text",
          status: "sent",
          created_at: new Date().toISOString(),
        },
      ],
    });

    renderWithProviders(<DemoChatPage />);

    await screen.findByText("Hello!");
    expect(screen.queryByText("Welcome to HIRA")).not.toBeInTheDocument();
    // The Demo Mode badge itself is independent of conversation state —
    // it's still shown in the header — but the starters must be gone.
    expect(screen.queryByText(/What can you do\?/)).not.toBeInTheDocument();
  });

  it("sends the starter's message immediately when a chip is clicked, and the starters disappear after", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getPlaygroundHistory).mockResolvedValue(emptyHistory());
    vi.mocked(api.listKbEntries).mockResolvedValue([]);
    vi.mocked(api.sendPlaygroundMessage).mockResolvedValue(playgroundResponse());

    renderWithProviders(<DemoChatPage />);

    const chip = await screen.findByRole("button", { name: /What can you do\?/ });
    await user.click(chip);

    await waitFor(() => expect(api.sendPlaygroundMessage).toHaveBeenCalledWith(
      expect.any(Function),
      "What can you do?",
    ));
    await waitFor(() =>
      expect(screen.queryByText(/What can you do\?/, { selector: "button *" })).not.toBeInTheDocument(),
    );
  });
});
