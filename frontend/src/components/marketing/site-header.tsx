import { Bot } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

// "/#anchor", not "#anchor" — these render on every page under (legal) too
// now, not just the homepage; a bare "#anchor" only scrolls if that id
// already exists on the current page, which silently does nothing from
// /privacy, /terms, etc.
const NAV_LINKS = [
  { href: "/#features", label: "Features" },
  { href: "/#how-it-works", label: "How it works" },
  { href: "/#faq", label: "FAQ" },
];

// No mobile nav-toggle: the anchor links simply hide below sm, leaving Sign
// in / Get started always reachable — keeps this header (and the whole
// marketing page) free of client-side JS, matching "fast loading" and
// "clarity over animation".
//
// V4 "Signal & Quiet": dropped the border-b — a hard rule right above a
// deliberately quiet, borderless hero reads as leftover chrome. The glass
// scrim below keeps nav legible over whatever scrolls underneath it; that's
// doing the separation work a hairline used to.
//
// Liquid Glass PR-1 — three changes, all geometry and material, none
// structural (same links, same hrefs, same order, same markup shape):
//
//   1. Container. max-w-6xl (1152px) with the hero on max-w-[1420px] meant
//      the logo sat ~130px inboard of the headline it sits above, and the
//      CTA the same distance inboard of the stage — the page's two most
//      prominent left/right edges disagreeing on where the margin is. Both
//      now share one container and one gutter ramp, so every edge lines up
//      at every breakpoint.
//   2. Material. bg-background/80 + backdrop-blur is a scrim: it hides what
//      passes under it. The glass material samples it instead — same blur
//      radius, but the saturation boost keeps the hero's warm light visible
//      *through* the bar rather than washed to grey behind it.
//   3. Weight. h-16 → h-[4.5rem] and gap-6 → gap-8 between links: the bar
//      was sized for a dashboard chrome, not for the opening frame of a
//      landing page.
// Dark Hero PR-1 — the header carries `dark` for the same reason the hero
// does, and it is the one change that makes a locally-dark hero viable at
// all. The header is a sibling *above* <main>, so a light glass bar sat
// across the top of the dark hero as a hard white band — the seam this was
// supposed to avoid.
//
// The alternative was a scroll listener toggling the header's theme at the
// hero's boundary, which is what most sites do. Rejected: it puts client JS
// into a header that is deliberately JS-free, it flashes the wrong theme
// before hydration, and with JS unavailable it strands either white text on
// a light bar or dark text on a dark one — an accessibility failure in
// exchange for a cosmetic gain.
//
// A permanently dark bar has none of those problems. Over the hero it is
// continuous with it; over the light sections below it reads as a dark
// sticky nav, which is an ordinary and legible pattern rather than a
// compromise. Contrast is measured, not assumed — see the delivery notes.
//
// The fill is overridden to opaque. The header occupies y 0–72 and the hero
// starts *below* it, so at rest the glass samples the light <body>, not the
// hero — a translucent dark fill over a light backdrop rendered as a grey
// band sitting on top of a near-black hero. Overriding the token rather
// than abandoning the utility keeps the sheen and the refraction edge doing
// their work; only the transparency goes. backdrop-filter goes with it,
// since filtering a backdrop nothing can see through is GPU work spent
// every frame of every scroll for no visible result.
// The `!` on the two fill overrides is load-bearing, not decoration: `.dark`
// declares --glass-fill unlayered, Tailwind emits arbitrary properties into
// the utilities layer, and unlayered rules beat layered ones at equal
// specificity — so without it the override silently loses and the bar
// renders as translucent grey over the light body behind it.
export function SiteHeader() {
  return (
    <header className="glass dark sticky top-0 z-30 text-foreground [--glass-fill-strong:var(--background)]! [--glass-fill:var(--background)]! [backdrop-filter:none]">
      <div className="mx-auto flex h-[4.5rem] max-w-[1420px] items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="flex items-center gap-2.5 rounded-sm text-[1.0625rem] font-semibold tracking-tight focus-visible:focus-ring"
        >
          <span className="flex size-8 items-center justify-center rounded-[0.625rem] bg-brand text-brand-foreground shadow-e1">
            <Bot className="size-4" aria-hidden="true" />
          </span>
          HIRA
        </Link>

        <nav aria-label="Primary" className="hidden items-center gap-8 sm:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              // Signal & Depth PR-7 — no keyboard focus treatment at all
              // before this; a Tab landed here with only the browser's
              // default outline, inconsistent with every button on the
              // page. focus-visible:focus-ring is the app's own existing
              // opt-in utility (already used across the dashboard), not a
              // new pattern invented for this fix.
              className="rounded-sm text-[0.9375rem] font-medium text-muted-foreground transition-colors duration-[var(--motion-fast)] hover:text-foreground focus-visible:focus-ring"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-1.5">
          <Button asChild variant="ghost" size="sm" className="rounded-full px-3.5 text-[0.9375rem]">
            <Link href="/sign-in">Sign in</Link>
          </Button>
          {/* rounded-full, matching the hero CTA directly below it — the two
              most important actions on the page were different shapes. */}
          <Button asChild size="sm" className="h-9 rounded-full px-4 text-[0.9375rem]">
            <Link href="/sign-up">Get started</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}
