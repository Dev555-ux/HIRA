import { AiEmployees } from "@/components/marketing/ai-employees";
import { Faq } from "@/components/marketing/faq";
import { Features } from "@/components/marketing/features";
import { FinalCta } from "@/components/marketing/final-cta";
import { Hero } from "@/components/marketing/hero";
import { HowItWorks } from "@/components/marketing/how-it-works";
import { Problem } from "@/components/marketing/problem";
import { SignatureDemo } from "@/components/marketing/signature-demo";
import { SiteFooter } from "@/components/marketing/site-footer";
import { SiteHeader } from "@/components/marketing/site-header";
import { Solution } from "@/components/marketing/solution";
import { Trust } from "@/components/marketing/trust";

// Hero states the problem and SignatureDemo proves the fix immediately after
// — a visitor sees the promise and its evidence within the first two
// sections, before Problem makes the deeper case for anyone not yet sold.
//
// Sprint 68 — documented vertical-padding scale for every section below
// (Sprint 67 audit: six of eight sections already converged on the middle
// tier; Solution was the one outlier, now fixed). Any new section should
// pick one of these three rather than inventing a fourth:
//
//   Compact band            py-10 sm:py-12   (40 → 48px)   — Trust, AiEmployees
//   Standard section        py-16 sm:py-24   (64 → 96px)   — everything else
//   Flagship / hero-adjacent py-24 sm:py-32  (96 → 128px)  — SignatureDemo only
//
// Footer (py-8, fixed) is deliberately outside this scale — it's a closing
// utility bar, not a narrative section, and was never part of the rhythm
// the scale above describes.
export function MarketingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
      >
        Skip to content
      </a>
      <SiteHeader />
      <main id="main-content" tabIndex={-1} className="flex-1 focus:outline-none">
        <Hero />
        <SignatureDemo />
        <Trust />
        <Problem />
        <Solution />
        <AiEmployees />
        <Features />
        <HowItWorks />
        <Faq />
        <FinalCta />
      </main>
      <SiteFooter />
    </div>
  );
}
