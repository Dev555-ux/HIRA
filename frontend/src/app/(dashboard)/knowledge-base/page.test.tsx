import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
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
  });

  it("shows an Import Website button beside Add entry", async () => {
    renderWithProviders(<KnowledgeBasePage />);
    expect(
      await screen.findByRole("button", { name: /import website/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add entry/i })).toBeInTheDocument();
  });

  it("opens a dialog with a URL field and Cancel / Import Website actions", async () => {
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: /import website/i }));

    expect(screen.getByText("Import website")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("https://example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Import Website" })).toBeInTheDocument();
  });

  it("rejects an invalid URL without calling the API", async () => {
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: /import website/i }));
    await user.type(screen.getByPlaceholderText("https://example.com"), "not-a-url");
    await user.click(screen.getByRole("button", { name: "Import Website" }));

    expect(await screen.findByText(/enter a valid url/i)).toBeInTheDocument();
    expect(api.importWebsite).not.toHaveBeenCalled();
  });

  it("shows 'Importing website…' and disables controls while the import is pending", async () => {
    const user = userEvent.setup();
    let resolveImport!: (value: { pages_imported: number; entries_created: number }) => void;
    vi.mocked(api.importWebsite).mockReturnValue(
      new Promise((resolve) => {
        resolveImport = resolve;
      }),
    );

    renderWithProviders(<KnowledgeBasePage />);
    await user.click(await screen.findByRole("button", { name: /import website/i }));
    await user.type(screen.getByPlaceholderText("https://example.com"), "https://example.com");
    await user.click(screen.getByRole("button", { name: "Import Website" }));

    const pendingButton = await screen.findByRole("button", { name: "Importing website…" });
    expect(pendingButton).toBeDisabled();
    expect(screen.getAllByText("Importing website…").length).toBeGreaterThan(0);
    expect(screen.getByPlaceholderText("https://example.com")).toBeDisabled();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeDisabled();

    resolveImport({ pages_imported: 1, entries_created: 3 });
  });

  it("shows a success toast with the counts and refreshes the list on success", async () => {
    const user = userEvent.setup();
    vi.mocked(api.importWebsite).mockResolvedValue({ pages_imported: 1, entries_created: 4 });

    renderWithProviders(<KnowledgeBasePage />);
    await user.click(await screen.findByRole("button", { name: /import website/i }));
    await user.type(screen.getByPlaceholderText("https://example.com"), "https://example.com");
    await user.click(screen.getByRole("button", { name: "Import Website" }));

    expect(
      await screen.findByText("HIRA learned 4 new facts about your business"),
    ).toBeInTheDocument();
    expect(screen.getByText("Imported from 1 page.")).toBeInTheDocument();

    // Dialog closed after success.
    expect(screen.queryByText("Import website")).not.toBeInTheDocument();

    // List refreshed: one call on mount, one after the mutation invalidates the query.
    await waitFor(() => expect(api.listKbEntries).toHaveBeenCalledTimes(2));
  });

  it("closes the dialog without importing when Cancel is clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: /import website/i }));
    await user.click(screen.getByRole("button", { name: /cancel/i }));

    expect(screen.queryByText("Import website")).not.toBeInTheDocument();
    expect(api.importWebsite).not.toHaveBeenCalled();
  });
});

describe("KnowledgeBasePage — delete confirmation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listKbEntries).mockResolvedValue([
      { id: "1", title: "Office hours", content: "9am-5pm", created_at: "", updated_at: "" },
    ]);
  });

  it("uses a styled dialog, not a native confirm(), to confirm deletion", async () => {
    const confirmSpy = vi.spyOn(window, "confirm");
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: /delete entry/i }));

    expect(await screen.findByText('Delete "Office hours"?')).toBeInTheDocument();
    expect(confirmSpy).not.toHaveBeenCalled();
  });

  it("deletes the entry when the dialog is confirmed", async () => {
    vi.mocked(api.deleteKbEntry).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: /delete entry/i }));
    await screen.findByText('Delete "Office hours"?');
    await user.click(screen.getByRole("button", { name: /^delete$/i }));

    await waitFor(() => expect(api.deleteKbEntry).toHaveBeenCalledWith(expect.any(Function), "1"));
    expect(screen.queryByText('Delete "Office hours"?')).not.toBeInTheDocument();
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

describe("KnowledgeBasePage — error state", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a retryable error instead of a misleading 'No knowledge entries yet' on fetch failure", async () => {
    vi.mocked(api.listKbEntries).mockRejectedValue(new Error("Network error"));
    renderWithProviders(<KnowledgeBasePage />);

    expect(await screen.findByText("Couldn't load knowledge base")).toBeInTheDocument();
    expect(screen.getByText("Network error")).toBeInTheDocument();
    expect(screen.queryByText("No knowledge entries yet")).not.toBeInTheDocument();
  });

  it("retries the fetch when Retry is clicked", async () => {
    vi.mocked(api.listKbEntries).mockRejectedValueOnce(new Error("Network error"));
    vi.mocked(api.listKbEntries).mockResolvedValueOnce([]);
    const user = userEvent.setup();
    renderWithProviders(<KnowledgeBasePage />);

    await user.click(await screen.findByRole("button", { name: /retry/i }));

    expect(await screen.findByText("No knowledge entries yet")).toBeInTheDocument();
  });
});
