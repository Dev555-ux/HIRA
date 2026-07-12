import { Bot, MessageSquare } from "lucide-react";
import { Badge } from "@/components/ui/badge";

const FUTURE_ROLES = ["Sales follow-up", "Support", "Scheduling"];

export function AiEmployees() {
  return (
    <section className="border-t py-16 sm:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight">AI employees, not just automations</h2>
          <p className="mt-4 text-muted-foreground">
            HIRA is built as the first in a lineup of AI employees a business can
            put to work on a specific job. Today, that&apos;s the Receptionist.
          </p>
        </div>

        <div className="mx-auto mt-12 max-w-lg rounded-2xl border bg-card p-8 text-center shadow-sm">
          <div className="mx-auto flex size-14 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <MessageSquare className="size-6" aria-hidden="true" />
          </div>
          <h3 className="mt-4 text-xl font-semibold">The Receptionist</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Answers customer questions, books appointments, and escalates what it
            can&apos;t handle — live today, working inside your WhatsApp.
          </p>
          <Badge variant="success" className="mt-4">
            Available now
          </Badge>
        </div>

        <div className="mx-auto mt-8 flex max-w-lg flex-col items-center gap-3 text-center">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Bot className="size-4" aria-hidden="true" />
            More AI employees are on the roadmap
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2">
            {FUTURE_ROLES.map((role) => (
              <Badge key={role} variant="outline" className="text-muted-foreground">
                {role}
              </Badge>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
