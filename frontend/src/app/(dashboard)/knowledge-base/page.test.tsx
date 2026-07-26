import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/toast";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import KnowledgeBasePage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    listKbEntries: vi.fn(),
    createKbEntry: vi.fn(),
    updateKbEntry: vi.fn(),
    deleteKbEntry: vi.fn(),
    importWebsite: vi.fn(),
    listKbDrafts: vi.fn(),
    publishKbEntry: vi.fn(),
    rejectKbEntry: vi.fn(),
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

describe("KnowledgeBasePage — website import", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listKbEntries).mockResolvedValue([]);
    vi.mocked(api.listKbDrafts).mockResolvedValue([]);
  });

  it("shows an Import Website button beside Add a fact", async () => {
    renderWithProviders(<KnowledgeBasePage />);
    expect(
      await screen.findByRole("button", { name: /import website/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add a fact/i })).toBeInTheDocument();
  });

  it("opens a dialog with a URL field and Cancel / Teach HIRA actions", async () => {
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: /import website/i }));

    expect(screen.getByText("Teach HIRA from your website")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("https://example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Teach HIRA" })).toBeInTheDocument();
  });

  it("rejects an invalid URL without calling the API", async () => {
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: /import website/i }));
    await user.type(screen.getByPlaceholderText("https://example.com"), "not-a-url");
    await user.click(screen.getByRole("button", { name: "Teach HIRA" }));

    expect(await screen.findByText(/enter a valid url/i)).toBeInTheDocument();
    expect(api.importWebsite).not.toHaveBeenCalled();
  });

  it("closes the dialog without importing when Cancel is clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: /import website/i }));
    await user.click(screen.getByRole("button", { name: /cancel/i }));

    expect(screen.queryByText("Teach HIRA from your website")).not.toBeInTheDocument();
    expect(api.importWebsite).not.toHaveBeenCalled();
  });

  describe("progress experience", () => {
    afterEach(() => vi.useRealTimers());

    it("explains what HIRA is doing instead of a bare spinner, and hides the form while pending", async () => {
      const user = userEvent.setup();
      vi.mocked(api.importWebsite).mockReturnValue(new Promise(() => {})); // never resolves

      renderWithProviders(<KnowledgeBasePage />);
      await user.click(await screen.findByRole("button", { name: /import website/i }));
      await user.type(screen.getByPlaceholderText("https://example.com"), "https://example.com");
      await user.click(screen.getByRole("button", { name: "Teach HIRA" }));

      expect(await screen.findByText("Teaching HIRA about your business")).toBeInTheDocument();
      expect(screen.getByText("Reading your website…")).toBeInTheDocument();
      // The form itself is gone, not just disabled — nothing to click mid-import.
      expect(screen.queryByPlaceholderText("https://example.com")).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /cancel/i })).not.toBeInTheDocument();
    });

    it("advances through the real stages over time without ever claiming completion early", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      const user = userEvent.setup({ delay: null });
      vi.mocked(api.importWebsite).mockReturnValue(new Promise(() => {}));

      renderWithProviders(<KnowledgeBasePage />);
      await user.click(await screen.findByRole("button", { name: /import website/i }));
      await user.type(screen.getByPlaceholderText("https://example.com"), "https://example.com");
      await user.click(screen.getByRole("button", { name: "Teach HIRA" }));

      expect(await screen.findByText("Reading your website…")).toBeInTheDocument();

      await act(() => vi.advanceTimersByTimeAsync(1300));
      expect(screen.getByText("Extracting useful information…")).toBeInTheDocument();

      await act(() => vi.advanceTimersByTimeAsync(1300 * 5));
      // Holds on the last real stage — never invents a fifth, fake one.
      expect(screen.getByText("Preparing AI responses…")).toBeInTheDocument();
      expect(screen.queryByText(/^HIRA is ready$/)).not.toBeInTheDocument();
    });
  });

  describe("success experience", () => {
    it("shows what HIRA found, pending review, not a bare 'learned' claim", async () => {
      const user = userEvent.setup();
      vi.mocked(api.importWebsite).mockResolvedValue({
        pages_imported: 1,
        entries_created: 4,
        import_batch_id: "batch-1",
        entries: [
          { id: "1", title: "Example", content: "We are open 9am to 5pm." },
          { id: "2", title: "Example", content: "Consultations start at $60." },
        ],
      });

      renderWithProviders(<KnowledgeBasePage />);
      await user.click(await screen.findByRole("button", { name: /import website/i }));
      await user.type(screen.getByPlaceholderText("https://example.com"), "https://example.com");
      await user.click(screen.getByRole("button", { name: "Teach HIRA" }));

      expect(await screen.findByText("Pending your review")).toBeInTheDocument();
      expect(
        screen.getByText(
          "Found 4 new facts from example.com — HIRA won't use any of it until you approve it below.",
        ),
      ).toBeInTheDocument();
      expect(screen.getByText("We are open 9am to 5pm.")).toBeInTheDocument();
      expect(screen.getByText("Consultations start at $60.")).toBeInTheDocument();

      expect(screen.queryByRole("link", { name: /ask hira/i })).not.toBeInTheDocument();

      // Drafts refreshed: one call on mount, one after the mutation invalidates the query.
      await waitFor(() => expect(api.listKbDrafts).toHaveBeenCalledTimes(2));
    });

    it("closes and resets when Done is clicked, ready for a fresh import next time", async () => {
      const user = userEvent.setup();
      vi.mocked(api.importWebsite).mockResolvedValue({
        pages_imported: 1,
        entries_created: 1,
        import_batch_id: "batch-1",
        entries: [{ id: "1", title: "Example", content: "A fact." }],
      });

      renderWithProviders(<KnowledgeBasePage />);
      await user.click(await screen.findByRole("button", { name: /import website/i }));
      await user.type(screen.getByPlaceholderText("https://example.com"), "https://example.com");
      await user.click(screen.getByRole("button", { name: "Teach HIRA" }));

      await user.click(await screen.findByRole("button", { name: "Done" }));
      expect(screen.queryByText("Pending your review")).not.toBeInTheDocument();

      await user.click(await screen.findByRole("button", { name: /import website/i }));
      expect(screen.getByText("Teach HIRA from your website")).toBeInTheDocument();
      expect(screen.queryByText("Pending your review")).not.toBeInTheDocument();
    });
  });
});

