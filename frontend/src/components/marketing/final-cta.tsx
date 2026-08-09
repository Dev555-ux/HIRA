"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { WorkingIndicator } from "@/components/ui/working-indicator";
import { Reveal } from "@/components/marketing/reveal";
import { SectionHeader } from "@/components/marketing/section-header";

export function FinalCta() {
  // DESIGN-MOTION-001 §7.8: hover does one working-line pass beneath the
  // final CTA — the last thing a visitor sees before converting is a
  // glimpse of the employee ready to start. No pulsing/breathing on its own.
  const [hovering, setHovering] = useState(false);

  return (
    <section className="border-t py-16 sm:py-24">
      <Reveal className="mx-auto max-w-2xl px-4 sm:px-6">
        <SectionHeader
          title="Never miss another message again"
          description="Set up your knowledge base, connect WhatsApp, and test HIRA yourself — before a single customer sees a reply."
        />
        <div className="mt-8 flex flex-col items-center gap-3">
          <Button
            asChild
            size="lg"
            onMouseEnter={() => setHovering(true)}
            onMouseLeave={() => setHovering(false)}
            onFocus={() => setHovering(true)}
            onBlur={() => setHovering(false)}
          >
            <Link href="/sign-up">
              Get started
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
          <WorkingIndicator
            state={hovering ? "working" : "idle"}
            label="Ready to start"
            className="w-24"
          />
        </div>
      </Reveal>
    </section>
  );
}
