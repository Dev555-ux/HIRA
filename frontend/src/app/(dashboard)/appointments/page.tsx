"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, CalendarClock, Plus, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import {
  useAppointments,
  useCancelAppointment,
  useCreateAppointment,
  useRescheduleAppointment,
} from "@/hooks/use-appointments";
import { useCustomers } from "@/hooks/use-customers";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { ApiError } from "@/lib/api";
import { APPOINTMENT_STATUS_BADGE, formatAppointmentRange } from "@/lib/appointments";
import type { Appointment, Customer } from "@/lib/types";
import { toDateTimeInputValue } from "@/lib/utils";

const RANGE_DAYS = 30;

export default function AppointmentsPage() {
  const [isCreating, setIsCreating] = useState(false);
  const { from, to } = useMemo(() => {
    const now = new Date();
    return {
      from: now.toISOString(),
      to: new Date(now.getTime() + RANGE_DAYS * 86_400_000).toISOString(),
    };
  }, []);

  const { data: appointments, isLoading, isError, error, isFetching, refetch } = useAppointments({
    from,
    to,
  });

  return (
    <>
      <PageHeader
        title="Appointments"
        description={`Upcoming appointments over the next ${RANGE_DAYS} days.`}
        action={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className={isFetching ? "animate-spin" : ""} />
              Refresh
            </Button>
            <Button size="sm" onClick={() => setIsCreating(true)}>
              <Plus /> New appointment
            </Button>
          </div>
        }
      />

      {isLoading && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      )}

      {isError && (
        <EmptyState
          icon={AlertTriangle}
          title="Couldn't load appointments"
          description={error instanceof Error ? error.message : "Something went wrong."}
          action={
            <Button size="sm" onClick={() => refetch()}>
              Retry
            </Button>
          }
        />
      )}

      {!isLoading && !isError && appointments && appointments.length === 0 && (
        <EmptyState
          icon={CalendarClock}
          title="No upcoming appointments"
          description="Appointments booked by you or the Receptionist will show up here."
          action={
            <Button size="sm" onClick={() => setIsCreating(true)}>
              <Plus /> New appointment
            </Button>
          }
        />
      )}

      {!isLoading && !isError && appointments && appointments.length > 0 && (
        <div className="space-y-3">
          {appointments.map((appointment) => (
            <AppointmentRow key={appointment.id} appointment={appointment} />
          ))}
        </div>
      )}

      <Dialog open={isCreating} onOpenChange={setIsCreating}>
        {isCreating && <CreateAppointmentForm onDone={() => setIsCreating(false)} />}
      </Dialog>
    </>
  );
}

function AppointmentRow({ appointment }: { appointment: Appointment }) {
  const { toast } = useToast();
  const cancelAppointment = useCancelAppointment();
  const [isRescheduling, setIsRescheduling] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const statusBadge = APPOINTMENT_STATUS_BADGE[appointment.status];
  const name =
    appointment.customer?.display_name || appointment.customer?.wa_phone || "Unknown customer";

  async function handleCancel() {
    try {
      await cancelAppointment.mutateAsync(appointment.id);
      toast({ title: "Appointment cancelled" });
    } catch (err) {
      toast({
        title: "Couldn't cancel appointment",
        description: err instanceof ApiError ? err.message : "Something went wrong — please try again.",
        variant: "destructive",
      });
    }
    setConfirmCancel(false);
  }

  return (
    <Card>
      <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div>
          <p className="text-sm font-medium">{name}</p>
          <p className="text-xs text-muted-foreground">
            {formatAppointmentRange(appointment.starts_at, appointment.ends_at)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={statusBadge.variant}>{statusBadge.label}</Badge>
          {appointment.status !== "cancelled" && (
            <>
              <Button variant="outline" size="sm" onClick={() => setIsRescheduling(true)}>
                Reschedule
              </Button>
              <Button variant="outline" size="sm" onClick={() => setConfirmCancel(true)}>
                Cancel
              </Button>
            </>
          )}
        </div>
      </CardContent>

      <Dialog open={isRescheduling} onOpenChange={setIsRescheduling}>
        {isRescheduling && (
          <RescheduleForm appointment={appointment} onDone={() => setIsRescheduling(false)} />
        )}
      </Dialog>

      <ConfirmDialog
        open={confirmCancel}
        onOpenChange={setConfirmCancel}
        title="Cancel this appointment?"
        description="The customer will need to be notified separately — cancelling here does not message them."
        confirmLabel="Cancel appointment"
        cancelLabel="Keep it"
        onConfirm={handleCancel}
        isPending={cancelAppointment.isPending}
      />
    </Card>
  );
}

const rescheduleSchema = z
  .object({
    starts_at: z.string().min(1, "Start time is required"),
    ends_at: z.string().min(1, "End time is required"),
  })
  .refine((values) => new Date(values.ends_at) > new Date(values.starts_at), {
    message: "End time must be after start time",
    path: ["ends_at"],
  });

type RescheduleFormValues = z.infer<typeof rescheduleSchema>;

function RescheduleForm({
  appointment,
  onDone,
}: {
  appointment: Appointment;
  onDone: () => void;
}) {
  const { toast } = useToast();
  const reschedule = useRescheduleAppointment();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RescheduleFormValues>({
    resolver: zodResolver(rescheduleSchema),
    defaultValues: {
      starts_at: toDateTimeInputValue(appointment.starts_at),
      ends_at: toDateTimeInputValue(appointment.ends_at),
    },
  });

  async function onSubmit(values: RescheduleFormValues) {
    try {
      await reschedule.mutateAsync({ id: appointment.id, payload: values });
      toast({ title: "Appointment rescheduled", variant: "success" });
      onDone();
    } catch (err) {
      toast({
        title: "Couldn't reschedule appointment",
        description: err instanceof ApiError ? err.message : "Something went wrong — please try again.",
        variant: "destructive",
      });
    }
  }

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Reschedule appointment</DialogTitle>
      </DialogHeader>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">New start</span>
          <Input type="datetime-local" {...register("starts_at")} />
          {errors.starts_at && (
            <span className="block text-xs text-destructive">{errors.starts_at.message}</span>
          )}
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">New end</span>
          <Input type="datetime-local" {...register("ends_at")} />
          {errors.ends_at && (
            <span className="block text-xs text-destructive">{errors.ends_at.message}</span>
          )}
        </label>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onDone} disabled={reschedule.isPending}>
            Cancel
          </Button>
          <Button type="submit" disabled={reschedule.isPending}>
            {reschedule.isPending ? "Saving…" : "Reschedule"}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
}