describe("KnowledgeBasePage — manual facts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listKbEntries).mockResolvedValue([]);
    vi.mocked(api.listKbDrafts).mockResolvedValue([]);
  });

  it("confirms after teaching HIRA a fact manually", async () => {
    const user = userEvent.setup();
    vi.mocked(api.createKbEntry).mockResolvedValue([
      { id: "1", title: "Office hours", content: "9am-5pm", status: "published", import_batch_id: null, created_at: "", updated_at: "" },
    ]);

    renderWithProviders(<KnowledgeBasePage />);
    await user.click(await screen.findByRole("button", { name: /add a fact/i }));
    await user.type(screen.getByPlaceholderText("Office hours"), "Office hours");
    await user.type(
      screen.getByPlaceholderText("We are open Monday to Friday, 9am to 6pm."),
      "9am-5pm",
    );
    await user.click(screen.getByRole("button", { name: "Teach HIRA" }));

    expect(await screen.findByText("HIRA learned this fact.")).toBeInTheDocument();
  });
});

describe("KnowledgeBasePage — delete confirmation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listKbEntries).mockResolvedValue([
      { id: "1", title: "Office hours", content: "9am-5pm", status: "published", import_batch_id: null, created_at: "", updated_at: "" },
    ]);
    vi.mocked(api.listKbDrafts).mockResolvedValue([]);
  });

  it("uses a styled dialog, not a native confirm(), to confirm deletion", async () => {
    const confirmSpy = vi.spyOn(window, "confirm");
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: /delete entry/i }));

    expect(await screen.findByText('Delete "Office hours"?')).toBeInTheDocument();
    expect(confirmSpy).not.toHaveBeenCalled();
  });

  it("deletes the entry and confirms when the dialog is confirmed", async () => {
    vi.mocked(api.deleteKbEntry).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: /delete entry/i }));
    await screen.findByText('Delete "Office hours"?');
    await user.click(screen.getByRole("button", { name: /^delete$/i }));

    await waitFor(() => expect(api.deleteKbEntry).toHaveBeenCalledWith(expect.any(Function), "1"));
    expect(screen.queryByText('Delete "Office hours"?')).not.toBeInTheDocument();
    expect(await screen.findByText("Removed — HIRA won't reference this anymore.")).toBeInTheDocument();
  });

  it("shows an error toast instead of a false success when deletion fails", async () => {
    vi.mocked(api.deleteKbEntry).mockRejectedValue(new Error("Network error"));
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: /delete entry/i }));
    await screen.findByText('Delete "Office hours"?');
    await user.click(screen.getByRole("button", { name: /^delete$/i }));

    expect(await screen.findByText("Couldn't remove this fact")).toBeInTheDocument();
    expect(
      screen.queryByText("Removed — HIRA won't reference this anymore."),
    ).not.toBeInTheDocument();
  });

  it("does not delete when the dialog is cancelled", async () => {
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: /delete entry/i }));
    await screen.findByText('Delete "Office hours"?');
    await user.click(screen.getByRole("button", { name: /cancel/i }));

    expect(screen.queryByText('Delete "Office hours"?')).not.toBeInTheDocument();
    expect(api.deleteKbEntry).not.toHaveBeenCalled();
  });
});

