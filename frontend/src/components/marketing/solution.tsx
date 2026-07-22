import { SectionHeader } from "@/components/marketing/section-header";

// The three-card breakdown of what "one employee" means (knowledge, calendar,
// hand-off) used to live here — it's cut because Features below covers the
// same three claims as concrete product capabilities. This section's only
// job is the thesis statement that frames Features; it should not re-list it.
//
// Sprint 68: padding normalized from py-20 to the standard py-24 desktop
// tier (Sprint 67 audit flagged this as the one section matching none of
// the site's three padding tiers), and a border-t added to restore the
// section-divider rhythm every other section already follows.
export function Solution() {
  return (
    <section className="border-t py-16 sm:py-24">
      <div className="mx-auto max-w-3xl px-4 sm:px-6">
        <SectionHeader
          title="One employee, not a bundle of bots"
          description="A single AI agent holds the conversation, your calendar, and your leads together — not three separate tools handing your customer between them, and never pretending to know things it doesn't."
        />
      </div>
    </section>
  );
}
