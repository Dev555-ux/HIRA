"use client";

import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useOnboardingStatus } from "@/hooks/use-onboarding";
import { useSettings, useUpdateSettings } from "@/hooks/use-settings";
import { ApiError } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import type { AiReplyMode } from "@/lib/types";
import { cn, describeWhatsAppConnection } from "@/lib/utils";

export default function SettingsPage() {
  const { mocked } = useAuthContext();
  const { data: onboarding } = useOnboardingStatus();
  const whatsapp = describeWhatsAppConnection(onboarding?.business?.whatsapp_connection_status);
  const business = onboarding?.business;

  return (
    <>
      <PageHeader title="Settings" description="Configure your business and integrations." />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Business information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Editing business name and industry is coming soon — for now these are set at
              signup.
            </p>
            <Row label="Business name" value={business?.name ?? "—"} />
            <Row label="Industry" value={business?.industry ?? "Not set"} />
            <Row
              label="Timezone"
              value={
                <span className="flex items-center gap-2">
                  {business?.timezone ?? "UTC"}
                  <Button asChild size="sm" variant="ghost" className="h-auto p-0 underline">
                    <Link href="/calendar">Change</Link>
                  </Button>
                </span>
              }
            />
          </CardContent>
        </Card>

        <AiReplyModeCard />

        <Card>
          <CardHeader>
            <CardTitle className="text-base">AI settings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row label="Model" value="llama-3.3-70b-versatile" />
            <Row label="Embeddings" value="local bge-small (384d)" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Integration status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row label="Clerk auth" value={<Badge variant={mocked ? "warning" : "success"}>{mocked ? "Mock (dev)" : "Connected"}</Badge>} />
            <Row label="Groq" value={<Badge variant="success">Live</Badge>} />
            <Row
              label="WhatsApp"
              value={<Badge variant={whatsapp.variant}>{whatsapp.label}</Badge>}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">WhatsApp configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Connecting your own WhatsApp number is coming soon.
            </p>
            <Field label="Phone number ID" placeholder="Not connected yet" disabled />
            <Field label="Access token" placeholder="Not connected yet" disabled />
          </CardContent>
        </Card>
      </div>
    </>
  );
}

const MODE_OPTIONS: { value: AiReplyMode; title: string; description: string }[] = [
  {
    value: "assisted",
    title: "Assisted",
    description: "Human approves every reply.",
  },
  {
    value: "autonomous",
    title: "Autonomous",
    description: "AI replies immediately on WhatsApp.",
  },
];

function AiReplyModeCard() {
  const { data, isLoading, isError, refetch } = useSettings();
  const updateSettings = useUpdateSettings();
  const { toast } = useToast();
  const [selected, setSelected] = useState<AiReplyMode | null>(null);

  useEffect(() => {
    if (data) setSelected(data.mode);
  }, [data]);

  const current = selected ?? data?.mode ?? null;
  const isDirty = data != null && current != null && current !== data.mode;
  const isSaving = updateSettings.isPending;
  const controlsDisabled = isLoading || isSaving;

  async function handleSave() {
    if (current == null) return;
    try {
      await updateSettings.mutateAsync({ mode: current });
      toast({
        title: "Settings saved",
        description: "AI Reply Mode updated.",
        variant: "success",
      });
    } catch (err) {
      toast({
        title: "Couldn't save settings",
        description:
          err instanceof ApiError ? err.message : "Something went wrong — please try again.",
        variant: "destructive",
      });
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">AI Reply Mode</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : isError ? (
          <EmptyState
            icon={AlertTriangle}
            title="Couldn't load AI Reply Mode"
            description="Something went wrong — please try again."
            action={
              <Button size="sm" onClick={() => refetch()}>
                Retry
              </Button>
            }
            className="border-0 py-6"
          />
        ) : (
          <div className="space-y-3" role="radiogroup" aria-label="AI Reply Mode">
            {MODE_OPTIONS.map((option) => (
              <ModeOption
                key={option.value}
                {...option}
                checked={current === option.value}
                disabled={controlsDisabled}
                onChange={setSelected}
              />
            ))}
          </div>
        )}
        {!isError && (
          <Button size="sm" onClick={handleSave} disabled={controlsDisabled || !isDirty}>
            {isSaving ? "Saving…" : "Save"}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function ModeOption({
  value,
  title,
  description,
  checked,
  disabled,
  onChange,
}: {
  value: AiReplyMode;
  title: string;
  description: string;
  checked: boolean;
  disabled: boolean;
  onChange: (value: AiReplyMode) => void;
}) {
  return (
    <label
      className={cn(
        "flex items-start gap-3 rounded-lg border p-4 transition-colors",
        checked ? "border-primary bg-accent/50" : "border-input hover:bg-accent/30",
        disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer",
      )}
    >
      <input
        type="radio"
        name="ai-reply-mode"
        value={value}
        checked={checked}
        disabled={disabled}
        onChange={() => onChange(value)}
        className="mt-1 size-4 accent-primary disabled:cursor-not-allowed"
      />
      <span className="space-y-0.5">
        <span className="block text-sm font-medium">{title}</span>
        <span className="block text-sm text-muted-foreground">{description}</span>
      </span>
    </label>
  );
}

function Field({
  label,
  ...props
}: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium">{label}</span>
      <Input {...props} />
    </label>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span>{value}</span>
    </div>
  );
}
