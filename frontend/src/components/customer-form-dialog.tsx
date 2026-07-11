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
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { useCreateCustomer, useUpdateCustomer } from "@/hooks/use-customers";
import { ApiError } from "@/lib/api";
import type { Customer, CustomerDetail } from "@/lib/types";

const customerFormSchema = z.object({
  display_name: z.string().trim().min(1, "Name is required"),
  wa_phone: z.string().trim(),
  email: z.string().trim().email("Enter a valid email address").or(z.literal("")),
  notes: z.string().trim(),
});

type CustomerFormValues = z.infer<typeof customerFormSchema>;

// "new" opens the create form; a Customer/CustomerDetail opens it pre-filled
// for editing; null keeps the dialog closed.
export type CustomerDialogTarget = Customer | CustomerDetail | "new" | null;

// Manually creating or editing a customer here only ever touches the
// Customer row — it never creates a Lead, Conversation, or Message, and
// never sends WhatsApp (see app/services/customers.py on the backend).
export function CustomerFormDialog({
  target,
  onOpenChange,
}: {
  target: CustomerDialogTarget;
  onOpenChange: (open: boolean) => void;
}) {
  const createCustomer = useCreateCustomer();
  const updateCustomer = useUpdateCustomer();
  const isPending = createCustomer.isPending || updateCustomer.isPending;

  return (
    <Dialog open={target !== null} onOpenChange={(open) => !isPending && onOpenChange(open)}>
      {target !== null && (
        <CustomerForm
          customer={target === "new" ? null : target}
          isPending={isPending}
          error={createCustomer.error ?? updateCustomer.error}
          onSubmit={async (values) => {
            const payload = {
              display_name: values.display_name.trim(),
              wa_phone: values.wa_phone.trim() || null,
              email: values.email.trim() || null,
              notes: values.notes.trim() || null,
            };
            if (target === "new") {
              await createCustomer.mutateAsync(payload);
            } else if (target) {
              await updateCustomer.mutateAsync({ id: target.id, payload });
            }
            onOpenChange(false);
          }}
        />
      )}
    </Dialog>
  );
}

function CustomerForm({
  customer,
  onSubmit,
  isPending,
  error,
}: {
  customer: Customer | CustomerDetail | null;
  onSubmit: (values: CustomerFormValues) => Promise<void>;
  isPending: boolean;
  error: unknown;
}) {
  const { toast } = useToast();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CustomerFormValues>({
    resolver: zodResolver(customerFormSchema),
    defaultValues: {
      display_name: customer?.display_name ?? "",
      wa_phone: customer?.wa_phone ?? "",
      email: customer?.email ?? "",
      notes: customer?.notes ?? "",
    },
  });

  async function handleFormSubmit(values: CustomerFormValues) {
    try {
      await onSubmit(values);
      toast({
        title: customer ? "Customer updated" : "Customer added",
        variant: "success",
      });
    } catch {
      // surfaced below via `error`
    }
  }

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>{customer ? "Edit customer" : "Add customer"}</DialogTitle>
        <DialogDescription>
          {customer
            ? "Update this customer's details."
            : "Add a customer manually — no message, lead, or appointment is created."}
        </DialogDescription>
      </DialogHeader>
      <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4" noValidate>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Name</span>
          <Input placeholder="Jordan Lee" {...register("display_name")} />
          {errors.display_name && (
            <span className="block text-xs text-destructive">{errors.display_name.message}</span>
          )}
        </label>

        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Phone</span>
          <Input placeholder="+1 555 987 6543" {...register("wa_phone")} />
        </label>

        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Email</span>
          <Input type="email" placeholder="jordan@example.com" {...register("email")} />
          {errors.email && (
            <span className="block text-xs text-destructive">{errors.email.message}</span>
          )}
        </label>

        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Notes</span>
          <Textarea rows={3} placeholder="Anything worth remembering…" {...register("notes")} />
        </label>

        {error != null && (
          <p className="text-sm text-destructive">
            {error instanceof ApiError
              ? error.message
              : "Something went wrong — please try again."}
          </p>
        )}

        <DialogFooter>
          <Button type="submit" disabled={isPending}>
            {isPending ? "Saving…" : customer ? "Save changes" : "Add customer"}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
}
