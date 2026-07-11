"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { useCreateLead } from "@/hooks/use-leads";
import { ApiError } from "@/lib/api";
import { LEAD_STAGES } from "@/lib/leads";
import type { Lead } from "@/lib/types";

const newLeadSchema = z.object({
  display_name: z.string().trim().min(1, "Full name is required"),
  company: z.string().trim(),
  email: z.string().trim().email("Enter a valid email address").or(z.literal("")),
  wa_phone: z.string().trim(),
  stage: z.enum([
    "new",
    "contacted",
    "qualified",
    "proposal_sent",
    "negotiation",
    "won",
    "lost",
  ]),
  source: z.string().trim(),
  estimated_value: z.string().trim(),
  next_follow_up_at: z.string().trim(),
  notes: z.string().trim(),
});

type NewLeadFormValues = z.infer<typeof newLeadSchema>;

// Creates a Lead from scratch — no customer needs to already exist. The
// backend resolves/creates the customer (match by phone, then email, else
// create new) before creating the lead; see app/services/customers.py's
// resolve_or_create_customer (Sprint 38).
export function NewLeadDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (lead: Lead) => void;
}) {
  const { toast } = useToast();
  const createLead = useCreateLead();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<NewLeadFormValues>({
    resolver: zodResolver(newLeadSchema),
    defaultValues: {
      display_name: "",
      company: "",
      email: "",
      wa_phone: "",
      stage: "new",
      source: "",
      estimated_value: "",
      next_follow_up_at: "",
      notes: "",
    },
  });

  async function onSubmit(values: NewLeadFormValues) {
    try {
      const lead = await createLead.mutateAsync({
        display_name: values.display_name.trim(),
        company: values.company.trim() || null,
        email: values.email.trim() || null,
        wa_phone: values.wa_phone.trim() || null,
        stage: values.stage,
        source: values.source.trim() || null,
        estimated_value: values.estimated_value.trim() ? Number(values.estimated_value) : null,
        next_follow_up_at: values.next_follow_up_at.trim() || null,
        notes: values.notes.trim() || null,
      });
      toast({ title: "Lead created", variant: "success" });
      reset();
      onCreated(lead);
    } catch {
      // surfaced below via createLead.error
    }
  }

  function handleOpenChange(next: boolean) {
    if (createLead.isPending) return;
    if (!next) reset();
    onOpenChange(next);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      {open && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New lead</DialogTitle>
            <DialogDescription>
              Add a lead without waiting for a WhatsApp message. If the phone or email matches an
              existing customer, that customer is reused — otherwise a new one is created.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">Full name</span>
              <Input placeholder="Jordan Lee" {...register("display_name")} />
              {errors.display_name && (
                <span className="block text-xs text-destructive">
                  {errors.display_name.message}
                </span>
              )}
            </label>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block space-y-1.5">
                <span className="text-sm font-medium">Company</span>
                <Input placeholder="Acme Co" {...register("company")} />
              </label>
              <label className="block space-y-1.5">
                <span className="text-sm font-medium">Email</span>
                <Input type="email" placeholder="jordan@example.com" {...register("email")} />
                {errors.email && (
                  <span className="block text-xs text-destructive">{errors.email.message}</span>
                )}
              </label>
              <label className="block space-y-1.5">
                <span className="text-sm font-medium">Phone</span>
                <Input placeholder="+1 555 987 6543" {...register("wa_phone")} />
              </label>
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
                <Input placeholder="e.g. referral, website" {...register("source")} />
              </label>
              <label className="block space-y-1.5">
                <span className="text-sm font-medium">Estimated value</span>
                <Input
                  type="number"
                  step="0.01"
                  placeholder="0.00"
                  {...register("estimated_value")}
                />
              </label>
              <label className="block space-y-1.5 sm:col-span-2">
                <span className="text-sm font-medium">Follow-up date</span>
                <Input
                  type="date"
                  aria-label="Follow-up date"
                  {...register("next_follow_up_at")}
                />
              </label>
            </div>

            <label className="block space-y-1.5">
              <span className="text-sm font-medium">Notes</span>
              <Textarea rows={3} placeholder="Anything worth remembering…" {...register("notes")} />
            </label>

            {createLead.error != null && (
              <p className="text-sm text-destructive">
                {createLead.error instanceof ApiError
                  ? createLead.error.message
                  : "Something went wrong — please try again."}
              </p>
            )}

            <DialogFooter>
              <Button type="submit" disabled={createLead.isPending}>
                {createLead.isPending ? "Creating…" : "Create lead"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      )}
    </Dialog>
  );
}