const createSchema = z
  .object({
    starts_at: z.string().min(1, "Start time is required"),
    ends_at: z.string().min(1, "End time is required"),
    summary: z.string().trim().min(1, "Summary is required"),
  })
  .refine((values) => new Date(values.ends_at) > new Date(values.starts_at), {
    message: "End time must be after start time",
    path: ["ends_at"],
  });

type CreateFormValues = z.infer<typeof createSchema>;

function CreateAppointmentForm({ onDone }: { onDone: () => void }) {
  const { toast } = useToast();
  const createAppointment = useCreateAppointment();
  const [customerQuery, setCustomerQuery] = useState("");
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const debouncedQuery = useDebouncedValue(customerQuery);
  const { data: customersData } = useCustomers({ search: debouncedQuery || undefined, limit: 5 });
  const customers = debouncedQuery ? (customersData?.data ?? []) : [];

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CreateFormValues>({ resolver: zodResolver(createSchema) });

  async function onSubmit(values: CreateFormValues) {
    if (!selectedCustomer) {
      toast({ title: "Select a customer first", variant: "destructive" });
      return;
    }
    try {
      await createAppointment.mutateAsync({ customer_id: selectedCustomer.id, ...values });
      toast({ title: "Appointment booked", variant: "success" });
      onDone();
    } catch (err) {
      toast({
        title: "Couldn't book appointment",
        description: err instanceof ApiError ? err.message : "Something went wrong — please try again.",
        variant: "destructive",
      });
    }
  }

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>New appointment</DialogTitle>
      </DialogHeader>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <div className="space-y-1.5">
          <span className="text-sm font-medium">Customer</span>
          {selectedCustomer ? (
            <div className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
              <span>{selectedCustomer.display_name || selectedCustomer.wa_phone}</span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setSelectedCustomer(null)}
              >
                Change
              </Button>
            </div>
          ) : (
            <div className="space-y-1">
              <Input
                placeholder="Search customers by name or phone…"
                value={customerQuery}
                onChange={(e) => setCustomerQuery(e.target.value)}
              />
              {customers.length > 0 && (
                <ul className="max-h-40 overflow-y-auto rounded-md border">
                  {customers.map((c) => (
                    <li key={c.id}>
                      <button
                        type="button"
                        className="block w-full px-3 py-2 text-left text-sm hover:bg-accent"
                        onClick={() => {
                          setSelectedCustomer(c);
                          setCustomerQuery("");
                        }}
                      >
                        {c.display_name || c.wa_phone}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Summary</span>
          <Input placeholder="e.g. Dental cleaning" {...register("summary")} />
          {errors.summary && (
            <span className="block text-xs text-destructive">{errors.summary.message}</span>
          )}
        </label>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">Start</span>
            <Input type="datetime-local" {...register("starts_at")} />
            {errors.starts_at && (
              <span className="block text-xs text-destructive">{errors.starts_at.message}</span>
            )}
          </label>
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">End</span>
            <Input type="datetime-local" {...register("ends_at")} />
            {errors.ends_at && (
              <span className="block text-xs text-destructive">{errors.ends_at.message}</span>
            )}
          </label>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={onDone}
            disabled={createAppointment.isPending}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={createAppointment.isPending}>
            {createAppointment.isPending ? "Booking…" : "Book appointment"}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
}
