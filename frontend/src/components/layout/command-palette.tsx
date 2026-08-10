"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Search } from "lucide-react";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { navGroups, navItems, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

// DESIGN-MOTION-001 §10.28: "command palette remembers recent commands and
// surfaces them first." Persisted across visits (not just the session) since
// a founder's most-used pages are a stable habit, not a per-tab thing.
// Failure (private browsing, quota, disabled storage) degrades to "no
// recents" — never an error surfaced for what's purely a convenience.
const RECENT_KEY = "hira:command-palette:recent";
const MAX_RECENT = 3;

function loadRecentHrefs(): string[] {
  try {
    const raw = window.localStorage.getItem(RECENT_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function saveRecentHrefs(hrefs: string[]) {
  try {
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(hrefs));
  } catch {
    // Best-effort; recents are a nicety, not a feature worth failing loudly over.
  }
}

// Subsequence match ("cust" -> "Customers", "appoint" -> "Appointments") —
// enough for a ~12-route list; a scoring/fuzzy library would be solving a
// problem this data size doesn't have.
function fuzzyMatch(query: string, label: string): boolean {
  const q = query.toLowerCase();
  const t = label.toLowerCase();
  let qi = 0;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) qi++;
  }
  return qi === q.length;
}

interface ResultGroup {
  label: string | null;
  items: NavItem[];
}