describe("KnowledgeBasePage — pending review (draft imports)", () => {
  const draftEntry = (id: string, content: string) => ({
    id,
    title: "Opening Hours",
    content,
    status: "draft" as const,
    import_batch_id: "batch-1",
    created_at: "",
    updated_at: "",
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listKbEntries).mockResolvedValue([]);
  });

  it("does not show a Pending Review section when there are no drafts", async () => {
    vi.mocked(api.listKbDrafts).mockResolvedValue([]);
    renderWithProviders(<KnowledgeBasePage />);

    await screen.findByText("HIRA doesn't know this yet");
    expect(screen.queryByLabelText("Approve fact")).not.toBeInTheDocument();
  });

  it("shows each draft batch with its facts and per-fact actions", async () => {
    vi.mocked(api.listKbDrafts).mockResolvedValue([
      {
        import_batch_id: "batch-1",
        entries: [draftEntry("1", "We open at 9am."), draftEntry("2", "We close at 5pm.")],
      },
    ]);
    renderWithProviders(<KnowledgeBasePage />);

    expect(await screen.findByText(/2 facts imported from Opening Hours/)).toBeInTheDocument();
    expect(screen.getByText("We open at 9am.")).toBeInTheDocument();
    expect(screen.getByText("We close at 5pm.")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Approve fact")).toHaveLength(2);
    expect(screen.getAllByLabelText("Reject fact")).toHaveLength(2);
  });

  it("publishes a single fact when Approve is clicked", async () => {
    vi.mocked(api.listKbDrafts).mockResolvedValue([
      { import_batch_id: "batch-1", entries: [draftEntry("1", "We open at 9am.")] },
    ]);
    vi.mocked(api.publishKbEntry).mockResolvedValue({
      ...draftEntry("1", "We open at 9am."),
      status: "published",
    });
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByLabelText("Approve fact"));

    await waitFor(() =>
      expect(api.publishKbEntry).toHaveBeenCalledWith(expect.any(Function), "1"),
    );
  });

  it("rejects (deletes) a single fact when Reject is clicked", async () => {
    vi.mocked(api.listKbDrafts).mockResolvedValue([
      { import_batch_id: "batch-1", entries: [draftEntry("1", "We open at 9am.")] },
    ]);
    vi.mocked(api.rejectKbEntry).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByLabelText("Reject fact"));

    await waitFor(() => expect(api.rejectKbEntry).toHaveBeenCalledWith(expect.any(Function), "1"));
  });

  it("publishes every fact in the batch when Approve all is clicked, and reports full success", async () => {
    vi.mocked(api.listKbDrafts).mockResolvedValue([
      {
        import_batch_id: "batch-1",
        entries: [draftEntry("1", "We open at 9am."), draftEntry("2", "We close at 5pm.")],
      },
    ]);
    vi.mocked(api.publishKbEntry).mockResolvedValue(draftEntry("1", "We open at 9am."));
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: "Approve all" }));

    await waitFor(() => expect(api.publishKbEntry).toHaveBeenCalledTimes(2));
    expect(api.publishKbEntry).toHaveBeenCalledWith(expect.any(Function), "1");
    expect(api.publishKbEntry).toHaveBeenCalledWith(expect.any(Function), "2");
    expect(
      await screen.findByText("Published — HIRA will start using this right away."),
    ).toBeInTheDocument();
  });

  it("awaits every publish call and reports partial success when some fail", async () => {
    vi.mocked(api.listKbDrafts).mockResolvedValue([
      {
        import_batch_id: "batch-1",
        entries: [draftEntry("1", "We open at 9am."), draftEntry("2", "We close at 5pm.")],
      },
    ]);
    vi.mocked(api.publishKbEntry).mockImplementation((_getToken, id) =>
      id === "1"
        ? Promise.resolve(draftEntry("1", "We open at 9am."))
        : Promise.reject(new Error("network error")),
    );
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: "Approve all" }));

    await waitFor(() => expect(api.publishKbEntry).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Published 1 of 2 facts.")).toBeInTheDocument();
    expect(screen.getByText("1 failed to publish — please try again.")).toBeInTheDocument();
  });

  it("reports failure without claiming success when every publish call fails", async () => {
    vi.mocked(api.listKbDrafts).mockResolvedValue([
      { import_batch_id: "batch-1", entries: [draftEntry("1", "We open at 9am.")] },
    ]);
    vi.mocked(api.publishKbEntry).mockRejectedValue(new Error("network error"));
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: "Approve all" }));

    await waitFor(() => expect(api.publishKbEntry).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Couldn't publish any facts.")).toBeInTheDocument();
    expect(
      screen.queryByText("Published — HIRA will start using this right away."),
    ).not.toBeInTheDocument();
  });
});

