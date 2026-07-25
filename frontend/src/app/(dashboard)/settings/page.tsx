"use client";

import {
  AlertTriangle,
  Bot,
  BookOpen,
  Building2,
  CalendarClock,
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
import { ConfirmDialog } from "@/components/confirm-dialog";
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
import {
  useConnectWhatsApp,
  useDisconnectWhatsApp,
  useWhatsAppStatus,
  useWhatsAppWebhookConfig,
} from "@/hooks/use-whatsapp";
import { ApiError } from "@/lib/api";
import { useAuthContext } from "@/lib/auth-context";
import type { AiReplyMode, Business } from "@/lib/types";
import { cn, describeWhatsAppConnection, formatRelativeTime } from "@/lib/utils";

// Verify-step polling (Sprint 71, Task B) — faster than the app-wide
// POLL_INTERVAL_MS (15s, meant for passive background dashboard refresh)
// because this is an active, attended waiting state: the owner is staring
// at the dialog after sending themselves a WhatsApp message.
const VERIFY_POLL_INTERVAL_MS = 3_000;

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
  const { data: whatsappStatus } = useWhatsAppStatus();
  const [isWhatsAppWizardOpen, setIsWhatsAppWizardOpen] = useState(false);
  const [wizardStartStep, setWizardStartStep] = useState<WhatsAppWizardStep>("intro");
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
        <WhatsAppWizardAutoOpen onOpen={() => openWhatsAppWizard("intro")} />
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
                  Your AI employee is connected
                  {whatsappStatus?.phone_number_id_masked ? (
                    <>
                      {" "}
                      (<span className="font-medium text-foreground">
                        {whatsappStatus.phone_number_id_masked}
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
                <Button size="sm" variant="outline" onClick={() => openWhatsAppWizard("intro")}>
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
          businessName={business?.name ?? "your business"}
          startStep={wizardStartStep}
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

type WhatsAppWizardStep = "intro" | "form" | "webhook" | "verify";

/** Real self-serve connection (Sprint 69, ONBOARD-D "guided-manual v1") —
 * no Embedded Signup (that needs Meta's Tech Provider approval, not yet
 * granted). The business owner creates their own Meta System User token on
 * Meta's own site — same as connecting Google Calendar requires a trip
 * through Google's own consent screen — then pastes the four resulting
 * values here. HIRA verifies them against Meta's API before storing
 * anything (POST /api/v1/whatsapp/connect), so a typo'd token fails
 * immediately with a specific reason instead of on the first real customer
 * message. Submitting again (reconnect) just replaces what's stored.
 *
 * Sprint 71: credential verification alone doesn't prove real messages can
 * arrive — the business's own Meta App also needs the Callback URL/Verify
 * Token pasted into its webhook config (DEC-038), a step Meta doesn't expose
 * any way to automate here. So a successful connect now moves to a
 * "webhook" step (Task A) showing those exact values, then a "verify" step
 * (Task B) that polls for a real inbound message instead of just trusting
 * the stored credentials. */
function WhatsAppConnectWizard({
  open,
  onOpenChange,
  businessName,
  startStep,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  businessName: string;
  startStep: WhatsAppWizardStep;
}) {
  const [step, setStep] = useState<WhatsAppWizardStep>(startStep);
  const [phoneNumberId, setPhoneNumberId] = useState("");
  const [wabaId, setWabaId] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [appSecret, setAppSecret] = useState("");
  const [error, setError] = useState<string | null>(null);
  const connectWhatsApp = useConnectWhatsApp();

  // The dialog stays mounted across open/close (only its content is
  // conditionally rendered below), so re-opening needs an explicit sync to
  // whatever step the caller asked for — e.g. Settings' "Check connection"
  // button reopens straight at "verify", not back at "intro".
  useEffect(() => {
    if (open) setStep(startStep);
  }, [open, startStep]);

  function close(open: boolean) {
    if (connectWhatsApp.isPending) return;
    onOpenChange(open);
    if (!open) {
      setStep("intro");
      setPhoneNumberId("");
      setWabaId("");
      setAccessToken("");
      setAppSecret("");
      setError(null);
    }
  }

  async function handleConnect() {
    setError(null);
    try {
      await connectWhatsApp.mutateAsync({
        phone_number_id: phoneNumberId.trim(),
        whatsapp_business_account_id: wabaId.trim(),
        access_token: accessToken.trim(),
        app_secret: appSecret.trim(),
      });
      // Not "connected" yet as far as the owner should believe — the
      // webhook and verify steps below are what actually prove it (Task B).
      setStep("webhook");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong — please try again.");
    }
  }

  const canSubmit = Boolean(
    phoneNumberId.trim() && wabaId.trim() && accessToken.trim() && appSecret.trim(),
  );

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
              <ExternalLink className="mt-0.5 size-4 shrink-0 text-primary" />
              <span className="text-muted-foreground">
                You&apos;ll need four values from your own Meta App: a Phone Number ID, a WhatsApp
                Business Account ID, a System User access token, and your App Secret.
              </span>
            </li>
          </ul>
          <DialogFooter>
            <Button variant="outline" onClick={() => close(false)}>
              Cancel
            </Button>
            <Button onClick={() => setStep("form")}>I have these ready</Button>
          </DialogFooter>
        </DialogContent>
      )}
      {open && step === "form" && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Connect WhatsApp for {businessName}</DialogTitle>
            <DialogDescription>
              From your Meta App&apos;s dashboard — WhatsApp → API Setup, and App → Settings →
              Basic for the App Secret.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">Phone Number ID</span>
              <Input
                value={phoneNumberId}
                onChange={(e) => setPhoneNumberId(e.target.value)}
                placeholder="1234567890"
                disabled={connectWhatsApp.isPending}
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">WhatsApp Business Account ID</span>
              <Input
                value={wabaId}
                onChange={(e) => setWabaId(e.target.value)}
                placeholder="1234567890"
                disabled={connectWhatsApp.isPending}
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">System User access token</span>
              <Input
                type="password"
                value={accessToken}
                onChange={(e) => setAccessToken(e.target.value)}
                placeholder="EAAG…"
                disabled={connectWhatsApp.isPending}
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">App Secret</span>
              <Input
                type="password"
                value={appSecret}
                onChange={(e) => setAppSecret(e.target.value)}
                placeholder="From App → Settings → Basic"
                disabled={connectWhatsApp.isPending}
              />
            </label>
          </div>
          {error && (
            <p className="rounded-md bg-destructive/10 p-2 text-sm text-destructive" role="alert">
              {error}
            </p>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setStep("intro")}
              disabled={connectWhatsApp.isPending}
            >
              Back
            </Button>
            <Button onClick={handleConnect} disabled={!canSubmit || connectWhatsApp.isPending}>
              {connectWhatsApp.isPending ? "Connecting…" : "Connect"}
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
  const { data, isLoading, isError, refetch } = useWhatsAppWebhookConfig();
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
            {isLoading || !data ? (
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
          <Button onClick={onNext} disabled={isLoading || !data}>
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
          Send a WhatsApp message from your phone to your connected business number.
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
