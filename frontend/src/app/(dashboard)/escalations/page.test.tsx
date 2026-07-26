import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/toast";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { Escalation } from "@/lib/types";
import EscalationsPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    listEscalations: vi.fn(),
    assignEscalation: vi.fn(),
    unassignEscalation: vi.fn(),
    resolveEscalation: vi.fn(),
  },
}));

import { api } from "@/lib/api";

function mockAuth(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return {
    getToken: async () => "test-token",
    user: { name: "Dev", email: "dev@test.com", imageUrl: null },
    isLoaded: true,
    mocked: true,
    signOut: vi.fn(),
    openProfile: vi.fn(),
    ...overrides,
  };
}

function renderWithProviders(auth: AuthContextValue = mockAuth()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={auth}>
        <ToastProvider>
          <EscalationsPage />
        </ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

function escalation(overrides: Partial<Escalation> = {}): Escalation {
  return {
    id: "esc-1",
    reason: "low_confidence",
    status: "open",
    assigned_to: null,
    resolved_by: null,
    resolved_at: null,
    created_at: new Date().toISOString(),
    conversation: {
      id: "conv-1",
      customer: { id: "cust-1", display_name: "Jamie Rivera", wa_phone: "+15551230000" },
    },
    ...overrides,
  };
}

function listResponse(data: Escalation[]) {
  return { data, meta: { total: data.length, limit: 20, offset: 0 } };
}

describe("EscalationsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows an empty state when there are no open escalations", async () => {
    vi.mocked(api.listEscalations).mockResolvedValue(listResponse([]));
    renderWithProviders();

    expect(await screen.findByText("Nothing needs you right now")).toBeInTheDocument();
  });

  it("shows the customer, reason, and time for each escalation", async () => {
    vi.mocked(api.listEscalations).mockResolvedValue(
      listResponse([escalation({ reason: "customer_request" })]),
    );
    renderWithProviders();

    expect(await screen.findByText("Jamie Rivera")).toBeInTheDocument();
    expect(screen.getByText("Customer asked for a human")).toBeInTheDocument();
  });

  it("shows an Assign to me button when unassigned, and claims it on click", async () => {
    vi.mocked(api.listEscalations).mockResolvedValue(listResponse([escalation()]));
    vi.mocked(api.assignEscalation).mockResolvedValue(
      escalation({ assigned_to: { id: "u1", email: "dev@test.com" } }),
    );
    const user = userEvent.setup();
    renderWithProviders();

    await user.click(await screen.findByRole("button", { name: /assign to me/i }));

    await waitFor(() =>
      expect(api.assignEscalation).toHaveBeenCalledWith(expect.any(Function), "esc-1"),
    );
  });

  it("shows 'Assigned to you' and an Unassign button once claimed by the current user", async () => {
    vi.mocked(api.listEscalations).mockResolvedValue(
      listResponse([escalation({ assigned_to: { id: "u1", email: "dev@test.com" } })]),
    );
    renderWithProviders();

    expect(await screen.findByText("Assigned to you")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unassign" })).toBeInTheDocument();
  });

  it("shows the assignee's email when claimed by someone else", async () => {
    vi.mocked(api.listEscalations).mockResolvedValue(
      listResponse([escalation({ assigned_to: { id: "u2", email: "teammate@test.com" } })]),
    );
    renderWithProviders();

    expect(await screen.findByText("Assigned to teammate@test.com")).toBeInTheDocument();
  });

  it("resolves an escalation and shows a confirmation toast", async () => {
    vi.mocked(api.listEscalations).mockResolvedValue(listResponse([escalation()]));
    vi.mocked(api.resolveEscalation).mockResolvedValue(escalation({ status: "resolved" }));
    const user = userEvent.setup();
    renderWithProviders();

    await user.click(await screen.findByRole("button", { name: "Resolve" }));

    await waitFor(() =>
      expect(api.resolveEscalation).toHaveBeenCalledWith(expect.any(Function), "esc-1"),
    );
    expect(await screen.findByText("Resolved.")).toBeInTheDocument();
  });

  it("shows an error toast and leaves the escalation open when resolving fails", async () => {
    vi.mocked(api.listEscalations).mockResolvedValue(listResponse([escalation()]));
    vi.mocked(api.resolveEscalation).mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    renderWithProviders();

    await user.click(await screen.findByRole("button", { name: "Resolve" }));

    expect(await screen.findByText("Couldn't resolve this escalation")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resolve" })).toBeInTheDocument();
  });

  it("shows an error toast when assigning fails", async () => {
    vi.mocked(api.listEscalations).mockResolvedValue(listResponse([escalation()]));
    vi.mocked(api.assignEscalation).mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    renderWithProviders();

    await user.click(await screen.findByRole("button", { name: /assign to me/i }));

    expect(await screen.findByText("Couldn't assign this escalation")).toBeInTheDocument();
  });

  it("shows an error toast when unassigning fails", async () => {
    vi.mocked(api.listEscalations).mockResolvedValue(
      listResponse([escalation({ assigned_to: { id: "u1", email: "dev@test.com" } })]),
    );
    vi.mocked(api.unassignEscalation).mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    renderWithProviders();

    await user.click(await screen.findByRole("button", { name: "Unassign" }));

    expect(await screen.findByText("Couldn't unassign this escalation")).toBeInTheDocument();
  });

  it("hides assign/unassign/resolve actions for an already-resolved escalation", async () => {
    vi.mocked(api.listEscalations).mockResolvedValue(
      listResponse([escalation({ status: "resolved" })]),
    );
    renderWithProviders();

    await screen.findByText("Jamie Rivera");
    expect(screen.queryByRole("button", { name: "Resolve" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /assign to me/i })).not.toBeInTheDocument();
  });

  it("links to the conversation in the Inbox", async () => {
    vi.mocked(api.listEscalations).mockResolvedValue(listResponse([escalation()]));
    renderWithProviders();

    const link = await screen.findByRole("link", { name: /open conversation/i });
    expect(link).toHaveAttribute("href", "/inbox?conversation=conv-1");
  });

  it("defaults to the Open status filter", async () => {
    vi.mocked(api.listEscalations).mockResolvedValue(listResponse([]));
    renderWithProviders();

    await waitFor(() =>
      expect(api.listEscalations).toHaveBeenCalledWith(expect.any(Function), {
        status: "open",
        assigned: undefined,
      }),
    );
  });

  it("switches to the Resolved filter when clicked", async () => {
    vi.mocked(api.listEscalations).mockResolvedValue(listResponse([]));
    const user = userEvent.setup();
    renderWithProviders();

    await screen.findByText("Nothing needs you right now");
    await user.click(screen.getByRole("button", { name: "Resolved" }));

    await waitFor(() =>
      expect(api.listEscalations).toHaveBeenCalledWith(expect.any(Function), {
        status: "resolved",
        assigned: undefined,
      }),
    );
  });

  it("filters by Unassigned when clicked", async () => {
    vi.mocked(api.listEscalations).mockResolvedValue(listResponse([]));
    const user = userEvent.setup();
    renderWithProviders();

    await screen.findByText("Nothing needs you right now");
    await user.click(screen.getByRole("button", { name: "Unassigned" }));

    await waitFor(() =>
      expect(api.listEscalations).toHaveBeenCalledWith(expect.any(Function), {
        status: "open",
        assigned: "unassigned",
      }),
    );
  });
});
