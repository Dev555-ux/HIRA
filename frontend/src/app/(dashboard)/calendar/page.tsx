"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, CalendarCheck, ExternalLink, Unlink } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusPill } from "@/components/ui/status-pill";
import { useToast } from "@/components/ui/toast";
import {
  useCalendarSettings,
  useCalendarStatus,
  useDisconnectCalendar,
  useStartCalendarConnect,
  useUpdateCalendarSettings,
} from "@/hooks/use-calendar";
import { ApiError } from "@/lib/api";

const DAYS: { key: "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun"; label: string }[] = [
  { key: "mon", label: "Monday" },
  { key: "tue", label: "Tuesday" },
  { key: "wed", label: "Wednesday" },
  { key: "thu", label: "Thursday" },
  { key: "fri", label: "Friday" },
  { key: "sat", label: "Saturday" },
  { key: "sun", label: "Sunday" },
];

const dayHoursSchema = z.object({
  enabled: z.boolean(),
  open: z.string(),
  close: z.string(),
});

const settingsSchema = z.object({
  timezone: z.string().trim().min(1, "Timezone is required"),
  mon: dayHoursSchema,
  tue: dayHoursSchema,
  wed: dayHoursSchema,
  thu: dayHoursSchema,
  fri: dayHoursSchema,
  sat: dayHoursSchema,
  sun: dayHoursSchema,
});

type SettingsFormValues = z.infer<typeof settingsSchema>;

