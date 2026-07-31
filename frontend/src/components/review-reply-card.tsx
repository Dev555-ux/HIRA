"use client";

import { BookOpen, Check, Pencil, X } from "lucide-react";
import { useState } from "react";
import { ActivityDot, type ActivityState } from "@/components/ui/activity-dot";
import { ReviewSurface } from "@/components/ui/ai-surface";
import { ConfidenceBadge, type ConfidenceLevel } from "@/components/ui/confidence-badge";
import { EvidenceCard } from "@/components/ui/evidence-card";
import { StatusPill } from "@/components/ui/status-pill";
import { WorkingIndicator, type WorkingState } from "@/components/ui/working-indicator";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

// The AI review experience from HIRA EXPERIENCE FILM (Scenes 3 & 5) and
// DESIGN-MOTION-001 §9, composed from the PR2 primitives. Presentational and
// controlled: the caller passes the draft + real action handlers, so this owns
// no data-fetching and no mutation logic (that stays in the approval hooks —
// use-pending.ts). It deliberately does NOT decide where it sits in the Inbox
// layout; wiring is a follow-up once DESIGN-SCREENBOOK-001 lands.
//
// Honesty over fabrication (per the PR brief): the backend today exposes the
// grounding *count* (ai_meta.retrieved_count) but no per-source content and no
// confidence score, and there is no live generation/streaming signal. So this
// shows a grounding-count summary, renders ConfidenceBadge only when a score is
// actually supplied, and uses WorkingIndicator only in its honest *resting*
// state — never a fabricated "thinking" animation. See the TODOs below.

export type ReviewStatus = "waiting" | "sending" | "sent" | "escalated" | "error";

const STATUS_META: Record<
  ReviewStatus,
  { pill: ActivityState; line: WorkingState; label: string }
> = {
  waiting: { pill: "waiting", line: "waiting", label: "Awaiting your review" },
  sending: { pill: "working", line: "working", label: "Sending…" },
  sent: { pill: "success", line: "idle", label: "Sent" },
  escalated: { pill: "waiting", line: "idle", label: "Escalated to you" },
  error: { pill: "error", line: "idle", label: "Couldn't send" },
};

export interface ReviewReplyCardProps {
  /** The AI-drafted reply awaiting review. */
  body: string;
  /** Employee/agent name for the header, e.g. "Maya". Falls back to a generic label. */
  authorLabel?: string;
  /** Review lifecycle state. Defaults to "waiting" (the Assisted-mode gate). */
  status?: ReviewStatus;
  /** ai_meta.retrieved_count — real grounding count. null/0 hides the summary. */
  groundedCount?: number | null;
  /** Confidence is shown ONLY when a real score is supplied; today the backend
   *  provides none, so callers pass undefined and no badge renders (no fabrication). */
  confidence?: ConfidenceLevel;
  onApprove?: () => void;
  onReject?: () => void;
  /** Called with the edited text when the founder saves an edit. */
  onEdit?: (nextBody: string) => void;
  /** An action is in flight — controls disable, nothing is faked. */
  pending?: boolean;
  /** When actions are unavailable, controls disable and this explains why (a11y + tooltip). */
  disabledReason?: string;
  className?: string;
}

export function ReviewReplyCard({
  body,
  authorLabel,
  status = "waiting",
  groundedCount,
  confidence,
  onApprove,
  onReject,
  onEdit,
  pending = false,
  disabledReason,
  className,
}: ReviewReplyCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(body);

  const meta = STATUS_META[status];
  const actionable = status === "waiting" && !disabledReason;
  const controlsDisabled = pending || !actionable;

  function startEdit() {
    setDraft(body);
    setIsEditing(true);
  }
  function saveEdit() {
    onEdit?.(draft);
    setIsEditing(false);
  }

  return (
    <ReviewSurface
      role="group"
      className={cn("space-y-3 p-4", className)}
      aria-label="AI reply pending your review"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="type-caption font-medium text-muted-foreground">
          {authorLabel ? `${authorLabel} drafted a reply` : "Drafted reply"}
        </span>
        <div className="flex items-center gap-2">
          {/* Confidence renders only when a real score exists (none today). */}
          {confidence && <ConfidenceBadge level={confidence} />}
          <StatusPill state={meta.pill}>{meta.label}</StatusPill>
        </div>
      </div>

      {/* Honest resting/working line — the draft "comes to a stop at the gate"
          (DESIGN-MOTION-001 §6.9). Never a fabricated "thinking" pass. */}
      <WorkingIndicator state={meta.line} label={meta.label} />

      {isEditing ? (
        <div className="space-y-2">
          <label htmlFor="review-draft" className="sr-only">
            Edit reply
          </label>
          <Textarea
            id="review-draft"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="min-h-24"
          />
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={() => setIsEditing(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={saveEdit} disabled={pending || draft.trim().length === 0}>
              Save
            </Button>
          </div>
        </div>
      ) : (
        <p className="type-body whitespace-pre-line text-foreground">{body}</p>
      )}

      {/* Grounding: real count from ai_meta.retrieved_count. Per-source titles/
          snippets need an API that doesn't exist yet — TODO: swap this summary
          for one EvidenceCard per source once grounding content is exposed. */}
      {typeof groundedCount === "number" && groundedCount > 0 && (
        <EvidenceCard
          source={`Grounded in ${groundedCount} knowledge source${groundedCount === 1 ? "" : "s"}`}
          icon={<BookOpen />}
        />
      )}

      {!isEditing && (
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <ActivityDot state={meta.pill} />
            <span className="type-caption text-muted-foreground">
              {disabledReason ?? (actionable ? "Nothing sends without you" : meta.label)}
            </span>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="ghost"
              onClick={onReject}
              disabled={controlsDisabled || !onReject}
              title={disabledReason}
            >
              <X /> Reject
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={startEdit}
              disabled={controlsDisabled || !onEdit}
              title={disabledReason}
            >
              <Pencil /> Edit
            </Button>
            <Button
              size="sm"
              onClick={onApprove}
              disabled={controlsDisabled || !onApprove}
              title={disabledReason}
            >
              <Check /> Approve &amp; send
            </Button>
          </div>
        </div>
      )}
    </ReviewSurface>
  );
}
