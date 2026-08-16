"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import {
  AlertTriangle,
  Bot,
  BookOpen,
  Building2,
  CalendarClock,
  ChevronDown,
  Copy,
  ExternalLink,
  Globe,
  MessageCircle,
  Palette,
  ShieldCheck,
  Unlink,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { ThemeToggle } from "@/components/theme-toggle";
import { aiSurfaceClassName } from "@/components/ui/ai-surface";
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
import { StatusPill } from "@/components/ui/status-pill";
import { useToast } from "@/components/ui/toast";
import { useCalendarStatus } from "@/hooks/use-calendar";
import { useKbEntries } from "@/hooks/use-knowledge-base";
import { useOnboardingStatus } from "@/hooks/use-onboarding";
import { useSettings, useUpdateSettings } from "@/hooks/use-settings";
import {
  useConnectWhatsApp,
  useDisconnectWhatsApp,
  useWhatsAppStatus,
  useWhatsAppWebhookConfig,
} from "@/hooks/use-whatsapp";
import { ApiError } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import { VARIANT_TO_STATE } from "@/lib/status";
import type { AiReplyMode, Business } from "@/lib/types";
import { cn, describeOnboardingStatus, describeWhatsAppConnection, formatRelativeTime } from "@/lib/utils";

// Verify-step polling (Sprint 71, Task B) — faster than the app-wide
// POLL_INTERVAL_MS (15s, meant for passive background dashboard refresh)
// because this is an active, attended waiting state: the owner is staring
// at the dialog after sending themselves a WhatsApp message.
const VERIFY_POLL_INTERVAL_MS = 3_000;

