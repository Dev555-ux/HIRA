import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useInView } from "./use-in-view";

function Probe({ once }: { once?: boolean }) {
  const { ref, inView } = useInView<HTMLDivElement>({ once });
  return (
    <div ref={ref} data-testid="probe">
      {inView ? "visible" : "hidden"}
    </div>
  );
}

describe("useInView", () => {
  const originalIO = globalThis.IntersectionObserver;

  afterEach(() => {
    globalThis.IntersectionObserver = originalIO;
    vi.restoreAllMocks();
  });

  it("falls back to inView=true when IntersectionObserver is unavailable (e.g. jsdom)", () => {
    // @ts-expect-error — simulating an environment without the API
    delete globalThis.IntersectionObserver;
    render(<Probe />);
    expect(screen.getByTestId("probe")).toHaveTextContent("visible");
  });

  it("flips to true once the observed element intersects, then disconnects (once semantics)", () => {
    const disconnect = vi.fn();
    let trigger: (isIntersecting: boolean) => void = () => {};

    class MockObserver {
      constructor(cb: (entries: { isIntersecting: boolean }[]) => void) {
        trigger = (isIntersecting) => cb([{ isIntersecting }]);
      }
      observe = vi.fn();
      disconnect = disconnect;
    }
    // @ts-expect-error — test double
    globalThis.IntersectionObserver = MockObserver;

    render(<Probe />);
    expect(screen.getByTestId("probe")).toHaveTextContent("hidden");

    act(() => trigger(true));
    expect(screen.getByTestId("probe")).toHaveTextContent("visible");
    expect(disconnect).toHaveBeenCalledOnce();
  });
});
