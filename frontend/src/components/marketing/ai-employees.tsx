"use client";

import { MessageSquare } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { WorkingIndicator } from "@/components/ui/working-indicator";
import { Reveal } from "@/components/marketing/reveal";

const FUTURE_ROLES = ["Sales follow-up", "Support", "Scheduling"];

// Deliberately a compact banner, not a full section-height block: it makes
// one small claim (there will be more AI employees later) that shouldn't
// compete for attention with Problem/Solution/Features above and below it.
export function AiEmployees() {
  // DESIGN-MOTION-001 §7.4: on hover, the employee's working-line does one
  // quiet pass — a preview of "doing the job" — reusing the same primitive
  // the dashboard uses, not a bespoke marketing-only effect.
  const [hovering, setHovering] = useState(false);

  return (
    <section className="border-t py-10 sm:py-12">
      <Reveal className="mx-auto max-w-6xl px-4 sm:px-6">
        <h2 className="sr-only">AI employees, not just automations</h2>
        <Card
          className="mx-auto flex max-w-3xl flex-col items-center gap-4 p-6 text-center sm:flex-row sm:gap-6 sm:text-left"
          onMouseEnter={() => setHovering(true)}
          onMouseLeave={() => setHovering(false)}
          onFocus={() => setHovering(true)}
          onBlur={() => setHovering(false)}
        >
          <div className="flex size-11 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <MessageSquare className="size-5" aria-hidden="true" />
          </div>
          <div className="flex-1">
            <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
              <h3 className="text-base font-semibold">The Receptionist</h3>
              <Badge variant="success">Available now</Badge>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Answers customer questions, books appointments, and escalates what
              it can&apos;t handle — live today, working inside your WhatsApp.
            </p>
            <div className="mt-2 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-xs text-muted-foreground sm:justify-start">
              <span>Next on the roadmap:</span>
              {FUTURE_ROLES.map((role) => (
                <Badge key={role} variant="outline" className="text-muted-foreground">
                  {role}
                </Badge>
              ))}
            </div>
            <WorkingIndicator
              state={hovering ? "working" : "idle"}
              label="The Receptionist"
              className="mt-3"
            />
          </div>
        </Card>
      </Reveal>
    </section>
  );
}
