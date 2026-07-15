"use client";

import {
  Activity,
  AlertTriangle,
  BookOpen,
  Building2,
  CalendarClock,
  Globe,
  MessageCircle,
  Palette,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useCalendarStatus } from "@/hooks/use-calendar";
import { useKbEntries } from "@/hooks/use-knowledge-base";
import { useOnboardingStatus } from "@/hooks/use-onboarding";
import { useSettings, useUpdateSettings } from "@/hooks/use-settings";
import { ApiError } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import type { AiReplyMode } from "@/lib/types";
import { cn, describeWhatsAppConnection } from "@/lib/utils";

// Shared, restrained hover treatment (Sprint 46's dashboard pattern, reused
// here rather than forked into a shared component — it's a plain Tailwind
// string, not a component).
const CARD_HOVER =
  "transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-md";

export default function SettingsPage() {
  const { mocked, openProfile } = useAuthContext();
  const { data: onboarding } = useOnboardingStatus();
  const { data: kbEntries } = useKbEntries();
  const { data: calendarStatus } = useCalendarStatus();
  const whatsapp = describeWhatsAppConnection(onboarding?.business?.whatsapp_connection_status);
  const business = onboarding?.business;

  return (
    <>
      <PageHeader
        title="Settings"
        description="Everything HIRA knows about your business, and how your employee behaves."
      />

      <Section title="Your business">
        <Card className={cn("lg:col-span-2", CARD_HOVER)}>
          <CardHeader className="flex-row items-center gap-3 space-y-0">
            <SectionIcon icon={Building2} />
            <CardTitle className="text-base">Business profile</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              This is what HIRA was told about {business?.name ?? "your business"} at signup.
              Editing these here isn&apos;t self-serve yet — reach out if anything needs to
              change.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              <ProfileField
                label="Business name"
                value={business?.name ?? "—"}
                why="Shown across your dashboard, and used whenever HIRA needs to refer to your business by name."
              />
              <ProfileField
                label="Industry"
                value={business?.industry ?? "Not set"}
                why="Recorded at signup. HIRA's answers are grounded in what you've taught it, not this label — add specifics under Business Knowledge for the best replies, whatever your industry."
              />
              <ProfileField
                label="Country"
                value={business?.country ?? "Not set"}
                why="For your own records — not currently used to change how HIRA behaves."
              />
              <ProfileField
                label="Contact email"
                value={business?.contact_email ?? "Not set"}
                why="How the HIRA team can reach you about your account. Never shared with customers."
              />
            </div>
          </CardContent>
        </Card>
      </Section>

      <Section title="Your employee">
        <AiReplyModeCard />

        <Card className={CARD_HOVER}>
          <CardHeader className="flex-row items-center gap-3 space-y-0">
            <SectionIcon icon={BookOpen} />
            <CardTitle className="text-base">Business Knowledge</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              HIRA checks these facts before answering every customer question — the more you
              add, the fewer questions it has to guess at.
            </p>
            {kbEntries ? (
              <p className="text-2xl font-semibold tracking-tight">{kbEntries.length}</p>
            ) : (
              <Skeleton className="h-8 w-10" />
            )}
            <p className="text-xs text-muted-foreground">
              {kbEntries?.length ? "facts taught so far" : "No facts taught yet"}
            </p>
            <Button asChild size="sm" variant="outline">
              <Link href="/knowledge-base">Manage Business Knowledge</Link>
            </Button>
          </CardContent>
        </Card>

        <Card className={CARD_HOVER}>
          <CardHeader className="flex-row items-center gap-3 space-y-0">
            <SectionIcon icon={CalendarClock} />
            <CardTitle className="text-base">Working hours &amp; calendar</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              HIRA only offers appointment times inside your working hours, in your timezone —
              and once Google Calendar is connected, it checks real availability before booking
              anything.
            </p>
            <Row
              label="Google Calendar"
              value={
                calendarStatus ? (
                  <Badge variant={calendarStatus.connected ? "success" : "secondary"}>
                    {calendarStatus.connected ? "Connected" : "Not connected"}
                  </Badge>
                ) : (
                  <Skeleton className="h-5 w-20" />
                )
              }
            />
            <Row label="Timezone" value={business?.timezone ?? "UTC"} />
            <Button asChild size="sm" variant="outline">
              <Link href="/calendar">
                {calendarStatus?.connected ? "Manage calendar" : "Connect Google Calendar"}
              </Link>
            </Button>
          </CardContent>
        </Card>
      </Section>

      <Section title="Connections">
        <Card className={CARD_HOVER}>
          <CardHeader className="flex-row items-center gap-3 space-y-0">
            <SectionIcon icon={MessageCircle} />
            <CardTitle className="text-base">WhatsApp</CardTitle>
            <Badge variant={whatsapp.variant} className="ml-auto">
              {whatsapp.label}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-3">
            {whatsapp.label === "Connected" ? (
              <p className="text-sm text-muted-foreground">
                Your WhatsApp Business number is connected — every message customers send there
                reaches HIRA automatically, and every reply sends from that same number.
              </p>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  Connecting your WhatsApp Business number is what lets HIRA read customer
                  messages and reply from your business&apos;s own number — customers keep messaging
                  the number they already know.
                </p>
                <p className="text-sm text-muted-foreground">
                  This isn&apos;t self-serve yet: reach out to the HIRA team with your WhatsApp
                  Business number and we&apos;ll connect it for you.
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card className={CARD_HOVER}>
          <CardHeader className="flex-row items-center gap-3 space-y-0">
            <SectionIcon icon={Activity} />
            <CardTitle className="text-base">Systems</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row label="Sign-in" value={<Badge variant={mocked ? "warning" : "success"}>{mocked ? "Mock (dev)" : "Connected"}</Badge>} />
            <Row label="AI provider" value={<Badge variant="success">Groq — llama-3.3-70b</Badge>} />
            <Row label="Knowledge search" value={<Badge variant="success">local, on-device</Badge>} />
          </CardContent>
        </Card>
      </Section>

      <Section title="Account">
        <Card className={CARD_HOVER}>
          <CardHeader className="flex-row items-center gap-3 space-y-0">
            <SectionIcon icon={Palette} />
            <CardTitle className="text-base">Appearance</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Switch between light and dark, or follow your system.
            </p>
            <ThemeToggle />
          </CardContent>
        </Card>

        <Card className={CARD_HOVER}>
          <CardHeader className="flex-row items-center gap-3 space-y-0">
            <SectionIcon icon={ShieldCheck} />
            <CardTitle className="text-base">Security</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Your password, two-factor authentication, and active sessions are managed through
              your sign-in provider, not HIRA directly.
            </p>
            <Button size="sm" variant="outline" onClick={openProfile}>
              Manage account security
            </Button>
          </CardContent>
        </Card>
      </Section>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h2>
      <div className="grid gap-4 lg:grid-cols-2">{children}</div>
    </section>
  );
}

function SectionIcon({ icon: Icon }: { icon: LucideIcon }) {
  return (
    <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10">
      <Icon className="size-4 text-primary" />
    </div>
  );
}

function ProfileField({ label, value, why }: { label: string; value: string; why: string }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{label}</span>
        <span className="text-sm text-muted-foreground">{value}</span>
      </div>
      <p className="text-xs text-muted-foreground">{why}</p>
    </div>
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
    <Card className={CARD_HOVER}>
      <CardHeader className="flex-row items-center gap-3 space-y-0">
        <SectionIcon icon={Globe} />
        <CardTitle className="text-base">How your employee responds</CardTitle>
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
          <>
            <Button size="sm" onClick={handleSave} disabled={controlsDisabled || !isDirty}>
              {isSaving ? "Saving…" : "Save"}
            </Button>
            <p className="text-xs text-muted-foreground">
              Either way, you can escalate any conversation to yourself from Pending Replies.
            </p>
          </>
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

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      {/* A plain div, not a span: value can be a Badge or Skeleton (both
          render a div), and a div can't validly nest inside a span. */}
      <div>{value}</div>
    </div>
  );
}
