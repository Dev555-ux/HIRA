import { BookOpen, CheckCircle2, MessageCircle, Rocket, MessageSquareText } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { useKbEntries } from "@/hooks/use-knowledge-base";
import { embeddedSignupEnabled } from "@/lib/config";
import type { Business } from "@/lib/types";

type StepStatus = "done" | "available" | "blocked";

interface ChecklistStep {
  label: string;
  description: string;
  icon: typeof BookOpen;
  status: StepStatus;
  trailing: React.ReactNode;
}

/** Next-steps shown after signup. Every step's status and trailing control is
 * computed from real data (KB entry count, business.whatsapp_connection_status,
 * business.onboarding_status) — nothing here is a fabricated claim.
 *
 * WhatsApp Connection is now a real, self-serve backend action (Sprint 69,
 * ONBOARD-D) — "Connect"/"Retry" route to Settings, which auto-opens the
 * real connect form (?whatsapp=connect), not a placeholder. Go Live still
 * has no self-serve action (ONBOARDING_IMPLEMENTATION_PLAN.md Milestone F,
 * not this sprint's scope) — "Enable AI" surfaces an honest toast instead of
 * pretending to flip a switch that doesn't exist server-side. */
export function OnboardingChecklist({ business }: { business: Business }) {
  const { data: kbEntries } = useKbEntries();
  const { toast } = useToast();

  const knowledgeImportDone = (kbEntries?.length ?? 0) > 0;
  const whatsappConnected = business.whatsapp_connection_status === "connected";
  // "pending_verification" is the schema's only other non-connected state
  // today (nothing sets it yet — see the Business model) — it's the closest
  // real signal to "something needs your attention," so it maps to Retry
  // rather than Connect.
  const whatsappNeedsRetry = business.whatsapp_connection_status === "pending_verification";
  const isLive = business.onboarding_status === "live";
  // Go Live's real prerequisites: the two steps that actually gate real
  // customer traffic. Test AI is a self-serve sandbox, not a precondition.
  const prerequisitesMet = knowledgeImportDone && whatsappConnected;

  function handleEnableAI() {
    // Sprint 71, Task C: concrete process + timeline instead of an
    // open-ended "reach out" — the founder personally reviews every
    // business before real customer traffic goes live (SEC-3, the
    // prompt-injection guardrail, isn't built yet — see IMPLEMENTATION_PLAN.md),
    // and we already have a channel to reach them: the contact email they
    // gave us at signup, not an invented support address.
    toast({
      title: "Setup looks complete",
      description: business.contact_email
        ? `We review every business personally before enabling real customer conversations. We'll email ${business.contact_email} within 1 business day.`
        : "We review every business personally before enabling real customer conversations. We'll reach out within 1 business day.",
    });
  }

  const steps: ChecklistStep[] = [
    {
      label: "Teach HIRA",
      description: "Add facts about your business, or import them straight from your website.",
      icon: BookOpen,
      status: knowledgeImportDone ? "done" : "available",
      trailing: knowledgeImportDone ? (
        <Badge variant="success" className="animate-fade-in">
          Done
        </Badge>
      ) : (
        <Button asChild size="sm" variant="outline">
          <Link href="/knowledge-base">Get started</Link>
        </Button>
      ),
    },
    {
      label: "WhatsApp Connection",
      description: "Connect the WhatsApp number your customers already message.",
      icon: MessageCircle,
      status: whatsappConnected ? "done" : "blocked",
      trailing: whatsappConnected ? (
        <Badge variant="success" className="animate-fade-in">
          Connected
        </Badge>
      ) : (
        <Button asChild size="sm" variant="outline">
          {/* Track B (ONBOARD-E): only reroutes here when Embedded Signup is
           * actually configured — off by default, so this link is
           * unchanged in production today. */}
          <Link href={embeddedSignupEnabled ? "/connect-whatsapp" : "/settings?whatsapp=connect"}>
            {whatsappNeedsRetry ? "Retry" : "Connect"}
          </Link>
        </Button>
      ),
    },
    {
      label: "Test AI",
      description: "Try HIRA yourself before a real customer does.",
      icon: MessageSquareText,
      status: "available",
      trailing: (
        <Button asChild size="sm" variant="outline">
          <Link href="/demo">Get started</Link>
        </Button>
      ),
    },
    {
      label: "Go Live",
      description: "Turn HIRA on for real customer conversations.",
      icon: Rocket,
      status: isLive ? "done" : prerequisitesMet ? "available" : "blocked",
      trailing: isLive ? (
        <Badge variant="success" className="animate-fade-in">
          Live
        </Badge>
      ) : prerequisitesMet ? (
        <Button size="sm" variant="outline" onClick={handleEnableAI}>
          Enable AI
        </Button>
      ) : (
        <Button size="sm" variant="outline" disabled>
          Complete setup first
        </Button>
      ),
    },
  ];

  const doneCount = steps.filter((step) => step.status === "done").length;

  return (
    <Card className="mb-6 transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-md">
      <CardHeader className="flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="size-4 text-success" />
          <CardTitle className="text-base">Finish setting up {business.name}</CardTitle>
        </div>
        <Badge variant="secondary">
          {doneCount} of {steps.length} done
        </Badge>
      </CardHeader>
      <CardContent>
        <ul className="divide-y">
          {steps.map((step) => (
            <li key={step.label} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted">
                <step.icon className="size-4 text-muted-foreground" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{step.label}</p>
                <p className="truncate text-xs text-muted-foreground">{step.description}</p>
              </div>
              {step.trailing}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
