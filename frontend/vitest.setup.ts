import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement layout, so this is simply absent — any component
// that scrolls a ref into view (e.g. Demo Chat's auto-scroll-to-latest-
// message) throws without a stub. A no-op is correct here: tests assert on
// rendered content, never on scroll position.
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}

// Same gap, different API: the signature demo's auto-scroll-to-latest-
// message calls the scroll-container element's own scrollTo, not the
// window's — jsdom implements neither by default.
if (typeof Element !== "undefined" && !Element.prototype.scrollTo) {
  Element.prototype.scrollTo = () => {};
}

// jsdom has no layout engine and therefore no notion of a reduced-motion
// media query either — any component checking prefers-reduced-motion
// throws without this stub. Defaults to "no preference" so tests exercise
// the animated code path unless a test explicitly overrides matchMedia.
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
}
