import Link from "next/link";

// Signal & Depth PR-7 — these 7 links previously had only hover:text-
// foreground, no transition and no focus-visible treatment, unlike
// site-header.tsx's identical-purpose nav links (which already pair the
// same color change with transition-colors duration-[var(--motion-fast)]).
// Same fix as the header: an instant color snap becomes a smooth one, and
// focus-visible:focus-ring (the app's existing opt-in utility, already used
// across the dashboard) replaces the unstyled browser-default outline.
export function SiteFooter() {
  return (
    // Phase 2 — the footer carries `dark`, the same scoped treatment the header
// and hero use. Two reasons, both continuity: a light footer directly under
// FinalCta's dark closing band put a hard horizontal seam at the very end of
// the page, the one place PR-1 had taught the eye to expect a dissolve; and
// the page now opens and closes in the same material, which is what makes
// the whole thing read as one document rather than a dark hero bolted to a
// light page. No layout, link or copy change — the border-t goes because
// there is no longer a tone change for it to mark.
    <footer className="dark bg-background py-8 text-foreground">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 text-sm text-muted-foreground sm:flex-row sm:px-6">
        <p>&copy; {new Date().getFullYear()} HIRA. All rights reserved.</p>
        <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
          <Link href="/sign-in" className="transition-colors duration-[var(--motion-fast)] hover:text-foreground focus-visible:focus-ring">
            Sign in
          </Link>
          <Link href="/sign-up" className="transition-colors duration-[var(--motion-fast)] hover:text-foreground focus-visible:focus-ring">
            Get started
          </Link>
          <Link href="/privacy" className="transition-colors duration-[var(--motion-fast)] hover:text-foreground focus-visible:focus-ring">
            Privacy
          </Link>
          <Link href="/terms" className="transition-colors duration-[var(--motion-fast)] hover:text-foreground focus-visible:focus-ring">
            Terms
          </Link>
          <Link href="/data-deletion" className="transition-colors duration-[var(--motion-fast)] hover:text-foreground focus-visible:focus-ring">
            Data Deletion
          </Link>
          <Link href="/contact" className="transition-colors duration-[var(--motion-fast)] hover:text-foreground focus-visible:focus-ring">
            Contact
          </Link>
          <Link href="/company" className="transition-colors duration-[var(--motion-fast)] hover:text-foreground focus-visible:focus-ring">
            Company
          </Link>
        </div>
      </div>
    </footer>
  );
}
