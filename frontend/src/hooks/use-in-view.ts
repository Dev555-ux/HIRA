import { useEffect, useRef, useState } from "react";

// DESIGN-MOTION-001 §7.5: section content enters via IntersectionObserver,
// once — never re-triggering on scroll-up (re-triggering reads as cheap).
// Fires once and disconnects; a component that needs continuous visibility
// tracking (e.g. pausing a loop while offscreen, §7.3) should pass
// `once: false` instead.
//
// Falls back to visible when IntersectionObserver isn't available (older
// browsers, or jsdom in tests, which doesn't implement it) — content must
// never be permanently invisible just because the observer API is missing.
//
// Starts `false` unconditionally (never `typeof IntersectionObserver ===
// "undefined"` in the initial useState) — that check is true during SSR
// (no DOM in Node) and false on a browser client, so using it as the
// initial state produced mismatched server/client markup and a real
// hydration error the first time this was tried in an actual browser
// (jsdom masked it in tests, since jsdom lacks the API too and so agreed
// with the server). The fallback now happens inside the effect instead —
// same "check only in an effect" fix already used by useReducedMotion/
// useIsCompact in signature-demo.tsx for the identical class of bug.
export function useInView<T extends HTMLElement>({
  once = true,
  rootMargin = "0px 0px -10% 0px",
}: { once?: boolean; rootMargin?: string } = {}) {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const node = ref.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          if (once) observer.disconnect();
        } else if (!once) {
          setInView(false);
        }
      },
      { rootMargin },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [once, rootMargin]);

  return { ref, inView };
}