export default function SettingsPage() {
  const { openProfile } = useAuthContext();
  const { data: onboarding } = useOnboardingStatus();
  const { data: kbEntries } = useKbEntries();
  const { data: calendarStatus } = useCalendarStatus();
  const { data: whatsappStatus } = useWhatsAppStatus();
  const [isWhatsAppWizardOpen, setIsWhatsAppWizardOpen] = useState(false);
  const [wizardStartStep, setWizardStartStep] = useState<WhatsAppWizardStep>("entry");
  const [confirmDisconnectWhatsApp, setConfirmDisconnectWhatsApp] = useState(false);
  const disconnectWhatsApp = useDisconnectWhatsApp();
  const { toast } = useToast();
  const whatsapp = describeWhatsAppConnection(whatsappStatus?.status);
  const business = onboarding?.business;
  const whatsappConnected = whatsappStatus?.connected ?? false;

  function openWhatsAppWizard(step: WhatsAppWizardStep) {
    setWizardStartStep(step);
    setIsWhatsAppWizardOpen(true);
  }

  async function handleDisconnectWhatsApp() {
    try {
      await disconnectWhatsApp.mutateAsync();
      toast({ title: "WhatsApp disconnected" });
    } catch (err) {
      toast({
        title: "Couldn't disconnect",
        description: err instanceof ApiError ? err.message : "Something went wrong — please try again.",
        variant: "destructive",
      });
    }
    setConfirmDisconnectWhatsApp(false);
  }

  return (
    <>
      <Suspense fallback={null}>
        <WhatsAppWizardAutoOpen onOpen={() => openWhatsAppWizard("entry")} />
      </Suspense>
      <PageHeader
        title="Settings"
        description="Everything HIRA knows about your business, and how your employee behaves."
      />

      <Section title="Your business">
        <Card interactive className="lg:col-span-2">
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

        <Card interactive>
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

        <Card interactive>
          <CardHeader className="flex-row items-center gap-3 space-y-0">
            <SectionIcon icon={CalendarClock} />
            <CardTitle className="text-base">HIRA Calendar</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              HIRA Calendar manages your appointments automatically, and only offers times inside
              your working hours, in your timezone. You can optionally connect Google Calendar
              for synchronization.
            </p>
            <Row
              label="Status"
              value={
                calendarStatus ? (
                  <StatusPill state="success">
                    {calendarStatus.connected ? "Google Sync Enabled" : "Active"}
                  </StatusPill>
                ) : (
                  <Skeleton className="h-5 w-20" />
                )
              }
            />
            <Row label="Timezone" value={business?.timezone ?? "UTC"} />
            <Button asChild size="sm" variant="outline">
              <Link href="/calendar">Manage calendar</Link>
            </Button>
          </CardContent>
        </Card>
      </Section>

      <Section title="Connections">
        <Card interactive className="lg:col-span-2">
          <CardHeader className="flex-row items-center gap-3 space-y-0">
            <SectionIcon icon={MessageCircle} />
            <CardTitle className="text-base">WhatsApp</CardTitle>
            <StatusPill state={VARIANT_TO_STATE[whatsapp.variant]} className="ml-auto">
              {whatsapp.label}
            </StatusPill>
          </CardHeader>
          <CardContent className="space-y-3">
            {whatsappConnected ? (
              <>
                <p className="text-sm text-muted-foreground">
                  Your AI employee is connected
                  {/* Sprint 72: prefer the real, dialable number over the
                      masked technical ID whenever Meta has told us it —
                      falls back for connections made before this existed. */}
                  {whatsappStatus?.display_phone_number || whatsappStatus?.phone_number_id_masked ? (
                    <>
                      {" "}
                      (<span className="font-medium text-foreground">
                        {whatsappStatus.display_phone_number ?? whatsappStatus.phone_number_id_masked}
                      </span>
                      )
                    </>
                  ) : null}{" "}
                  — customers can message your business through WhatsApp right now, and HIRA
                  replies from that same number automatically.
                </p>
                <Row
                  label="Connection health"
                  value={
                    // Real signal (last actual inbound Message), never
                    // inferred from stored credentials — Demo Chat is no
                    // longer presented as proof this works (Sprint 71, Task B).
                    whatsappStatus?.last_inbound_at ? (
                      <span className="text-foreground">
                        Last message {formatRelativeTime(whatsappStatus.last_inbound_at)}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">No messages received yet</span>
                    )
                  }
                />
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => openWhatsAppWizard("verify")}
                  >
                    Check connection
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setConfirmDisconnectWhatsApp(true)}
                    disabled={disconnectWhatsApp.isPending}
                  >
                    <Unlink /> Disconnect
                  </Button>
                </div>
              </>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  {whatsapp.label === "Needs attention"
                    ? "We're finishing your WhatsApp connection. If we need anything else from you, we'll ask for it here."
                    : "Connecting your WhatsApp Business number is what lets HIRA read customer messages and reply from your business's own number — customers keep messaging the number they already know."}
                </p>
                <Button size="sm" variant="outline" onClick={() => openWhatsAppWizard("entry")}>
                  <ExternalLink />{" "}
                  {whatsapp.label === "Needs attention" ? "Continue setup" : "Connect WhatsApp"}
                </Button>
              </>
            )}
          </CardContent>
        </Card>

        <ConfirmDialog
          open={confirmDisconnectWhatsApp}
          onOpenChange={setConfirmDisconnectWhatsApp}
          title="Disconnect WhatsApp?"
          description="HIRA will stop reading and replying to messages on this number until you reconnect it."
          confirmLabel="Disconnect"
          onConfirm={handleDisconnectWhatsApp}
          isPending={disconnectWhatsApp.isPending}
        />

        <WhatsAppConnectWizard
          open={isWhatsAppWizardOpen}
          onOpenChange={setIsWhatsAppWizardOpen}
          startStep={wizardStartStep}
        />
      </Section>

      <Section title="Account">
        <Card interactive>
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

        <Card interactive>
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
  const onboarding = describeOnboardingStatus(business?.onboarding_status);

  return (
    <Card interactive>
      <CardHeader className="flex-row items-center gap-3 space-y-0">
        <SectionIcon icon={Bot} />
        <CardTitle className="text-base">AI Employee</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <Row
          label="Status"
          value={
            business ? (
              <StatusPill state={VARIANT_TO_STATE[onboarding.variant]}>
                {onboarding.label}
              </StatusPill>
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
  const { data, isPending, isError, refetch } = useSettings();
  const updateSettings = useUpdateSettings();
  const { toast } = useToast();
  const [selected, setSelected] = useState<AiReplyMode | null>(null);

  useEffect(() => {
    if (data) setSelected(data.mode);
  }, [data]);

  const current = selected ?? data?.mode ?? null;
  const isDirty = data != null && current != null && current !== data.mode;
  const isSaving = updateSettings.isPending;
  const controlsDisabled = isPending || isSaving;

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
    // M13: the one settings control that directly governs AI behavior gets
    // the AI-identity spine (M4's aiSurfaceClassName) — combined with the
    // page's existing hover treatment, not replacing it.
    <Card interactive className={aiSurfaceClassName}>
      <CardHeader className="flex-row items-center gap-3 space-y-0">
        <SectionIcon icon={Globe} />
        <CardTitle className="text-base">How your employee responds</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isPending ? (
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
        "flex items-start gap-3 rounded-md border p-4 transition-colors",
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

// Rev 2: plain-text, collapsible walkthroughs — deliberately not
// screenshots. Meta's own console UI changes often enough that embedded
// screenshots go stale within a few months and become actively misleading;
// menu paths and field names are far more durable, and the "official guide"
// links below point at Meta's own docs, which Meta keeps current so HIRA
// doesn't have to. Split per field (not one upfront wall of text) and
// collapsed by default, under a "don't have this yet" toggle — an owner who
// already has these values ready should never have to read past them. HIRA's
// customers already run WhatsApp Business day to day; what they're less
// likely to already have is the *developer*-side Meta App/System User/token,
// which is what these walk through.
const CREATE_APP_HELP = [
  {
    title: "Create a Meta App",
    description:
      'developers.facebook.com → My Apps → Create App → choose "Business" → add the "WhatsApp" product.',
    guideUrl: "https://developers.facebook.com/docs/development/create-an-app",
  },
];

const ACCESS_TOKEN_HELP = [
  {
    title: "Create a System User",
    description:
      "Meta Business Settings → Users → System Users → Add → assign it to your WhatsApp Business Account with Manage access.",
    guideUrl: "https://developers.facebook.com/docs/whatsapp/business-management-api/get-started",
  },
  {
    title: "Generate a permanent access token",
    description:
      'From that System User: Generate New Token → select your App → grant the "whatsapp_business_messaging" and "whatsapp_business_management" permissions → copy the token immediately (Meta only shows it once).',
    guideUrl: "https://developers.facebook.com/docs/whatsapp/business-management-api/get-started",
  },
];

function FieldHelp({
  toggleLabel,
  steps,
}: {
  toggleLabel: string;
  steps: { title: string; description: string; guideUrl: string }[];
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="overflow-hidden rounded-md border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 p-3 text-left text-sm font-medium transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
      >
        {toggleLabel}
        <ChevronDown className={cn("size-4 shrink-0 transition-transform duration-[var(--motion-fast)]", open && "rotate-180")} />
      </button>
      {open && (
        <ol className="space-y-3 border-t p-3">
          {steps.map((step, i) => (
            <li key={step.title} className="flex gap-3 text-sm">
              <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
                {i + 1}
              </span>
              <div className="space-y-0.5">
                <p className="font-medium">{step.title}</p>
                <p className="text-muted-foreground">{step.description}</p>
                <a
                  href={step.guideUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  Meta&apos;s guide <ExternalLink className="size-3" />
                </a>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function StepDots({ count, current }: { count: number; current: number }) {
  return (
    <div className="flex justify-center gap-1.5" aria-hidden="true">
      {Array.from({ length: count }).map((_, i) => (
        <span
          key={i}
          className={cn("size-1.5 rounded-full", i <= current ? "bg-primary" : "bg-muted")}
        />
      ))}
    </div>
  );
}

const whatsappCredentialsSchema = z.object({
  phone_number_id: z.string().trim().min(1, "Enter your Phone Number ID"),
  whatsapp_business_account_id: z.string().trim().min(1, "Enter your WhatsApp Business Account ID"),
  access_token: z.string().trim().min(1, "Enter your access token"),
  app_secret: z.string().trim().min(1, "Enter your App Secret"),
});
type WhatsAppCredentialsValues = z.infer<typeof whatsappCredentialsSchema>;

const FIELD_STEP_ORDER = ["phone", "waba", "token", "secret"] as const;
type FieldStep = (typeof FIELD_STEP_ORDER)[number];

// Rev 3: dropped the small Meta-jargon caption line above each input —
// the screen title now carries the business-language name on its own
// (§2 of this session's UX pass: "the owner should only see Meta
// terminology when absolutely unavoidable"). The one exception is the
// phone/WABA pair: both are plain numeric IDs on the same Meta "API Setup"
// page, genuinely easy to mix up, so their descriptions keep a small
// quoted cross-reference to Meta's own field label — not shown as a
// separate label, just folded into the locating instructions.
const FIELD_CONFIG: Record<
  FieldStep,
  {
    name: keyof WhatsAppCredentialsValues;
    title: string;
    description: string;
    placeholder: string;
    type?: string;
    help?: { toggleLabel: string; steps: typeof CREATE_APP_HELP };
  }
> = {
  phone: {
    name: "phone_number_id",
    title: "Your WhatsApp Number",
    description: 'Meta App dashboard → WhatsApp → API Setup — labeled "Phone number ID."',
    placeholder: "1234567890",
    help: { toggleLabel: "Don't have a Meta App yet?", steps: CREATE_APP_HELP },
  },
  waba: {
    name: "whatsapp_business_account_id",
    title: "Business Account",
    description: 'Same page — labeled "WhatsApp Business Account ID."',
    placeholder: "1234567890",
  },
  token: {
    name: "access_token",
    title: "Access Key",
    description: "From a System User assigned to this account.",
    placeholder: "EAAG…",
    type: "password",
    help: { toggleLabel: "Don't have an access token yet?", steps: ACCESS_TOKEN_HELP },
  },
  secret: {
    name: "app_secret",
    title: "App Secret",
    description: "Meta App dashboard → Settings → Basic.",
    placeholder: "From App → Settings → Basic",
    type: "password",
  },
};

type WhatsAppWizardStep = "entry" | FieldStep | "webhook" | "verify";

/** Real self-serve connection (Sprint 69, ONBOARD-D "guided-manual v1") —
 * no Embedded Signup yet (that needs Meta's Tech Provider approval; per
 * DEC-052 §0 and confirmed directly with the founder, that application has
 * still not been submitted). The owner already runs WhatsApp Business and
 * already has customers messaging that number, so there's no
 * account-creation branch here, no "what is WhatsApp Business" explanation —
 * just the fastest path to locating four values from an account that
 * already exists.
 *
 * Rev 3 note (reconciled against DEC-052 / WHATSAPP_ONBOARDING_V2_DESIGN.md,
 * the approved-pending-Meta-approval target design): that document's own
 * §9/§10 roadmap is explicit that guided-manual v1 stays the *default* entry
 * point until Embedded Signup is built AND pilot-validated — Embedded Signup
 * only "cuts over" to become primary at roadmap step 7, not before. So the
 * `entry` screen below intentionally does NOT show a "Continue with Meta"
 * button (that's DEC-052 §3.1's Welcome screen, for once Track B exists) —
 * its copy and single "Connect WhatsApp" action match DEC-052 §3.1's own
 * Welcome-screen button label, and it leads directly into this same
 * guided-manual flow, exactly as canonical intends "today."
 *
 * One field per screen (Rev 2): each screen has exactly one purpose, and the
 * rare owner who doesn't yet have the *developer*-side Meta App/System
 * User/token gets that help collapsed behind a toggle on the field where
 * it's first needed, not dumped upfront.
 *
 * HIRA verifies the four values against Meta's API before storing anything
 * (POST /api/v1/whatsapp/connect), so a typo'd token fails immediately with
 * a specific reason instead of on the first real customer message.
 * Submitting again (reconnect) just replaces what's stored.
 *
 * Sprint 71: credential verification alone doesn't prove real messages can
 * arrive — the business's own Meta App also needs the Callback URL/Verify
 * Token pasted into its webhook config (DEC-038), a step Meta doesn't expose
 * any way to automate here. So a successful connect moves to a "webhook"
 * step (Task A) showing those exact values, then a "verify" step (Task B)
 * that polls for a real inbound message instead of just trusting the stored
 * credentials — the one failure mode credential verification can't catch. */
function WhatsAppConnectWizard({
  open,
  onOpenChange,
  startStep,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  startStep: WhatsAppWizardStep;
}) {
  const [step, setStep] = useState<WhatsAppWizardStep>(startStep);
  const [error, setError] = useState<string | null>(null);
  const connectWhatsApp = useConnectWhatsApp();
  const form = useForm<WhatsAppCredentialsValues>({
    resolver: zodResolver(whatsappCredentialsSchema),
    defaultValues: {
      phone_number_id: "",
      whatsapp_business_account_id: "",
      access_token: "",
      app_secret: "",
    },
  });

  // The dialog stays mounted across open/close (only its content is
  // conditionally rendered below), so re-opening needs an explicit sync to
  // whatever step the caller asked for — e.g. Settings' "Check connection"
  // button reopens straight at "verify", not back at the first field.
  useEffect(() => {
    if (open) setStep(startStep);
  }, [open, startStep]);

  function close(open: boolean) {
    if (connectWhatsApp.isPending) return;
    onOpenChange(open);
    if (!open) {
      setStep("entry");
      form.reset();
      setError(null);
    }
  }

  async function handleConnect(values: WhatsAppCredentialsValues) {
    setError(null);
    try {
      await connectWhatsApp.mutateAsync(values);
      // Not "connected" yet as far as the owner should believe — the
      // webhook and verify steps below are what actually prove it (Task B).
      setStep("webhook");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong — please try again.");
    }
  }

  const fieldIndex = FIELD_STEP_ORDER.indexOf(step as FieldStep);
  const isFieldStep = fieldIndex !== -1;
  const fieldConfig = isFieldStep ? FIELD_CONFIG[step as FieldStep] : null;

  async function handleFieldNext() {
    if (!fieldConfig) return;
    const valid = await form.trigger(fieldConfig.name);
    if (!valid) return;
    if (fieldIndex === FIELD_STEP_ORDER.length - 1) {
      await form.handleSubmit(handleConnect)();
    } else {
      setStep(FIELD_STEP_ORDER[fieldIndex + 1]);
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      {open && step === "entry" && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Connect WhatsApp</DialogTitle>
            <DialogDescription>
              Connect your existing WhatsApp Business account. Your customers will continue using
              the same number.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => setStep(FIELD_STEP_ORDER[0])}>Connect WhatsApp</Button>
          </DialogFooter>
        </DialogContent>
      )}
      {open && fieldConfig && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{fieldConfig.title}</DialogTitle>
            <DialogDescription>{fieldConfig.description}</DialogDescription>
          </DialogHeader>
          <label className="block space-y-1.5">
            {/* Visually hidden: the DialogTitle above already carries the
                business-language name on screen (no need to repeat it or
                show Meta's jargon term as a visible caption), but the
                input still needs an accessible name for screen readers. */}
            <span className="sr-only">{fieldConfig.title}</span>
            <Input
              type={fieldConfig.type}
              placeholder={fieldConfig.placeholder}
              disabled={connectWhatsApp.isPending}
              {...form.register(fieldConfig.name)}
            />
            {form.formState.errors[fieldConfig.name] && (
              <span className="block text-xs text-destructive">
                {form.formState.errors[fieldConfig.name]?.message}
              </span>
            )}
          </label>
          {fieldConfig.help && (
            <FieldHelp toggleLabel={fieldConfig.help.toggleLabel} steps={fieldConfig.help.steps} />
          )}
          {error && fieldIndex === FIELD_STEP_ORDER.length - 1 && (
            <p className="rounded-md bg-destructive/10 p-2 text-sm text-destructive" role="alert">
              {error}
            </p>
          )}
          <StepDots count={FIELD_STEP_ORDER.length} current={fieldIndex} />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => (fieldIndex === 0 ? setStep("entry") : setStep(FIELD_STEP_ORDER[fieldIndex - 1]))}
              disabled={connectWhatsApp.isPending}
            >
              Back
            </Button>
            <Button onClick={handleFieldNext} disabled={connectWhatsApp.isPending}>
              {fieldIndex === FIELD_STEP_ORDER.length - 1
                ? connectWhatsApp.isPending
                  ? "Connecting…"
                  : "Connect"
                : "Continue"}
            </Button>
          </DialogFooter>
        </DialogContent>
      )}
      {open && step === "webhook" && (
        <DialogContent>
          <WebhookConfigStep onNext={() => setStep("verify")} />
        </DialogContent>
      )}
      {open && step === "verify" && (
        <DialogContent>
          <VerifyConnectionStep onDone={() => close(false)} />
        </DialogContent>
      )}
    </Dialog>
  );
}

// Sprint 71, Task A: the values every business must paste into their own
// Meta App (App → WhatsApp → Configuration → Webhooks) — shown directly
// instead of only pointed at developer docs. Both come from the backend
// (GET /api/v1/whatsapp/webhook-config): the callback URL is derived from
// real deployment config (RAILWAY_PUBLIC_DOMAIN), never hardcoded here, and
// the verify token is intentionally shared/non-secret (DEC-038).
function WebhookConfigStep({ onNext }: { onNext: () => void }) {
  const { data, isPending, isError, refetch } = useWhatsAppWebhookConfig();
  const { toast } = useToast();

  function copy(value: string) {
    void navigator.clipboard.writeText(value);
    toast({ title: "Copied to clipboard" });
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Set up your webhook</DialogTitle>
        <DialogDescription>
          One more step in your Meta App before real messages can reach HIRA.
        </DialogDescription>
      </DialogHeader>
      {isError ? (
        // Found during Sprint 71 release verification: without this branch,
        // a failed fetch left the loading skeleton showing forever with no
        // way out — the wizard's only genuine "stuck" state.
        <EmptyState
          icon={AlertTriangle}
          title="Couldn't load your webhook details"
          description="Something went wrong — please try again."
          action={
            <Button size="sm" onClick={() => refetch()}>
              Retry
            </Button>
          }
          className="border-0 py-6"
        />
      ) : (
        <>
          <div className="space-y-3">
            {isPending || !data ? (
              <>
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
              </>
            ) : (
              <>
                <CopyableField label="Callback URL" value={data.callback_url} onCopy={copy} />
                <CopyableField label="Verify Token" value={data.verify_token} onCopy={copy} />
              </>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            Paste these values into your Meta App:
            <br />
            Meta App → WhatsApp → Configuration → Webhooks
            <br />
            Then subscribe to the &quot;messages&quot; field.
          </p>
        </>
      )}
      {!isError && (
        <DialogFooter>
          <Button onClick={onNext} disabled={isPending || !data}>
            Next: Verify connection
          </Button>
        </DialogFooter>
      )}
    </>
  );
}

function CopyableField({
  label,
  value,
  onCopy,
}: {
  label: string;
  value: string;
  onCopy: (value: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <span className="text-sm font-medium">{label}</span>
      <div className="flex items-center gap-2">
        <Input readOnly value={value} onFocus={(e) => e.target.select()} className="font-mono text-xs" />
        <Button
          type="button"
          size="icon"
          variant="outline"
          aria-label={`Copy ${label}`}
          onClick={() => onCopy(value)}
        >
          <Copy />
        </Button>
      </div>
    </div>
  );
}

// Sprint 71, Task B: replaces the old "Send a test message" link to Demo
// Chat, which proved nothing about the real WhatsApp connection (Demo Chat
// works identically whether or not the webhook is configured). This polls
// the one real production signal — an actual persisted inbound Message
// (GET /api/v1/whatsapp/status's last_inbound_at) — and never simulates or
// infers success from stored credentials alone.
function VerifyConnectionStep({ onDone }: { onDone: () => void }) {
  const { data } = useWhatsAppStatus({ refetchInterval: VERIFY_POLL_INTERVAL_MS });
  const { toast } = useToast();
  const [announced, setAnnounced] = useState(false);
  const verified = Boolean(data?.last_inbound_at);

  useEffect(() => {
    if (verified && !announced) {
      toast({ title: "WhatsApp connected", variant: "success" });
      setAnnounced(true);
    }
  }, [verified, announced, toast]);

  return (
    <>
      <DialogHeader>
        <DialogTitle>Verify your connection</DialogTitle>
        <DialogDescription>
          {/* Sprint 72: the wizard previously said "your connected business
              number" with no way to know what that number actually was —
              phone_number_id (already collected) is a Meta-internal ID, not
              a dialable number. display_phone_number is the real one. */}
          {data?.display_phone_number ? (
            <>
              Send a WhatsApp message from your phone to{" "}
              <span className="font-medium text-foreground">{data.display_phone_number}</span>.
            </>
          ) : (
            "Send a WhatsApp message from your phone to your connected business number."
          )}
        </DialogDescription>
      </DialogHeader>
      <p className="text-sm text-muted-foreground">
        For example: <span className="font-medium text-foreground">&quot;Hello&quot;</span> or{" "}
        <span className="font-medium text-foreground">&quot;Testing HIRA&quot;</span>
      </p>
      {verified ? (
        <div className="space-y-1 rounded-md bg-success/10 p-3 text-sm" role="status">
          <p className="font-medium text-success">✅ WhatsApp Connected</p>
          <p className="text-muted-foreground">
            Last message received: {formatRelativeTime(data!.last_inbound_at!)}
          </p>
          <p className="text-muted-foreground">Webhook: Healthy</p>
        </div>
      ) : (
        <div className="rounded-md bg-muted p-3 text-sm" role="status">
          ⏳ Waiting for your first WhatsApp message…
        </div>
      )}
      <DialogFooter>
        <Button onClick={onDone}>{verified ? "Done" : "I'll do this later"}</Button>
      </DialogFooter>
    </>
  );
}