describe("KnowledgeBasePage — empty and error states", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listKbDrafts).mockResolvedValue([]);
  });

  it("explains what to do next instead of a bare 'no data' message", async () => {
    vi.mocked(api.listKbEntries).mockResolvedValue([]);
    renderWithProviders(<KnowledgeBasePage />);

    expect(await screen.findByText("HIRA doesn't know this yet")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Add a fact, or import your website, and HIRA will start using it to answer customers immediately.",
      ),
    ).toBeInTheDocument();
  });

  it("shows a retryable error instead of a misleading empty state on fetch failure", async () => {
    vi.mocked(api.listKbEntries).mockRejectedValue(new Error("Network error"));
    renderWithProviders(<KnowledgeBasePage />);

    expect(await screen.findByText("Couldn't load your business knowledge")).toBeInTheDocument();
    expect(screen.getByText("Network error")).toBeInTheDocument();
    expect(screen.queryByText("HIRA doesn't know this yet")).not.toBeInTheDocument();
  });

  it("retries the fetch when Retry is clicked", async () => {
    vi.mocked(api.listKbEntries).mockRejectedValueOnce(new Error("Network error"));
    vi.mocked(api.listKbEntries).mockResolvedValueOnce([]);
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: /retry/i }));

    expect(await screen.findByText("HIRA doesn't know this yet")).toBeInTheDocument();
  });
});
