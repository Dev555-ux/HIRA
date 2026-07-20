"use client";

import { Bot, CheckCheck, CheckCircle2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

// A scripted, looping conversation — not a video, not a Lottie file, just
// React state + CSS animation (see globals.css's message-in/bubble-in/
// typing-dot/system-pulse keyframes). Grounded in the real Velocity Luxe
// Motors demo knowledge (beta/DEMO_BUSINESS_KNOWLEDGE_VELOCITY_LUXE_MOTORS.md
// §2/§5): the dealership's actual SUV lineup (BMW X7, Mercedes-Benz G-Class,
// Audi Q8 — not the X5/GLE/Q7 trims, which aren't in its real inventory) and
// its real financing terms (12–84 month tenures, §5).
type Beat =
  | { kind: "customer"; id: string; text: string; time: string; hold: number }
  | { kind: "hira"; id: string; text: string; time: string; hold: number }
  | { kind: "typing"; hold: number }
  | { kind: "system"; text: string; hold: number }
  | { kind: "booking"; id: string; day: string; clockTime: string; hold: number }
  | { kind: "end"; hold: number };

const BEATS: Beat[] = [
  { kind: "customer", id: "c1", text: "Hi, I'm looking for a luxury SUV.", time: "9:41 AM", hold: 900 },
  { kind: "typing", hold: 900 },
  {
    kind: "hira",
    id: "h1",
    text: "We currently have:\n• BMW X7\n• Mercedes-Benz G-Class\n• Audi Q8\n\nWould you like to compare them?",
    time: "9:41 AM",
    hold: 2800,
  },
  { kind: "customer", id: "c2", text: "Can I finance the BMW X7?", time: "9:42 AM", hold: 1600 },
  { kind: "typing", hold: 800 },
  {
    kind: "hira",
    id: "h2",
    text: "Yes. Financing is available for up to 84 months.\nWould you like an estimate?",
    time: "9:42 AM",
    hold: 2600,
  },
  { kind: "customer", id: "c3", text: "Book me for a test drive tomorrow.", time: "9:43 AM", hold: 1600 },
  { kind: "typing", hold: 800 },
  { kind: "system", text: "Checking calendar…", hold: 1200 },
  { kind: "booking", id: "b1", day: "Tomorrow", clockTime: "4:00 PM", hold: 2800 },
  { kind: "customer", id: "c4", text: "I'd like to speak with someone.", time: "9:44 AM", hold: 1600 },
  { kind: "typing", hold: 800 },
  {
    kind: "hira",
    id: "h3",
    text: "Absolutely. I've notified one of our sales specialists.\nSomeone will contact you shortly.",
    time: "9:44 AM",
    hold: 2800,
  },
  { kind: "end", hold: 3500 },
];

type RenderedMessage =
  | { kind: "customer"; id: string; text: string; time: string }
  | { kind: "hira"; id: string; text: string; time: string }
  | { kind: "booking"; id: string; day: string; clockTime: string };

type Ephemeral = { kind: "typing" } | { kind: "system"; text: string } | null;

function toRendered(beat: Beat): RenderedMessage | null {
  if (beat.kind === "customer" || beat.kind === "hira" || beat.kind === "booking") {
    return beat;
  }
  return null;
}

const STATIC_MESSAGES: RenderedMessage[] = BEATS.map(toRendered).filter(
  (m): m is RenderedMessage => m !== null,
);

function PhoneFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative mx-auto w-full max-w-[300px]">
      <div className="relative rounded-[2.5rem] border-[6px] border-foreground/10 bg-card p-2 shadow-2xl">
        <div className="absolute left-1/2 top-3 z-10 h-5 w-24 -translate-x-1/2 rounded-full bg-foreground/10" />
        <div className="relative h-[440px] overflow-hidden rounded-[2rem] bg-background">
          {children}
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: RenderedMessage }) {
  if (message.kind === "customer") {
    return (
      <div className="animate-message-in max-w-[80%] rounded-2xl rounded-bl-sm bg-secondary px-3 py-2 text-[13px] leading-snug">
        <p className="whitespace-pre-line">{message.text}</p>
        <p className="mt-1 text-[10px] text-muted-foreground">{message.time}</p>
      </div>
    );
  }

  if (message.kind === "hira") {
    return (
      <div className="animate-message-in ml-auto max-w-[80%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-[13px] leading-snug text-primary-foreground">
        <p className="whitespace-pre-line">{message.text}</p>
        <div className="mt-1 flex items-center justify-end gap-1 text-[10px] text-primary-foreground/70">
          {message.time}
          <CheckCheck className="size-3 shrink-0" aria-hidden="true" />
        </div>
      </div>
    );
  }

  return (
    <div className="animate-bubble-in ml-auto flex max-w-[80%] items-center gap-2 rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-[13px] text-primary-foreground">
      <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
      <span>
        Booked! <span className="font-semibold">{message.day}, {message.clockTime}</span>
      </span>
    </div>
  );
}

