import { AiEmployees } from "@/components/marketing/ai-employees";
import { Faq } from "@/components/marketing/faq";
import { Features } from "@/components/marketing/features";
import { FinalCta } from "@/components/marketing/final-cta";
import { Hero } from "@/components/marketing/hero";
import { HowItWorks } from "@/components/marketing/how-it-works";
import { Journey } from "@/components/marketing/journey";
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
// Vertical-padding scale for every section below. V4 "Signal & Quiet" split
// the old three-tier scale into five, on purpose — deliberate hierarchy
// means sections no longer share one weight:
//
//   Quiet footnote           py-6 sm:py-8              — Trust only
//   Compact band              py-10 sm:py-12            — AiEmployees only
//   Standard section          py-20 sm:py-28            — Journey, Problem,
//                                                          Features, How It
//                                                          Works, FAQ
//   Flagship / hero-adjacent  py-24 sm:py-32(-lg:py-32) — Hero, SignatureDemo
//   Signal band (bg-primary,  py-24 sm:py-32 lg:py-40   — Solution, FinalCta
//     inverted, bespoke type)
//
// The two Signal sections are intentionally the most generously spaced on
// the page — they're the two moments the product asks the reader to
// believe something, everything else is quieter by design. Any new
// section should land on the tier that matches its actual weight rather
// than defaulting to Standard.
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
        <Journey />
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
