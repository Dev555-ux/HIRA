import { useEffect, useState } from "react";

// Sprint 66 PR-9 — extracted verbatim from hero.tsx and signature-demo.tsx,
// which each defined this exact function locally (confirmed byte-identical
// before extracting). One shared hook now backs both.
export function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return reduced;
}
