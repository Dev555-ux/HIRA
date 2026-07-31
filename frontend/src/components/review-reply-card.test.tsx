import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ReviewReplyCard } from "./review-reply-card";

describe("ReviewReplyCard", () => {
  it("renders the draft on a labelled review region", () => {
    render(<ReviewReplyCard body="Yes, we're open Saturday." authorLabel="Maya" />);
    expect(screen.getByText("Yes, we're open Saturday.")).toBeInTheDocument();
    expect(
      screen.getByRole("group", { name: /ai reply pending your review/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Maya drafted a reply/i)).toBeInTheDocument();
  });

  it("shows the waiting review status (color-independent: text present)", () => {
    render(<ReviewReplyCard body="hi" />);
    expect(screen.getAllByText(/Awaiting your review/i).length).toBeGreaterThan(0);
  });

  it("fires approve and reject handlers", async () => {
    const user = userEvent.setup();
    const onApprove = vi.fn();
    const onReject = vi.fn();
    render(<ReviewReplyCard body="hi" onApprove={onApprove} onReject={onReject} />);

    await user.click(screen.getByRole("button", { name: /approve & send/i }));
    await user.click(screen.getByRole("button", { name: /reject/i }));

    expect(onApprove).toHaveBeenCalledOnce();
    expect(onReject).toHaveBeenCalledOnce();
  });

  it("edits the draft and saves the new text", async () => {
    const user = userEvent.setup();
    const onEdit = vi.fn();
    render(<ReviewReplyCard body="original" onEdit={onEdit} />);

    await user.click(screen.getByRole("button", { name: /edit/i }));
    const box = screen.getByLabelText(/edit reply/i);
    await user.clear(box);
    await user.type(box, "revised");
    await user.click(screen.getByRole("button", { name: /save/i }));

    expect(onEdit).toHaveBeenCalledWith("revised");
  });

  it("shows a grounding summary from the real retrieved count, and hides it when zero", () => {
    const { rerender } = render(<ReviewReplyCard body="hi" groundedCount={3} />);
    expect(screen.getByText(/Grounded in 3 knowledge sources/i)).toBeInTheDocument();

    rerender(<ReviewReplyCard body="hi" groundedCount={0} />);
    expect(screen.queryByText(/Grounded in/i)).not.toBeInTheDocument();
  });

  it("does not render a confidence badge when no score is supplied (no fabrication)", () => {
    render(<ReviewReplyCard body="hi" />);
    expect(screen.queryByLabelText(/confidence/i)).not.toBeInTheDocument();
  });

  it("disables the controls with a reason when actions are unavailable", () => {
    render(<ReviewReplyCard body="hi" disabledReason="Approvals are read-only here" />);
    expect(screen.getByRole("button", { name: /approve & send/i })).toBeDisabled();
    expect(screen.getByText(/Approvals are read-only here/i)).toBeInTheDocument();
  });

  it("hides action controls once the reply is no longer awaiting review", () => {
    render(<ReviewReplyCard body="hi" status="sent" onApprove={vi.fn()} />);
    // A sent reply is terminal — no approve control, just the status.
    expect(screen.queryByRole("button", { name: /approve & send/i })).toBeDisabled();
    expect(screen.getAllByText(/Sent/i).length).toBeGreaterThan(0);
  });

  it("renders a confidence badge when a real level is supplied", () => {
    render(<ReviewReplyCard body="hi" confidence="high" />);
    expect(screen.getByLabelText(/high confidence/i)).toBeInTheDocument();
  });

  it("shows per-source evidence cards when sources are supplied", () => {
    render(
      <ReviewReplyCard
        body="hi"
        groundedCount={2}
        groundingSources={[
          { title: "Saturday hours", type: "kb", snippet: "9am–2pm" },
          { title: "Cut + beard", type: "kb", snippet: "45 min" },
        ]}
      />,
    );
    expect(screen.getByText("Saturday hours")).toBeInTheDocument();
    expect(screen.getByText("9am–2pm")).toBeInTheDocument();
    expect(screen.getByText("Cut + beard")).toBeInTheDocument();
    // The count summary is replaced by the per-source cards.
    expect(screen.queryByText(/Grounded in 2 knowledge sources/i)).not.toBeInTheDocument();
  });

  it("falls back to the count summary when sources are empty", () => {
    render(<ReviewReplyCard body="hi" groundedCount={3} groundingSources={[]} />);
    expect(screen.getByText(/Grounded in 3 knowledge sources/i)).toBeInTheDocument();
  });

  it("maps generation_status to the working line: working animates, complete rests", () => {
    const { container, rerender } = render(
      <ReviewReplyCard body="hi" generationStatus="working" />,
    );
    expect(container.querySelector(".animate-working-line")).toBeInTheDocument();

    rerender(<ReviewReplyCard body="hi" generationStatus="complete" />);
    expect(container.querySelector(".animate-working-line")).not.toBeInTheDocument();

    rerender(<ReviewReplyCard body="hi" generationStatus="failed" />);
    expect(container.querySelector(".animate-working-line")).not.toBeInTheDocument();
  });
});
