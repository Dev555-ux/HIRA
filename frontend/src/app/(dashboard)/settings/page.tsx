"use client";

import {
  AlertTriangle,
  Bot,
  BookOpen,
  Building2,
  CalendarClock,
  Clock,
  Copy,
  Globe,
  MessageCircle,
  Palette,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useCalendarStatus } from "@/hooks/use-calendar";
import { useKbEntries } from "@/hooks/use-knowledge-base";
import { useOnboardingStatus } from "@/hooks/use-onboarding";
import { useSettings, useUpdateSettings } from "@/hooks/use-settings";
import { ApiError } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import type { AiReplyMode, Business } from "@/lib/types";
import { cn, describeWhatsAppConnection } from "@/lib/utils";

// Shared, restrained hover treatment (Sprint 46's dashboard pattern, reused
// here rather than forked into a shared component — it's a plain Tailwind
// string, not a component).
const CARD_HOVER =
  "transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-md";

export default function SettingsPage() {
  const { openProfile } = useAuthContext();
  const { data: onboarding } = useOnboardingStatus();
  const { data: kbEntries } = useKbEntries();
  const { data: calendarStatus } = useCalendarStatus();
  const [isWhatsAppWizardOpen, setIsWhatsAppWizardOpen] = useState(false);
  const whatsapp = describeWhatsAppConnection(onboarding?.business?.whatsapp_connection_status);
  const business = onboarding?.business;
  const whatsappConnected = onboarding?.business?.whatsapp_connection_status === "connected";

  return (
    <>
      <Suspense fallback={null}>
        <WhatsAppWizardAutoOpen onOpen={() => setIsWhatsAppWizardOpen(true)} />
      </Suspense>
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
        <AiEmployeeCard business={business} kbCount={kbEntries?.length} />

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
        <Card className={cn("lg:col-span-2", CARD_HOVER)}>
          <CardHeader className="flex-row items-center gap-3 space-y-0">
            <SectionIcon icon={MessageCircle} />
            <CardTitle className="text-base">WhatsApp</CardTitle>
            <Badge variant={whatsapp.variant} className="ml-auto">
              {whatsapp.label}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-3">
            {whatsappConnected ? (
              <>
                <p className="text-sm text-muted-foreground">
                  Your AI employee is connected — customers can message your business through
                  WhatsApp right now, and HIRA replies from that same number automatically.
                </p>
                <Button asChild size="sm" variant="outline">
                  <Link href="/demo">Send a test message</Link>
                </Button>
              </>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  {whatsapp.label === "Needs attention"
                    ? "We're finishing your WhatsApp connection. If we need anything else from you, we'll ask for it here."
                    : "Connecting your WhatsApp Business number is what lets HIRA read customer messages and reply from your business's own number — customers keep messaging the number they already know."}
                </p>
                <Button size="sm" variant="outline" onClick={() => setIsWhatsAppWizardOpen(true)}>
                  {whatsapp.label === "Needs attention" ? "Continue setup" : "Connect WhatsApp"}
                </Button>
              </>
            )}
          </CardContent>
        </Card>

        <WhatsAppConnectWizard
          open={isWhatsAppWizardOpen}
          onOpenChange={setIsWhatsAppWizardOpen}
          businessName={business?.name ?? "your business"}
        />
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

// An at-a-glance summary — no model names, no provider names, nothing a
// business owner would need to look up. Every field here is real data
// already fetched elsewhere on this page (business.onboarding_status,
// the knowledge-base count, AI Reply Mode); this card just answers "is my
// employee on and working" in one glance, without requiring reading the
// three detailed cards below it to piece that together.
function AiEmployeeCard({
  business,
  kbCount,
}: {
  business?: Business | null;
  kbCount?: number;
}) {
  const { data: settings } = useSettings();
  const isLive = business?.onboarding_status === "live";

  return (
    <Card className={CARD_HOVER}>
      <CardHeader className="flex-row items-center gap-3 space-y-0">
        <SectionIcon icon={Bot} />
        <CardTitle className="text-base">AI Employee</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <Row
          label="Status"
          value={
            business ? (
              <Badge variant={isLive ? "success" : "secondary"}>
                {isLive ? "Live" : "Setting up"}
              </Badge>
            ) : (
              <Skeleton className="h-5 w-16" />
            )
          }
        />
        <Row
          label="Knowledge learned"
          value={
            kbCount != null ? (
              `${kbCount} ${kbCount === 1 ? "fact" : "facts"}`
            ) : (
              <Skeleton className="h-5 w-16" />
            )
          }
        />
        <Row
          label="Reply mode"
          value={
            settings ? (
              <Badge variant="secondary">
                {settings.mode === "autonomous" ? "Autonomous" : "Assisted"}
              </Badge>
            ) : (
              <Skeleton className="h-5 w-20" />
            )
          }
        />
      </CardContent>
    </Card>
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

// The onboarding checklist links here with ?whatsapp=connect so "Connect"/
// "Continue setup" opens the wizard directly instead of landing the owner on
// Settings and making them find and click the button again. useSearchParams
// requires a Suspense boundary in the App Router — same pattern the Calendar
// page already uses for its own ?calendar=connected query param.
function WhatsAppWizardAutoOpen({ onOpen }: { onOpen: () => void }) {
  const searchParams = useSearchParams();
  useEffect(() => {
    if (searchParams.get("whatsapp") === "connect") {
      onOpen();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);
  return null;
}

type WhatsAppWizardStep = "intro" | "details";

/** WhatsApp has no self-serve connect flow yet (no OAuth, no backend endpoint
 * to receive a connection request) — this wizard doesn't pretend otherwise.
 * It explains what connecting means, then turns the owner's WhatsApp Business
 * number into a copyable request they can hand to the HIRA team through
 * whatever channel they already use. Nothing here is submitted anywhere;
 * the number is held in local component state only, for building the
 * copied text, and is discarded when the dialog closes. */
function WhatsAppConnectWizard({
  open,
  onOpenChange,
  businessName,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  businessName: string;
}) {
  const [step, setStep] = useState<WhatsAppWizardStep>("intro");
  const [waNumber, setWaNumber] = useState("");
  const { toast } = useToast();

  function close(open: boolean) {
    onOpenChange(open);
    if (!open) {
      setStep("intro");
      setWaNumber("");
    }
  }

  async function handleCopy() {
    const details = `Connect WhatsApp for ${businessName}\nWhatsApp Business number: ${waNumber.trim()}`;
    try {
      await navigator.clipboard.writeText(details);
      toast({
        title: "Copied",
        description: "Paste this wherever you already reach the HIRA team.",
        variant: "success",
      });
    } catch {
      toast({
        title: "Couldn't copy automatically",
        description: "Select the text above and copy it manually instead.",
        variant: "destructive",
      });
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      {open && step === "intro" && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Connect WhatsApp</DialogTitle>
            <DialogDescription>
              This is how customers will reach your new employee.
            </DialogDescription>
          </DialogHeader>
          <ul className="space-y-3">
            <li className="flex items-start gap-3 text-sm">
              <MessageCircle className="mt-0.5 size-4 shrink-0 text-primary" />
              <span className="text-muted-foreground">
                Customers keep messaging the WhatsApp number they already know — nothing changes
                for them.
              </span>
            </li>
            <li className="flex items-start gap-3 text-sm">
              <Bot className="mt-0.5 size-4 shrink-0 text-primary" />
              <span className="text-muted-foreground">
                HIRA reads every message and replies from that same number, grounded in what
                you&apos;ve taught it.
              </span>
            </li>
            <li className="flex items-start gap-3 text-sm">
              <Clock className="mt-0.5 size-4 shrink-0 text-primary" />
              <span className="text-muted-foreground">
                Connecting isn&apos;t instant — it&apos;s a short, guided step the HIRA team does
                with you, not an automatic signup.
              </span>
            </li>
          </ul>
          <DialogFooter>
            <Button variant="outline" onClick={() => close(false)}>
              Cancel
            </Button>
            <Button onClick={() => setStep("details")}>Continue</Button>
          </DialogFooter>
        </DialogContent>
      )}
      {open && step === "details" && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Your WhatsApp Business number</DialogTitle>
            <DialogDescription>
              Add the number your customers already message — we&apos;ll use this to connect it.
            </DialogDescription>
          </DialogHeader>
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">WhatsApp Business number</span>
            <Input
              placeholder="+1 555 000 1234"
              value={waNumber}
              onChange={(e) => setWaNumber(e.target.value)}
            />
          </label>
          <div className="rounded-lg border bg-muted/30 p-3 text-sm">
            <p className="font-medium">Connect WhatsApp for {businessName}</p>
            <p className="text-muted-foreground">
              WhatsApp Business number: {waNumber.trim() || "—"}
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setStep("intro")}>
              Back
            </Button>
            <Button onClick={handleCopy} disabled={!waNumber.trim()}>
              <Copy /> Copy request details
            </Button>
          </DialogFooter>
        </DialogContent>
      )}
    </Dialog>
  );
}
