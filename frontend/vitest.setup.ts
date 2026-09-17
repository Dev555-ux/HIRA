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

// jsdom doesn't provide localStorage in this Node/jsdom combination (Node
// 22+ ships its own experimental global `localStorage` that shadows jsdom's
// without actually being usable, per-file, without the `--localstorage-file`
// flag — a known Node/jsdom interaction, not something real browsers hit).
// A minimal in-memory Web Storage implementation is enough for anything this
// suite needs (the command palette's recent-commands persistence).
if (typeof window !== "undefined" && !window.localStorage) {
  const store = new Map<string, string>();
  Object.defineProperty(window, "localStorage", {
    value: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, String(value)),
      removeItem: (key: string) => void store.delete(key),
      clear: () => void store.clear(),
      key: (index: number) => Array.from(store.keys())[index] ?? null,
      get length() {
        return store.size;
      },
    },
    configurable: true,
  });
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

// jsdom has no IntersectionObserver, and Motion's whileInView has no fallback
// for its absence — without this, every revealed section would stay at
// opacity 0 in tests and assertions about visible content would fail for the
// wrong reason. The stub reports a single intersecting entry, which is the
// state tests care about: the content is on screen.
if (typeof window !== "undefined" && !window.IntersectionObserver) {
  class StubIntersectionObserver implements IntersectionObserver {
    readonly root = null;
    readonly rootMargin = "";
    readonly thresholds: ReadonlyArray<number> = [0];
    constructor(private readonly callback: IntersectionObserverCallback) {}
    observe(target: Element) {
      this.callback(
        [{ isIntersecting: true, target, intersectionRatio: 1 } as IntersectionObserverEntry],
        this,
      );
    }
    unobserve() {}
    disconnect() {}
    takeRecords(): IntersectionObserverEntry[] {
      return [];
    }
  }
  window.IntersectionObserver = StubIntersectionObserver as unknown as typeof IntersectionObserver;
  globalThis.IntersectionObserver = window.IntersectionObserver;
}