// IMPLEMENTATION-ROADMAP-001 M16. Hand-built on the existing Radix Dialog
// dependency (already used by AppShell's mobile drawer) rather than a new
// package (cmdk) — matching this codebase's established anti-new-dependency
// stance (DEC-031) and the roadmap's own recommendation to evaluate this
// first. Deliberately does not reuse ui/dialog.tsx's DialogContent: that
// primitive is a centered message-box shape (title/description/close-X) for
// confirmations and forms — reusing it here would read as exactly the
// "generic searchable modal" this is meant to feel nothing like. Built
// directly on the same Radix primitives AppShell's drawer already uses,
// with the palette's own top-anchored, search-first shape instead.
export function CommandPalette({
  open,
  onOpenChange,
  triggerRef,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The element to return focus to on close — captured by the caller at
   *  the moment it requests open, since Radix's own restore assumes
   *  Dialog.Root was already mounted (closed) beforehand. This palette is
   *  lazy-mounted on first use (dynamic import, M16's performance
   *  requirement), so its very first open mounts directly into the open
   *  state — exactly the case Radix's default restore doesn't reliably
   *  handle. */
  triggerRef: React.RefObject<Element | null>;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [recentHrefs, setRecentHrefs] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const listboxId = useId();

  // Fresh on every open, same as Spotlight/Raycast — a stale query from last
  // time isn't useful, and an empty box is the honest starting state. Recents
  // are re-read from storage on each open (not kept live in state while
  // closed) since nothing else in this component can change them meanwhile.
  useEffect(() => {
    if (!open) {
      setQuery("");
      setActiveIndex(0);
    } else {
      setRecentHrefs(loadRecentHrefs());
    }
  }, [open]);

  const resultGroups: ResultGroup[] = useMemo(() => {
    if (query.trim() === "") {
      const recentItems = recentHrefs
        .map((href) => navItems.find((item) => item.href === href))
        .filter((item): item is NavItem => Boolean(item));
      if (recentItems.length === 0) return navGroups;
      // Recent items are pulled out of whichever group they'd normally sit
      // in for this view — an href appearing twice would break keyboard nav
      // (activeIndex math and React keys both assume one row per href).
      const recentSet = new Set(recentItems.map((item) => item.href));
      const rest = navGroups
        .map((group) => ({
          label: group.label,
          items: group.items.filter((item) => !recentSet.has(item.href)),
        }))
        .filter((group) => group.items.length > 0);
      return [{ label: "Recent", items: recentItems }, ...rest];
    }
    return navGroups
      .map((group) => ({
        label: group.label,
        items: group.items.filter((item) => fuzzyMatch(query, item.label)),
      }))
      .filter((group) => group.items.length > 0);
  }, [query, recentHrefs]);

  const flatResults = useMemo(() => resultGroups.flatMap((g) => g.items), [resultGroups]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  function activate(item: NavItem) {
    saveRecentHrefs([item.href, ...recentHrefs.filter((href) => href !== item.href)].slice(0, MAX_RECENT));
    onOpenChange(false);
    router.push(item.href);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, flatResults.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = flatResults[activeIndex];
      if (item) activate(item);
    }
  }

  const activeItem = flatResults[activeIndex];
  const activeOptionId = activeItem ? `${listboxId}-${activeItem.href}` : undefined;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[var(--z-overlay)] bg-black/50 backdrop-blur-backdrop-sm data-[state=open]:animate-overlay-show data-[state=closed]:animate-overlay-hide" />
        <Dialog.Content
          onOpenAutoFocus={(e) => {
            e.preventDefault();
            inputRef.current?.focus();
          }}
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            if (triggerRef.current instanceof HTMLElement) triggerRef.current.focus();
          }}
          className="fixed left-1/2 top-[15vh] z-[var(--z-dialog)] w-full max-w-xl -translate-x-1/2 overflow-hidden rounded-xl border bg-card text-card-foreground shadow-e4 data-[state=open]:animate-dialog-content-show data-[state=closed]:animate-dialog-content-hide"
        >
          <Dialog.Title className="sr-only">Search</Dialog.Title>
          <Dialog.Description className="sr-only">
            Search for a page and press Enter to go there.
          </Dialog.Description>

          <div className="flex items-center gap-3 border-b px-4">
            <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              role="combobox"
              aria-expanded={open}
              aria-controls={listboxId}
              aria-activedescendant={activeOptionId}
              aria-autocomplete="list"
              aria-label="Search pages"
              placeholder="Search pages..."
              autoComplete="off"
              spellCheck={false}
              className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
            <kbd className="hidden shrink-0 rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:block">
              Esc
            </kbd>
          </div>

          <div
            id={listboxId}
            role="listbox"
            aria-label="Search results"
            className="max-h-[60vh] overflow-y-auto overscroll-contain p-2"
          >
            {flatResults.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-muted-foreground">
                No pages match &ldquo;{query}&rdquo;.
              </p>
            ) : (
              resultGroups.map((group, gi) => (
                <div key={group.label ?? `ungrouped-${gi}`} className="mb-1 last:mb-0">
                  {group.label && (
                    <p className="px-3 py-1.5 type-caption font-medium uppercase tracking-wide text-muted-foreground">
                      {group.label}
                    </p>
                  )}
                  {group.items.map((item) => {
                    const index = flatResults.indexOf(item);
                    const isActive = index === activeIndex;
                    const isCurrentRoute =
                      pathname === item.href || pathname.startsWith(`${item.href}/`);
                    const Icon = item.icon;
                    return (
                      <div
                        key={item.href}
                        id={`${listboxId}-${item.href}`}
                        role="option"
                        aria-selected={isActive}
                        onMouseEnter={() => setActiveIndex(index)}
                        onClick={() => activate(item)}
                        className={cn(
                          "flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-sm",
                          isActive
                            ? "bg-secondary text-secondary-foreground"
                            : "text-foreground",
                        )}
                      >
                        <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                        <span className="flex-1">{item.label}</span>
                        {isCurrentRoute && (
                          <span className="size-1.5 shrink-0 rounded-full bg-brand" aria-hidden="true" />
                        )}
                      </div>
                    );
                  })}
                </div>
              ))
            )}
          </div>

          {/* Announced to screen readers on every result-set change, without
              duplicating the visible (already announced-via-listbox) list. */}
          <p className="sr-only" role="status" aria-live="polite">
            {flatResults.length === 0
              ? `No results for ${query}`
              : `${flatResults.length} result${flatResults.length === 1 ? "" : "s"}`}
          </p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
