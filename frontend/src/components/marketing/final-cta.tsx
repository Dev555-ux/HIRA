import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { SectionHeader } from "@/components/marketing/section-header";

export function FinalCta() {
  return (
    <section className="border-t py-16 sm:py-24">
      <div className="mx-auto max-w-2xl px-4 sm:px-6">
        <SectionHeader
          title="Never miss another message again"
          description="Set up your knowledge base, connect WhatsApp, and test HIRA yourself — before a single customer sees a reply."
        />
        <div className="mt-8 flex justify-center">
          <Button asChild size="lg">
            <Link href="/sign-up">
              Get started
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
