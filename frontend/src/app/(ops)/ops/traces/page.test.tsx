import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { FounderTraceDetail, FounderTraceRow } from "@/lib/types";
import FounderTracesPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
  api: { listFounderTraces: vi.fn(), getFounderTraceDetail: vi.fn() },
}));

import { api } from "@/lib/api";

const mockAuth: AuthContextValue = {
  getToken: async () => "test-token",
  user: { name: "Founder", email: "founder@hira.test", imageUrl: null },
  isLoaded: true,
  mocked: true,
  signOut: vi.fn(),
  openProfile: vi.fn(),
};

function renderWithProviders() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={mockAuth}>
        <FounderTracesPage />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

const TRACE_ROW: FounderTraceRow = {
  id: "trace-1",
  business_id: "biz-1",
  business_name: "Bright Smile Dental",
  category: "action",
  plan_step_count: 1,
  roles: ["scheduler"],
  outcome: "sent",
  duration_ms: 320,
  created_at: "2026-07-25T12:00:00Z",
};

const TRACE_DETAIL: FounderTraceDetail = {
  id: "trace-1",
  business_id: "biz-1",
  business_name: "Bright Smile Dental",
  conversation_id: "conv-1",
  category: "action",
  customer_message: "Book a cleaning tomorrow at 2pm",
  plan: {
    category: "action",
    steps: [
      {
        domain: "calendar",
        action: "calendar_booking",
        role: "scheduler",
        tools: ["book_appointment", "check_availability"],
      },
    ],
    clarification_hint: null,
  },
  proposed_tool_calls: [{ tool_name: "book_appointment", agent_role: "scheduler" }],
  result_messages: [
    { id: "msg-1", type: "text", body: "You're booked for 2pm tomorrow!", status: "sent", ai_meta: null },
  ],
  outcome: "sent",
  duration_ms: 320,
  created_at: "2026-07-25T12:00:00Z",
};

describe("FounderTracesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists traces with their outcome and employee roles", async () => {
    vi.mocked(api.listFounderTraces).mockResolvedValue([TRACE_ROW]);
    renderWithProviders();

    expect(await screen.findByText("Bright Smile Dental")).toBeInTheDocument();
    expect(screen.getByText("Sent")).toBeInTheDocument();
    expect(screen.getByText("Scheduler")).toBeInTheDocument();
  });

  it("shows an honest empty state when nothing has been traced yet", async () => {
    vi.mocked(api.listFounderTraces).mockResolvedValue([]);
    renderWithProviders();

    expect(await screen.findByText("No executions yet")).toBeInTheDocument();
  });

  it("shows nothing selected until a trace is clicked", async () => {
    vi.mocked(api.listFounderTraces).mockResolvedValue([TRACE_ROW]);
    renderWithProviders();

    await screen.findByText("Bright Smile Dental");
    expect(screen.getByText("No execution selected")).toBeInTheDocument();
    expect(api.getFounderTraceDetail).not.toHaveBeenCalled();
  });

  it("replays the full execution when a trace is selected", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listFounderTraces).mockResolvedValue([TRACE_ROW]);
    vi.mocked(api.getFounderTraceDetail).mockResolvedValue(TRACE_DETAIL);
    renderWithProviders();

    await user.click(await screen.findByText("Bright Smile Dental"));

    expect(api.getFounderTraceDetail).toHaveBeenCalledWith(expect.any(Function), "trace-1");
    expect(await screen.findByText("Book a cleaning tomorrow at 2pm")).toBeInTheDocument();
    expect(screen.getByText(/calendar_booking/)).toBeInTheDocument();
    expect(screen.getByText("book_appointment")).toBeInTheDocument();
    expect(screen.getByText("You're booked for 2pm tomorrow!")).toBeInTheDocument();
  });

  it("disables Previous on the first page and Next once a page isn't full", async () => {
    vi.mocked(api.listFounderTraces).mockResolvedValue([TRACE_ROW]);
    renderWithProviders();

    await screen.findByText("Bright Smile Dental");
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("shows a retry option when the list fails to load", async () => {
    vi.mocked(api.listFounderTraces).mockRejectedValue(new Error("boom"));
    renderWithProviders();

    expect(await screen.findByText("Couldn't load executions")).toBeInTheDocument();
  });
});