function CalendarConnectionStatusFromQuery() {
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const qc = useQueryClient();

  useEffect(() => {
    const status = searchParams.get("calendar");
    if (status === "connected") {
      toast({ title: "Google Sync enabled", variant: "success" });
      qc.invalidateQueries({ queryKey: ["calendar-status"] });
    } else if (status === "error") {
      toast({
        title: "Couldn't enable Google Sync",
        description: searchParams.get("message") ?? "Something went wrong — please try again.",
        variant: "destructive",
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  return null;
}

export default function CalendarPage() {
  return (
    <>
      <PageHeader
        title="HIRA Calendar"
        description="Manages your appointments and availability automatically. Optionally connect Google Calendar to keep everything in sync."
      />
      <Suspense fallback={null}>
        <CalendarConnectionStatusFromQuery />
      </Suspense>

      <div className="space-y-4">
        <ConnectionCard />
        <SettingsCard />
      </div>
    </>
  );
}

// Sprint 79: HIRA Calendar is the product's own always-on scheduling system
// (Sprint 78's InternalSchedulerProvider, promoted from fallback to the
// default experience) — Google Calendar is now an optional sync layer on
// top of it, not a prerequisite. This card never shows a "Not connected"
// warning; the un-synced state is simply "HIRA Calendar, Active."
function ConnectionCard() {
  const { toast } = useToast();
  const { data: status, isPending, isError, refetch } = useCalendarStatus();
  const startConnect = useStartCalendarConnect();
  const disconnect = useDisconnectCalendar();
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);

  async function handleConnect() {
    try {
      const { authorization_url } = await startConnect.mutateAsync();
      window.location.href = authorization_url;
    } catch (err) {
      toast({
        title: "Couldn't start connecting Google Calendar",
        description: err instanceof ApiError ? err.message : "Something went wrong — please try again.",
        variant: "destructive",
      });
    }
  }

  async function handleDisconnect() {
    try {
      await disconnect.mutateAsync();
      toast({ title: "Google Sync disabled — HIRA Calendar is managing your schedule now." });
    } catch (err) {
      toast({
        title: "Couldn't disconnect",
        description: err instanceof ApiError ? err.message : "Something went wrong — please try again.",
        variant: "destructive",
      });
    }
    setConfirmDisconnect(false);
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">HIRA Calendar</CardTitle>
        {!isPending && !isError && (
          <StatusPill state="success">
            {status?.connected ? "Google Sync Enabled" : "Active"}
          </StatusPill>
        )}
      </CardHeader>
      <CardContent>
        {isPending ? (
          <Skeleton className="h-9 w-40" />
        ) : isError ? (
          <EmptyState
            icon={AlertTriangle}
            title="Couldn't load calendar status"
            description="Something went wrong — please try again."
            action={
              <Button size="sm" onClick={() => refetch()}>
                Retry
              </Button>
            }
            className="border-0 py-6"
          />
        ) : status?.connected ? (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Synced to Google Calendar:{" "}
              <span className="font-medium text-foreground">{status.calendar_id}</span>
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmDisconnect(true)}
              disabled={disconnect.isPending}
            >
              <Unlink /> Disconnect Google Sync
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              HIRA Calendar manages your appointments automatically. You can optionally connect
              Google Calendar in the future for synchronization.
            </p>
            <Button size="sm" onClick={handleConnect} disabled={startConnect.isPending}>
              <ExternalLink /> {startConnect.isPending ? "Connecting…" : "Connect Google Calendar"}
            </Button>
          </div>
        )}
      </CardContent>

      <ConfirmDialog
        open={confirmDisconnect}
        onOpenChange={setConfirmDisconnect}
        title="Disconnect Google Sync?"
        description="HIRA Calendar will keep managing your appointments and availability on its own — nothing already booked is affected."
        confirmLabel="Disconnect"
        onConfirm={handleDisconnect}
        isPending={disconnect.isPending}
      />
    </Card>
  );
}

function SettingsCard() {
  const { toast } = useToast();
  const { data: settings, isPending, isError, refetch } = useCalendarSettings();
  const updateSettings = useUpdateCalendarSettings();

  if (isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Timezone &amp; working hours</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState
            icon={AlertTriangle}
            title="Couldn't load calendar settings"
            description="Something went wrong — please try again."
            action={
              <Button size="sm" onClick={() => refetch()}>
                Retry
              </Button>
            }
            className="border-0 py-6"
          />
        </CardContent>
      </Card>
    );
  }

  if (isPending || !settings) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Timezone &amp; working hours</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-40 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <SettingsForm
      timezone={settings.timezone}
      workingHours={settings.working_hours}
      isPending={updateSettings.isPending}
      onSave={async (values) => {
        const working_hours = Object.fromEntries(
          DAYS.map(({ key }) => [
            key,
            values[key].enabled ? { open: values[key].open, close: values[key].close } : null,
          ]),
        );
        try {
          await updateSettings.mutateAsync({ timezone: values.timezone, working_hours });
          toast({ title: "Calendar settings saved", variant: "success" });
        } catch (err) {
          toast({
            title: "Couldn't save calendar settings",
            description: err instanceof ApiError ? err.message : "Something went wrong — please try again.",
            variant: "destructive",
          });
        }
      }}
    />
  );
}

function SettingsForm({
  timezone,
  workingHours,
  isPending,
  onSave,
}: {
  timezone: string;
  workingHours: Record<string, { open: string; close: string } | null> | null;
  isPending: boolean;
  onSave: (values: SettingsFormValues) => Promise<void>;
}) {
  const defaultDay = (key: string) => {
    const existing = workingHours?.[key];
    return {
      enabled: existing != null,
      open: existing?.open ?? "09:00",
      close: existing?.close ?? "17:00",
    };
  };

  const { register, handleSubmit, watch } = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      timezone,
      mon: defaultDay("mon"),
      tue: defaultDay("tue"),
      wed: defaultDay("wed"),
      thu: defaultDay("thu"),
      fri: defaultDay("fri"),
      sat: defaultDay("sat"),
      sun: defaultDay("sun"),
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Timezone &amp; working hours</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-4 text-sm text-muted-foreground">
          HIRA only offers appointment times inside these hours, in this timezone — closed days
          and hours outside this range are never offered to a customer.
        </p>
        <form onSubmit={handleSubmit(onSave)} className="space-y-4" noValidate>
          <label className="block max-w-xs space-y-1.5">
            <span className="text-sm font-medium">Timezone</span>
            <Input placeholder="e.g. America/New_York" {...register("timezone")} />
          </label>

          <div className="space-y-2">
            <span className="text-sm font-medium">Working hours</span>
            <div className="space-y-2">
              {DAYS.map(({ key, label }) => {
                const enabled = watch(`${key}.enabled`);
                return (
                  <div key={key} className="flex flex-wrap items-center gap-3 rounded-md border p-3">
                    <label className="flex w-32 shrink-0 items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        className="size-4 accent-primary"
                        {...register(`${key}.enabled`)}
                      />
                      {label}
                    </label>
                    {enabled ? (
                      <div className="flex items-center gap-2">
                        <Input type="time" className="w-32" {...register(`${key}.open`)} />
                        <span className="text-sm text-muted-foreground">to</span>
                        <Input type="time" className="w-32" {...register(`${key}.close`)} />
                      </div>
                    ) : (
                      <span className="text-sm text-muted-foreground">Closed</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <Button type="submit" size="sm" disabled={isPending}>
            <CalendarCheck /> {isPending ? "Saving…" : "Save"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
