"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, ArrowLeft, History, Pencil, Plus, Tag, Trash2, Users } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { CustomerFormDialog } from "@/components/customer-form-dialog";
import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { IconTooltip } from "@/components/ui/tooltip";
import { useCustomer, useCustomerTimeline, useDeleteCustomer } from "@/hooks/use-customers";
import { useCreateLead, useDeleteLead, useUpdateLead } from "@/hooks/use-leads";
import { ApiError } from "@/lib/api";
import { LEAD_STAGES, STAGE_BADGE_VARIANT } from "@/lib/leads";
import type { CustomerLead, LeadEventType, TimelineItem, TimelineLeadEventItem } from "@/lib/types";
import { cn, formatRelativeTime, toDateInputValue } from "@/lib/utils";

const TIMELINE_PAGE_SIZE = 20;

export function CustomerDetailPane({
  customerId,
  onBack,
}: {
  customerId: string | null;
  onBack: () => void;
}) {
  const { data: customer, isLoading, isError, error, refetch } = useCustomer(customerId);
  const { toast } = useToast();
  const [isEditing, setIsEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const deleteCustomer = useDeleteCustomer();

  async function handleDelete() {
    if (!customer) return;
    try {
      await deleteCustomer.mutateAsync(customer.id);
      toast({ title: "Customer deleted" });
      setConfirmDelete(false);
      onBack();
    } catch (err) {
      toast({
        title: "Couldn't delete customer",
        description:
          err instanceof ApiError ? err.message : "Something went wrong — please try again.",
        variant: "destructive",
      });
      setConfirmDelete(false);
    }
  }

  if (customerId === null) {
    return (
      <Card className="hidden min-h-[420px] lg:flex">
        <CardContent className="flex w-full items-center justify-center p-6">
          <EmptyState
            icon={Users}
            title="No customer selected"
            description="Select a customer to view their profile, pipeline, and timeline."
            className="border-0"
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-center gap-3 border-b px-4 py-3">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            aria-label="Back to customers"
            onClick={onBack}
          >
            <ArrowLeft />
          </Button>
          {isLoading && <Skeleton className="h-5 w-32" />}
          {isError && (
            <EmptyState
              icon={AlertTriangle}
              title="Couldn't load customer"
              description={error instanceof Error ? error.message : "Something went wrong."}
              action={
                <Button size="sm" onClick={() => refetch()}>
                  Retry
                </Button>
              }
              className="border-0 py-4"
            />
          )}
          {!isLoading && !isError && customer && (
            <>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {customer.display_name || customer.wa_phone}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {[
                    customer.company,
                    customer.wa_phone,
                    customer.email,
                    `${customer.conversation_count} conversation${customer.conversation_count === 1 ? "" : "s"}`,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              <div className="flex shrink-0 gap-1">
                <IconTooltip label="Edit customer">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Edit customer"
                    onClick={() => setIsEditing(true)}
                  >
                    <Pencil />
                  </Button>
                </IconTooltip>
                <IconTooltip label="Delete customer">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Delete customer"
                    className="text-destructive hover:text-destructive"
                    onClick={() => setConfirmDelete(true)}
                  >
                    <Trash2 />
                  </Button>
                </IconTooltip>
              </div>
            </>
          )}
        </div>
      </Card>

      {!isLoading && !isError && customer && (
        <>
          <LeadCard customerId={customer.id} lead={customer.lead} />
          <TimelineCard customerId={customer.id} />
        </>
      )}

      <CustomerFormDialog
        target={isEditing && customer ? customer : null}
        onOpenChange={(open) => !open && setIsEditing(false)}
      />
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete this customer?"
        description="This removes the customer and all their conversations, leads, and appointment history. This can't be undone."
        onConfirm={handleDelete}
        isPending={deleteCustomer.isPending}
      />
    </div>
  );
}

function LeadCard({ customerId, lead }: { customerId: string; lead: CustomerLead | null }) {
  const { toast } = useToast();
  const [isCreating, setIsCreating] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const deleteLead = useDeleteLead();

  async function handleDelete() {
    if (!lead) return;
    try {
      await deleteLead.mutateAsync(lead.id);
      toast({ title: "Lead deleted" });
    } catch (err) {
      toast({
        title: "Couldn't delete lead",
        description: err instanceof ApiError ? err.message : "Something went wrong — please try again.",
        variant: "destructive",
      });
    }
    setConfirmDelete(false);
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Lead</CardTitle>
        {lead && (
          <IconTooltip label="Delete lead">
            <Button
              variant="ghost"
              size="icon"
              aria-label="Delete lead"
              className="text-destructive hover:text-destructive"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 />
            </Button>
          </IconTooltip>
        )}
      </CardHeader>
      <CardContent>
        {lead === null && !isCreating && (
          <EmptyState
            icon={Tag}
            title="No lead yet"
            description="Track this customer through your sales pipeline."
            action={
              <Button size="sm" onClick={() => setIsCreating(true)}>
                <Plus /> Create lead
              </Button>
            }
            className="border-0 py-8"
          />
        )}
        {lead === null && isCreating && (
          <LeadForm
            mode="create"
            customerId={customerId}
            onDone={() => setIsCreating(false)}
            onCancel={() => setIsCreating(false)}
          />
        )}
        {lead !== null && <LeadForm mode="edit" customerId={customerId} lead={lead} />}
      </CardContent>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete this lead?"
        description="This removes the lead and its full history. This can't be undone."
        onConfirm={handleDelete}
        isPending={deleteLead.isPending}
      />
    </Card>
  );
}

const leadFormSchema = z.object({
  stage: z.enum([
    "new",
    "contacted",
    "qualified",
    "proposal_sent",
    "negotiation",
    "won",
    "lost",
  ]),
  source: z.string(),
  estimated_value: z.string(),
  notes: z.string(),
  next_follow_up_at: z.string(),
});

type LeadFormValues = z.infer<typeof leadFormSchema>;

function LeadForm({
  mode,
  customerId,
  lead,
  onDone,
  onCancel,
}: {
  mode: "create" | "edit";
  customerId: string;
  lead?: CustomerLead | null;
  onDone?: () => void;
  onCancel?: () => void;
}) {
  const { toast } = useToast();
  const createLead = useCreateLead();
  const updateLead = useUpdateLead();
  const isPending = createLead.isPending || updateLead.isPending;

  const { register, handleSubmit } = useForm<LeadFormValues>({
    resolver: zodResolver(leadFormSchema),
    defaultValues: {
      stage: lead?.stage ?? "new",
      source: lead?.source ?? "",
      estimated_value: lead?.estimated_value != null ? String(lead.estimated_value) : "",
      notes: lead?.notes ?? "",
      next_follow_up_at: toDateInputValue(lead?.next_follow_up_at ?? null),
    },
  });

  async function onSubmit(values: LeadFormValues) {
    const payload = {
      stage: values.stage,
      source: values.source.trim() ? values.source.trim() : null,
      estimated_value: values.estimated_value.trim() ? Number(values.estimated_value) : null,
      notes: values.notes.trim() ? values.notes.trim() : null,
      next_follow_up_at: values.next_follow_up_at.trim() || null,
    };
    try {
      if (mode === "create") {
        await createLead.mutateAsync({ customer_id: customerId, ...payload });
        toast({ title: "Lead created", variant: "success" });
      } else if (lead) {
        await updateLead.mutateAsync({ id: lead.id, payload });
        toast({ title: "Lead updated", variant: "success" });
      }
      onDone?.();
    } catch (err) {
      toast({
        title: mode === "create" ? "Couldn't create lead" : "Couldn't update lead",
        description: err instanceof ApiError ? err.message : "Something went wrong — please try again.",
        variant: "destructive",
      });
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      {lead && (
        <div className="flex items-center justify-between gap-2">
          <Badge variant={STAGE_BADGE_VARIANT[lead.stage]} className="w-fit">
            {LEAD_STAGES.find((s) => s.value === lead.stage)?.label ?? lead.stage}
          </Badge>
          <span className="text-xs text-muted-foreground">
            Created {formatRelativeTime(lead.created_at)}
          </span>
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Stage</span>
          <Select aria-label="Stage" {...register("stage")}>
            {LEAD_STAGES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Source</span>
          <Input placeholder="e.g. whatsapp, referral" {...register("source")} />
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Estimated value</span>
          <Input type="number" step="0.01" placeholder="0.00" {...register("estimated_value")} />
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Next follow-up</span>
          <Input type="date" aria-label="Next follow-up" {...register("next_follow_up_at")} />
        </label>
      </div>
      <label className="block space-y-1.5">
        <span className="text-sm font-medium">Notes</span>
        <Textarea rows={3} placeholder="Notes about this lead…" {...register("notes")} />
      </label>
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={isPending}>
          {isPending ? "Saving…" : mode === "create" ? "Create lead" : "Save changes"}
        </Button>
        {mode === "create" && (
          <Button type="button" variant="outline" size="sm" onClick={onCancel} disabled={isPending}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}

const LEAD_EVENT_COPY: Record<LeadEventType, (item: TimelineLeadEventItem) => string> = {
  lead_created: (item) => `Lead created (${item.to_value ?? "new"})`,
  stage_change: (item) => `Stage changed: ${item.from_value ?? "—"} → ${item.to_value ?? "—"}`,
  notes_updated: () => "Notes updated",
  follow_up_set: (item) =>
    item.to_value
      ? `Follow-up set for ${new Date(item.to_value).toLocaleDateString()}`
      : "Follow-up cleared",
  assigned: (item) => (item.to_value ? "Lead assigned" : "Lead unassigned"),
};

function TimelineCard({ customerId }: { customerId: string }) {
  const [offset, setOffset] = useState(0);
  const { data, isLoading, isError, error, refetch } = useCustomerTimeline(customerId, {
    limit: TIMELINE_PAGE_SIZE,
    offset,
  });
  const items = data?.data ?? [];
  const total = data?.meta.total ?? 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Timeline</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && (
          <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        )}

        {isError && (
          <EmptyState
            icon={AlertTriangle}
            title="Couldn't load timeline"
            description={error instanceof Error ? error.message : "Something went wrong."}
            action={
              <Button size="sm" onClick={() => refetch()}>
                Retry
              </Button>
            }
            className="border-0 py-8"
          />
        )}

        {!isLoading && !isError && items.length === 0 && (
          <EmptyState
            icon={History}
            title="No activity yet"
            description="Messages and CRM updates for this customer will appear here."
            className="border-0 py-8"
          />
        )}

        {!isLoading && !isError && items.length > 0 && (
          <ul className="space-y-3">
            {items.map((item) => (
              <TimelineRow key={`${item.type}-${item.id}`} item={item} />
            ))}
          </ul>
        )}

        {total > TIMELINE_PAGE_SIZE && (
          <div className="flex items-center justify-between pt-2 text-xs text-muted-foreground">
            <span>
              {offset + 1}–{Math.min(offset + TIMELINE_PAGE_SIZE, total)} of {total}
            </span>
            <div className="flex gap-1">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - TIMELINE_PAGE_SIZE))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={offset + TIMELINE_PAGE_SIZE >= total}
                onClick={() => setOffset(offset + TIMELINE_PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TimelineRow({ item }: { item: TimelineItem }) {
  if (item.type === "message") {
    return (
      <li
        className={cn(
          "flex flex-col gap-1",
          item.direction === "outbound" ? "items-end" : "items-start",
        )}
      >
        <div
          className={cn(
            "max-w-[85%] rounded-md px-3 py-2 text-sm",
            item.direction === "outbound" ? "bg-secondary text-secondary-foreground" : "bg-muted",
          )}
        >
          {item.body}
        </div>
        <span className="text-xs text-muted-foreground">{formatRelativeTime(item.created_at)}</span>
      </li>
    );
  }

  return (
    <li className="flex items-start gap-2 rounded-md border border-dashed px-3 py-2 text-sm">
      <Tag className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
      <div className="flex-1">
        <p>{LEAD_EVENT_COPY[item.event_type](item)}</p>
        <span className="text-xs text-muted-foreground">{formatRelativeTime(item.created_at)}</span>
      </div>
    </li>
  );
}