function TypingBubble() {
  return (
    <div className="animate-message-in ml-auto flex w-fit items-center gap-1 rounded-2xl rounded-br-sm bg-primary px-3 py-2.5">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="animate-typing-dot size-1.5 rounded-full bg-primary-foreground"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}

function SystemNotice({ text }: { text: string }) {
  return (
    <div className="animate-fade-in flex justify-center">
      <span className="animate-system-pulse rounded-full bg-secondary/70 px-3 py-1 text-[11px] text-muted-foreground">
        {text}
      </span>
    </div>
  );
}

function EndCard() {
  return (
    <div className="animate-fade-in absolute inset-0 flex flex-col items-center justify-center gap-4 bg-background px-6 text-center">
      <span className="flex size-10 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <Bot className="size-5" aria-hidden="true" />
      </span>
      <p className="text-base font-semibold tracking-tight">
        Never miss another customer message.
      </p>
      <span className="rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground">
        Get started
      </span>
    </div>
  );
}

function useReducedMotion() {
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

function DemoWidget() {
  const reducedMotion = useReducedMotion();
  const [beatIndex, setBeatIndex] = useState(0);
  const [messages, setMessages] = useState<RenderedMessage[]>(() => {
    const first = toRendered(BEATS[0]);
    return first ? [first] : [];
  });
  const [ephemeral, setEphemeral] = useState<Ephemeral>(null);
  const [showEnd, setShowEnd] = useState(false);
  const [paused, setPaused] = useState(false);
  const [tabHidden, setTabHidden] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onVisibility = () => setTabHidden(document.hidden);
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  useEffect(() => {
    if (paused || tabHidden || reducedMotion) {
      return;
    }
    const currentHold = BEATS[beatIndex].hold;
    const timer = setTimeout(() => {
      const nextIndex = beatIndex + 1;
      if (nextIndex >= BEATS.length) {
        setShowEnd(false);
        setEphemeral(null);
        const first = toRendered(BEATS[0]);
        setMessages(first ? [first] : []);
        setBeatIndex(0);
        return;
      }
      const beat = BEATS[nextIndex];
      const rendered = toRendered(beat);
      if (rendered) {
        setMessages((prev) => [...prev, rendered]);
        setEphemeral(null);
      } else if (beat.kind === "typing") {
        setEphemeral({ kind: "typing" });
      } else if (beat.kind === "system") {
        setEphemeral({ kind: "system", text: beat.text });
      } else if (beat.kind === "end") {
        setShowEnd(true);
        setEphemeral(null);
      }
      setBeatIndex(nextIndex);
    }, currentHold);
    return () => clearTimeout(timer);
  }, [beatIndex, paused, tabHidden, reducedMotion]);

  useEffect(() => {
    if (reducedMotion) return;
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, ephemeral, reducedMotion]);

  const summary =
    "Demo: a customer asks about SUVs, HIRA answers from the dealership's own inventory, explains financing, books a test drive, and hands off to a person when asked.";

  if (reducedMotion) {
    return (
      <div role="img" aria-label={summary} className="w-fit">
        <PhoneFrame>
          <div aria-hidden="true" className="flex h-full flex-col gap-2 overflow-y-auto p-3">
            {STATIC_MESSAGES.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
          </div>
        </PhoneFrame>
      </div>
    );
  }

  return (
    <div
      role="group"
      aria-label={`${summary} Animation pauses while hovered or focused.`}
      tabIndex={0}
      className="w-fit rounded-[2.5rem] outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div aria-hidden="true">
        <PhoneFrame>
          <div ref={scrollRef} className="flex h-full flex-col gap-2 overflow-y-auto p-3 scroll-smooth">
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
            {ephemeral?.kind === "typing" && <TypingBubble />}
            {ephemeral?.kind === "system" && <SystemNotice text={ephemeral.text} />}
          </div>
          {showEnd && <EndCard />}
        </PhoneFrame>
      </div>
    </div>
  );
}

// Section-level wrapper — same slot Product Proof occupied (immediately
// below Hero), same "SEE IT IN ACTION" eyebrow treatment, so this is a
// drop-in replacement rather than a new page section.
export function SignatureDemo() {
  return (
    <section className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 sm:pb-24">
      <h2 className="text-center text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        See it in action
      </h2>
      <div className="mt-6">
        <DemoWidget />
      </div>
    </section>
  );
}
