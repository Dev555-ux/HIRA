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
import type { GroundingSource } from "@/lib/types";
import { cn } from "@/lib/utils";

// The AI review experience from HIRA EXPERIENCE FILM (Scenes 3 & 5) and
// DESIGN-MOTION-001 §9, composed from the PR2 primitives. Presentational and
// controlled: the caller passes the draft + real review metadata + action
// handlers, so this owns no data-fetching and no mutation logic (that stays in
// the approval hooks — use-pending.ts).
//
// Honesty over fabrication (per the PR brief): every field is optional and
// rendered only from real backend data. ConfidenceBadge shows only when a real
// level is supplied; grounding shows per-source EvidenceCards when sources
// exist, otherwise a count summary; the WorkingIndicator reflects the real
// generation_status (or, absent it, the review lifecycle) — never a fabricated
// "thinking" animation.

export type ReviewStatus = "waiting" | "sending" | "sent" | "escalated" | "error";
export type GenerationStatus = "complete" | "failed" | "working" | "idle";

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

// generation_status → the working line's activity. The line has no error state
// by design (DESIGN-MOTION-001 §6.1 — foreground-toned body language, not a
// status colour); a failed generation stops the line, and the failure itself is
// carried by the StatusPill/ActivityDot (colour + text). "complete" rests at the
// gate, matching the Assisted-mode "flow to a stop" (§6.9).
const GENERATION_LINE: Record<GenerationStatus, WorkingState> = {
  working: "working",
  idle: "idle",
  complete: "waiting",
  failed: "idle",
};

export interface ReviewReplyCardProps {
  /** The AI-drafted reply awaiting review. */
  body: string;
  /** Employee/agent name for the header, e.g. "Maya". Falls back to a generic label. */
  authorLabel?: string;
  /** Review lifecycle state. Defaults to "waiting" (the Assisted-mode gate). */
  status?: ReviewStatus;
  /** grounding.retrieved_count — real grounding count. null/0 hides the summary. */
  groundedCount?: number | null;
  /** grounding.sources — when present, one EvidenceCard per source instead of
   *  the count summary. Empty/undefined falls back to the count. */
  groundingSources?: GroundingSource[];
  /** Confidence level, shown ONLY when a real one is supplied (undefined/null →
   *  no badge; never fabricated). */
  confidence?: ConfidenceLevel;
  /** Real generation_status; drives the working line. Absent → the line follows
   *  the review lifecycle instead (backward compatible). */
  generationStatus?: GenerationStatus;
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
  groundingSources,
  confidence,
  generationStatus,
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
  // The working line follows the real generation_status when we have it; absent
  // it, it follows the review lifecycle (unchanged, backward-compatible).
  const lineState = generationStatus ? GENERATION_LINE[generationStatus] : meta.line;
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

      {/* Honest working line, driven by the real generation_status when present
          (DESIGN-MOTION-001 §6.9). Never a fabricated "thinking" pass. */}
      <WorkingIndicator state={lineState} label={meta.label} />

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

      {/* Grounding: one EvidenceCard per real source when the backend supplies
          them; otherwise the honest count summary from retrieved_count. */}
      {groundingSources && groundingSources.length > 0 ? (
        <div className="space-y-2">
          {groundingSources.map((source, i) => (
            <EvidenceCard key={i} source={source.title ?? "Knowledge source"} icon={<BookOpen />}>
              {source.snippet ?? undefined}
            </EvidenceCard>
          ))}
        </div>
      ) : (
        typeof groundedCount === "number" &&
        groundedCount > 0 && (
          <EvidenceCard
            source={`Grounded in ${groundedCount} knowledge source${groundedCount === 1 ? "" : "s"}`}
            icon={<BookOpen />}
          />
        )
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
