import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement layout, so this is simply absent — any component
// that scrolls a ref into view (e.g. Demo Chat's auto-scroll-to-latest-
// message) throws without a stub. A no-op is correct here: tests assert on
// rendered content, never on scroll position.
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
