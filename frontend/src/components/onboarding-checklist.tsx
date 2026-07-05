import { BookOpen, CheckCircle2, MessageCircle, Rocket, MessageSquareText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ChecklistStep {
  label: string;
  description: string;
  icon: typeof BookOpen;
}

const STEPS: ChecklistStep[] = [
  {
    label: "Knowledge Import",
    description: "Teach HIRA about your business from your website, PDFs, or FAQs.",
    icon: BookOpen,
  },
  {
    label: "WhatsApp Connection",
    description: "Connect the WhatsApp number your customers already message.",
    icon: MessageCircle,
  },
  {
    label: "Test AI",
    description: "Try HIRA yourself before a real customer does.",
    icon: MessageSquareText,
  },
  {
    label: "Go Live",
    description: "Turn HIRA on for real customer conversations.",
    icon: Rocket,
  },
];

/** Placeholder next-steps shown after signup. None of these steps are wired
 * up yet (see ONBOARDING_IMPLEMENTATION_PLAN.md Milestones B-F) — this card
 * only orients a newly-provisioned business, it doesn't drive any behavior. */
export function OnboardingChecklist({ businessName }: { businessName: string }) {
  return (
    <Card className="mb-6">
      <CardHeader className="flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="size-4 text-success" />
          <CardTitle className="text-base">Finish setting up {businessName}</CardTitle>
        </div>
        <Badge variant="secondary">1 of 5 done</Badge>
      </CardHeader>
      <CardContent>
        <ul className="divide-y">
          {STEPS.map((step) => (
            <li key={step.label} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted">
                <step.icon className="size-4 text-muted-foreground" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{step.label}</p>
                <p className="truncate text-xs text-muted-foreground">{step.description}</p>
              </div>
              <Badge variant="outline">Coming soon</Badge>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
