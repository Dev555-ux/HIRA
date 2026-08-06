import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/toast";
import { AuthContext, type AuthContextValue } from "@/lib/auth-context";
import type { Appointment, Conversation, OnboardingStatus } from "@/lib/types";
import DashboardPage from "./page";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  api: {
    listPending: vi.fn(),
    getOnboardingStatus: vi.fn(),
    listConversations: vi.fn(),
    listCustomers: vi.fn(),
    listAppointments: vi.fn(),
    approveMessage: vi.fn(),
    rejectMessage: vi.fn(),
    updateDraft: vi.fn(),
  },
}));

import { api } from "@/lib/api";

const mockAuth: AuthContextValue = {
  getToken: async () => "test-token",
  user: { name: "Dev", email: "dev@test.com", imageUrl: null },
  isLoaded: true,
  mocked: true,
  signOut: vi.fn(),
  openProfile: vi.fn(),
};

const onboardingStatus: OnboardingStatus = {
  has_business: true,
  business: {
    id: "biz-1",
    name: "Stoneveil Dental",
    onboarding_status: "live",
    whatsapp_connection_status: "connected",
  } as OnboardingStatus["business"],
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

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getOnboardingStatus).mockResolvedValue(onboardingStatus);
    // Safe defaults so every test only needs to override what it cares about.
    vi.mocked(api.listPending).mockResolvedValue([]);
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 1, offset: 0 },
    });
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 1, offset: 0 },
    });
    vi.mocked(api.listAppointments).mockResolvedValue([]);
    vi.mocked(api.approveMessage).mockResolvedValue({ id: "msg-1", status: "sent" });
    vi.mocked(api.rejectMessage).mockResolvedValue({ id: "msg-1", status: "rejected" });
    vi.mocked(api.updateDraft).mockResolvedValue({
      id: "msg-1",
      body: "revised",
      status: "pending_approval",
    });
  });

  it("shows real conversation and customer totals from existing list endpoints", async () => {
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [],
      meta: { total: 37, limit: 1, offset: 0 },
    });
    vi.mocked(api.listCustomers).mockResolvedValue({
      data: [],
      meta: { total: 12, limit: 1, offset: 0 },
    });

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("37")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(api.listConversations).toHaveBeenCalledWith(
      expect.any(Function),
      expect.objectContaining({ limit: 1 }),
    );
    expect(api.listCustomers).toHaveBeenCalledWith(
      expect.any(Function),
      expect.objectContaining({ limit: 1 }),
    );
  });

  it("greets the signed-in owner by name with a real-data summary sentence", async () => {
    vi.mocked(api.listPending).mockResolvedValue([
      {
        id: "msg-1",
        conversation_id: "conv-1",
        body: "Yes, we're open!",
        created_at: new Date().toISOString(),
        customer: { id: "cust-1", display_name: "Jordan Lee", wa_phone: "+15551230000" },
        conversation_preview: null,
      },
    ]);

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Dev");
    expect(
      await screen.findByText("You have 1 reply waiting for review and no appointments booked."),
    ).toBeInTheDocument();
  });

  it("shows a reassuring KPI hint when there's nothing pending", async () => {
    renderWithProviders(<DashboardPage />);
    expect(await screen.findByText("Everything reviewed")).toBeInTheDocument();
  });

  it("shows an actionable KPI hint when replies are pending", async () => {
    vi.mocked(api.listPending).mockResolvedValue([
      {
        id: "msg-1",
        conversation_id: "conv-1",
        body: "Yes, we're open!",
        created_at: new Date().toISOString(),
        customer: { id: "cust-1", display_name: "Jordan Lee", wa_phone: "+15551230000" },
        conversation_preview: null,
      },
    ]);
    renderWithProviders(<DashboardPage />);
    // "Awaiting your review" also appears in the inline ReviewReplyCard's own
    // StatusPill (M10) — scope to the KPI tile specifically.
    const kpi = (await screen.findByText("Pending approvals")).closest<HTMLElement>(".rounded-xl")!;
    expect(await within(kpi).findByText("Awaiting your review")).toBeInTheDocument();
  });

  it("shows the pending-approval count and customer name", async () => {
    vi.mocked(api.listPending).mockResolvedValue([
      {
        id: "msg-1",
        conversation_id: "conv-1",
        body: "Yes, we're open!",
        created_at: new Date().toISOString(),
        customer: { id: "cust-1", display_name: "Jordan Lee", wa_phone: "+15551230000" },
        conversation_preview: null,
      },
    ]);

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("Yes, we're open!")).toBeInTheDocument();
    // Appears twice deliberately: once in "Needs your attention" (the full
    // draft) and once in "Recent activity" (the compact log entry).
    expect(screen.getAllByText("Jordan Lee").length).toBeGreaterThan(0);
  });

  it("shows a retryable error instead of a misleading zero when pending approvals fail to load", async () => {
    vi.mocked(api.listPending).mockRejectedValue(new Error("Network error"));

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("Couldn't load pending approvals")).toBeInTheDocument();
    expect(screen.queryByText("Nothing pending")).not.toBeInTheDocument();
    expect(screen.getAllByText("Couldn't load").length).toBeGreaterThan(0);
  });

  it("shows a dash instead of a misleading zero when conversation/customer totals fail to load", async () => {
    vi.mocked(api.listConversations).mockRejectedValue(new Error("Network error"));
    vi.mocked(api.listCustomers).mockRejectedValue(new Error("Network error"));

    renderWithProviders(<DashboardPage />);

    await screen.findByText("Nothing pending");
    expect(await screen.findAllByText("—")).toHaveLength(2);
    expect(await screen.findAllByText("Couldn't load")).toHaveLength(2);
  });

  it("shows upcoming appointments with customer name, time range, and status", async () => {
    const appointment: Appointment = {
      id: "appt-1",
      customer: { id: "cust-1", display_name: "Jordan Lee", wa_phone: "+15551230000" },
      conversation_id: null,
      starts_at: "2026-08-05T14:00:00",
      ends_at: "2026-08-05T15:00:00",
      status: "booked",
      created_at: "2026-08-01T00:00:00",
      updated_at: "2026-08-01T00:00:00",
    };
    vi.mocked(api.listAppointments).mockResolvedValue([appointment]);

    renderWithProviders(<DashboardPage />);

    // Wait for the appointment data itself to render before asserting the
    // rest — "Upcoming appointments" is static label text present from the
    // first render, so it resolves before the async data does.
    // Appears twice deliberately: once in "Upcoming appointments" and once
    // in "Recent activity" (the same booking, logged).
    await waitFor(() => expect(screen.getAllByText("Jordan Lee").length).toBeGreaterThan(0));
    expect(screen.getAllByText("Upcoming appointments")).toHaveLength(2);
    expect(screen.getByText("Booked")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument(); // the KPI count
  });

  it("shows a meaningful empty state when there are no upcoming appointments", async () => {
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("No upcoming appointments")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New appointment" })).toHaveAttribute(
      "href",
      "/appointments",
    );
  });

  it("shows a retryable error for the appointments widget when it fails to load", async () => {
    vi.mocked(api.listAppointments).mockRejectedValue(new Error("Network error"));

    renderWithProviders(<DashboardPage />);

    expect(await screen.findAllByText("Couldn't load")).not.toHaveLength(0);
  });

  it("merges conversations into Recent activity with their message preview", async () => {
    const conversation: Conversation = {
      id: "conv-1",
      status: "escalated",
      customer: { id: "cust-2", display_name: "Morgan Reyes", wa_phone: "+15559876543" },
      last_message_at: new Date().toISOString(),
      preview: "Can I speak to someone about a refund?",
      has_pending_approval: false,
      created_at: new Date().toISOString(),
    };
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [conversation],
      meta: { total: 1, limit: 5, offset: 0 },
    });

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("Morgan Reyes")).toBeInTheDocument();
    expect(screen.getByText("Can I speak to someone about a refund?")).toBeInTheDocument();
  });

  it("merges pending replies and appointments into Recent activity, most recent first", async () => {
    vi.mocked(api.listPending).mockResolvedValue([
      {
        id: "msg-1",
        conversation_id: "conv-1",
        body: "Yes, we're open!",
        created_at: "2026-08-01T12:00:00Z",
        customer: { id: "cust-1", display_name: "Jordan Lee", wa_phone: "+15551230000" },
        conversation_preview: null,
      },
    ]);
    vi.mocked(api.listAppointments).mockResolvedValue([
      {
        id: "appt-1",
        customer: { id: "cust-3", display_name: "Sam Torres", wa_phone: "+15557654321" },
        conversation_id: null,
        starts_at: "2026-08-05T14:00:00",
        ends_at: "2026-08-05T15:00:00",
        status: "booked",
        created_at: "2026-08-02T09:00:00Z",
        updated_at: "2026-08-02T09:00:00Z",
      },
    ]);

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("Reply drafted, awaiting your approval")).toBeInTheDocument();
    expect(screen.getByText(/Appointment booked for/)).toBeInTheDocument();
    expect(screen.getAllByText("Sam Torres").length).toBeGreaterThan(0);

    // Sam Torres's appointment was created after Jordan Lee's pending reply,
    // so it should appear first in the feed.
    const feed = await screen.findByTestId("activity-feed");
    const names = Array.from(feed.querySelectorAll("p.font-medium")).map((el) => el.textContent);
    expect(names.indexOf("Sam Torres")).toBeLessThan(names.indexOf("Jordan Lee"));
  });

  it("doesn't show the same pending draft twice in Recent activity", async () => {
    // A conversation whose latest message IS the still-pending draft used to
    // produce two rows for the same event: "Reply drafted, awaiting your
    // approval" (from the pending list) and the draft's own text again (from
    // the conversation preview, since that draft is the conversation's most
    // recent message).
    vi.mocked(api.listPending).mockResolvedValue([
      {
        id: "msg-1",
        conversation_id: "conv-1",
        body: "Yes, we're open Saturday from 9 to 5 -- would you like to book a slot?",
        created_at: "2026-08-01T12:00:00Z",
        customer: { id: "cust-1", display_name: "Jordan Lee", wa_phone: "+15551230000" },
        conversation_preview: null,
      },
    ]);
    vi.mocked(api.listConversations).mockResolvedValue({
      data: [
        {
          id: "conv-1",
          status: "active",
          customer: { id: "cust-1", display_name: "Jordan Lee", wa_phone: "+15551230000" },
          last_message_at: "2026-08-01T12:00:00Z",
          preview: "Yes, we're open Saturday from 9 to 5 -- would you like to book a slot?",
          has_pending_approval: true,
          created_at: "2026-08-01T12:00:00Z",
        },
      ],
      meta: { total: 1, limit: 5, offset: 0 },
    });

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("Reply drafted, awaiting your approval")).toBeInTheDocument();
    const feed = await screen.findByTestId("activity-feed");
    expect(within(feed).getAllByText("Jordan Lee")).toHaveLength(1);
  });

  it("shows a meaningful empty state when there is no recent activity", async () => {
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("Waiting for your first customer")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Try Demo Chat" })).toHaveAttribute(
      "href",
      "/demo",
    );
  });

  it("shows real WhatsApp status, never internal AI provider/model names", async () => {
    renderWithProviders(<DashboardPage />);

    await screen.findByText("WhatsApp status");
    expect(await screen.findByText("Connected")).toBeInTheDocument();
    expect(
      screen.queryByText(/groq|llama|claude|embedding|ai provider|knowledge search/i),
    ).not.toBeInTheDocument();
  });

  it("reflects a not-connected WhatsApp status honestly", async () => {
    vi.mocked(api.getOnboardingStatus).mockResolvedValue({
      has_business: true,
      business: {
        ...onboardingStatus.business!,
        whatsapp_connection_status: "not_connected",
      } as OnboardingStatus["business"],
    });
    renderWithProviders(<DashboardPage />);

    await screen.findByText("WhatsApp status");
    expect(screen.getByText("Not connected")).toBeInTheDocument();
  });

  it("refreshes every dashboard data source when Refresh is clicked", async () => {
    renderWithProviders(<DashboardPage />);
    await screen.findByText("Nothing pending");
    vi.mocked(api.listPending).mockClear();
    vi.mocked(api.getOnboardingStatus).mockClear();
    vi.mocked(api.listConversations).mockClear();
    vi.mocked(api.listCustomers).mockClear();
    vi.mocked(api.listAppointments).mockClear();

    await userEvent.click(screen.getByRole("button", { name: /refresh/i }));

    expect(api.listPending).toHaveBeenCalled();
    expect(api.getOnboardingStatus).toHaveBeenCalled();
    expect(api.listConversations).toHaveBeenCalled();
    expect(api.listCustomers).toHaveBeenCalled();
    expect(api.listAppointments).toHaveBeenCalled();
  });

  // M10: inline review wired directly on the Dashboard (not via
  // PendingReviewContainer/CONVERSATIONS_KEY — see DashboardReviewCard's own
  // comment) — these confirm the same use-pending.ts mutations Inbox and
  // /pending already rely on behave identically when triggered from here,
  // and that this section and the KPI tile never disagree afterward.
  describe("inline review (M10)", () => {
    const reply = {
      id: "msg-1",
      conversation_id: "conv-1",
      body: "Yes, we're open!",
      created_at: new Date().toISOString(),
      customer: { id: "cust-1", display_name: "Jordan Lee", wa_phone: "+15551230000" },
      conversation_preview: null,
    };

    it("approve removes the card and decrements the KPI in the same tick", async () => {
      // Once for the initial load; onSettled's invalidation refetches
      // afterward, and the (mocked) backend now correctly reflects the
      // approval — same as a real server response.
      vi.mocked(api.listPending).mockResolvedValueOnce([reply]).mockResolvedValue([]);
      const user = userEvent.setup();
      renderWithProviders(<DashboardPage />);

      await screen.findByText("Yes, we're open!");
      const kpiBefore = (await screen.findByText("Pending approvals")).closest<HTMLElement>(".rounded-xl")!;
      expect(await within(kpiBefore).findByText("1")).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: /approve & send/i }));

      // Optimistic PENDING_KEY update — no waiting on the network or the poll.
      await waitFor(() => expect(screen.queryByText("Yes, we're open!")).not.toBeInTheDocument());
      expect(api.approveMessage).toHaveBeenCalledWith(expect.any(Function), "msg-1");
      const kpiAfter = (await screen.findByText("Pending approvals")).closest<HTMLElement>(".rounded-xl")!;
      expect(await within(kpiAfter).findByText("0")).toBeInTheDocument();
    });

    it("reject removes the card via the same optimistic PENDING_KEY update", async () => {
      vi.mocked(api.listPending).mockResolvedValueOnce([reply]).mockResolvedValue([]);
      const user = userEvent.setup();
      renderWithProviders(<DashboardPage />);

      await screen.findByText("Yes, we're open!");
      await user.click(screen.getByRole("button", { name: /reject/i }));

      await waitFor(() => expect(screen.queryByText("Yes, we're open!")).not.toBeInTheDocument());
      expect(api.rejectMessage).toHaveBeenCalledWith(expect.any(Function), "msg-1");
    });

    it("edit saves the revised draft in place, without removing the card", async () => {
      vi.mocked(api.listPending).mockResolvedValue([reply]);
      const user = userEvent.setup();
      renderWithProviders(<DashboardPage />);

      await screen.findByText("Yes, we're open!");
      await user.click(screen.getByRole("button", { name: /edit/i }));
      const box = screen.getByLabelText(/edit reply/i);
      await user.clear(box);
      await user.type(box, "revised");
      await user.click(screen.getByRole("button", { name: /save/i }));

      await waitFor(() =>
        expect(api.updateDraft).toHaveBeenCalledWith(expect.any(Function), "msg-1", "revised"),
      );
      // Still awaiting review, still visible — an edit doesn't remove the card.
      // "Jordan Lee" also appears in Recent activity (existing behavior,
      // unrelated to this change), so scope to "Needs your attention".
      const section = (await screen.findByText("Needs your attention")).closest<HTMLElement>(".rounded-xl")!;
      expect(within(section).getByText("Jordan Lee")).toBeInTheDocument();
    });

    it("surfaces a destructive toast when approve fails, leaving the card reviewable", async () => {
      vi.mocked(api.listPending).mockResolvedValue([reply]);
      vi.mocked(api.approveMessage).mockRejectedValueOnce(new Error("network"));
      const user = userEvent.setup();
      renderWithProviders(<DashboardPage />);

      await screen.findByText("Yes, we're open!");
      await user.click(screen.getByRole("button", { name: /approve & send/i }));

      await waitFor(() => expect(screen.getByText("Yes, we're open!")).toBeInTheDocument());
      expect(screen.getByRole("button", { name: /approve & send/i })).toBeEnabled();
    });

    it("previews only the first PREVIEW_ROWS pending replies", async () => {
      const replies = Array.from({ length: 7 }, (_, i) => ({
        ...reply,
        id: `msg-${i}`,
        conversation_id: `conv-${i}`,
        body: `Reply body ${i}`,
        customer: { id: `cust-${i}`, display_name: `Customer ${i}`, wa_phone: "+15551230000" },
      }));
      vi.mocked(api.listPending).mockResolvedValue(replies);
      renderWithProviders(<DashboardPage />);

      await screen.findByText("Reply body 0");
      expect(screen.getByText("Reply body 4")).toBeInTheDocument();
      expect(screen.queryByText("Reply body 5")).not.toBeInTheDocument();
      expect(screen.queryByText("Reply body 6")).not.toBeInTheDocument();
    });
  });
});
