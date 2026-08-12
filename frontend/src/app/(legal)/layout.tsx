import { SiteFooter } from "@/components/marketing/site-footer";
import { SiteHeader } from "@/components/marketing/site-header";

// Public, unauthenticated chrome — same header/footer as the marketing
// homepage, so Privacy/Terms/Data Deletion/Contact/Company read as part of
// the same site rather than a bolted-on legal subsection.
export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="flex-1">
        <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6 sm:py-20">{children}</div>
      </main>
      <SiteFooter />
    </div>
  );
}
