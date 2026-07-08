import { BookOpen, CheckCircle2, MessageCircle, Rocket, MessageSquareText } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useKbEntries } from "@/hooks/use-knowledge-base";
import type { Business } from "@/lib/types";

type StepStatus = "done" | "available" | "unavailable";

interface ChecklistStep {
  label: string;
  description: string;
  icon: typeof BookOpen;
  href?: string;
  status: StepStatus;
}

/** Next-steps shown after signup. Status per step is computed from real data
 * (KB entry count, business.whatsapp_connection_status, business.onboarding_status)
 * — nothing here is a fabricated claim. "Knowledge Import" and "Test AI" are
 * already-live features (linked); "WhatsApp Connection" and "Go Live" have no
 * self-serve path yet, so they stay honestly labeled "Coming soon"
 * (see ONBOARDING_IMPLEMENTATION_PLAN.md Milestones D/F). */
export function OnboardingChecklist({ business }: { business: Business }) {
  const { data: kbEntries } = useKbEntries();

  const steps: ChecklistStep[] = [
    {
      label: "Knowledge Import",
      description: "Teach HIRA about your business from your website, PDFs, or FAQs.",
      icon: BookOpen,
      href: "/knowledge-base",
      status: (kbEntries?.length ?? 0) > 0 ? "done" : "available",
    },
    {
      label: "WhatsApp Connection",
      description: "Connect the WhatsApp number your customers already message.",
      icon: MessageCircle,
      status: business.whatsapp_connection_status === "connected" ? "done" : "unavailable",
    },
    {
      label: "Test AI",
      description: "Try HIRA yourself before a real customer does.",
      icon: MessageSquareText,
      href: "/playground",
      status: "available",
    },
    {
      label: "Go Live",
      description: "Turn HIRA on for real customer conversations.",
      icon: Rocket,
      status: business.onboarding_status === "live" ? "done" : "unavailable",
    },
  ];

  const doneCount = steps.filter((step) => step.status === "done").length;

  return (
    <Card className="mb-6">
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
              {step.status === "done" && <Badge variant="success">Done</Badge>}
              {step.status === "unavailable" && <Badge variant="outline">Coming soon</Badge>}
              {step.status === "available" && step.href && (
                <Button asChild size="sm" variant="outline">
                  <Link href={step.href}>Get started</Link>
                </Button>
              )}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
