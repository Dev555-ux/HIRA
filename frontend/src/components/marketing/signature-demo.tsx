"use client";

import { Bot, CheckCheck, CheckCircle2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

// The story this demo tells, beat by beat: a quiet, empty stage (nobody's
// at the business right now) — a single soft pulse (a message has just
// arrived) — a competent, unhurried resolution (question, financing,
// booking, human handoff) — a settled close. The silence at the start and
// the settle at the end are the point: the promise on this page is "never
// miss a message," and this restages that as something that happens, not
// just something that's claimed.
//
// Grounded in the real Velocity Luxe Motors demo knowledge
// (beta/DEMO_BUSINESS_KNOWLEDGE_VELOCITY_LUXE_MOTORS.md §2/§5): the
// dealership's actual SUV lineup (BMW X7, Mercedes-Benz G-Class, Audi Q8)
// and its real financing terms (12–84 month tenures).
type Beat =
  | { kind: "intro"; hold: number }
  | { kind: "customer"; id: string; text: string; time: string; hold: number }
  | { kind: "hira"; id: string; text: string; time: string; hold: number }
  | { kind: "typing"; hold: number }
  | { kind: "system"; text: string; hold: number }
  | { kind: "booking"; id: string; day: string; clockTime: string; hold: number }
  | { kind: "resolve"; hold: number }
  | { kind: "end"; hold: number };

const BEATS: Beat[] = [
  { kind: "intro", hold: 1600 },
  { kind: "customer", id: "c1", text: "Hi, I'm looking for a luxury SUV.", time: "9:41 AM", hold: 900 },
  { kind: "typing", hold: 900 },
  {
    kind: "hira",
    id: "h1",
    text: "We currently have:\n• BMW X7\n• Mercedes-Benz G-Class\n• Audi Q8\n\nWould you like to compare them?",
    time: "9:41 AM",
    hold: 2600,
  },
  { kind: "customer", id: "c2", text: "Can I finance the BMW X7?", time: "9:42 AM", hold: 1500 },
  { kind: "typing", hold: 800 },
  {
    kind: "hira",
    id: "h2",
    text: "Yes. Financing is available for up to 84 months.\nWould you like an estimate?",
    time: "9:42 AM",
    hold: 2400,
  },
  { kind: "customer", id: "c3", text: "Book me for a test drive tomorrow.", time: "9:43 AM", hold: 1500 },
  { kind: "typing", hold: 800 },
  { kind: "system", text: "Checking calendar…", hold: 1100 },
  { kind: "booking", id: "b1", day: "Tomorrow", clockTime: "4:00 PM", hold: 2600 },
  { kind: "customer", id: "c4", text: "I'd like to speak with someone.", time: "9:44 AM", hold: 1500 },
  { kind: "typing", hold: 800 },
  {
    kind: "hira",
    id: "h3",
    text: "Absolutely. I've notified one of our sales specialists.\nSomeone will contact you shortly.",
    time: "9:44 AM",
    hold: 2600,
  },
  { kind: "resolve", hold: 1400 },
  { kind: "end", hold: 3500 },
];

type RenderedMessage =
  | { kind: "customer"; id: string; text: string; time: string }
  | { kind: "hira"; id: string; text: string; time: string }
  | { kind: "booking"; id: string; day: string; clockTime: string };

type Ephemeral = { kind: "typing" } | { kind: "system"; text: string } | null;
type Phase = "intro" | "conversation" | "resolving" | "end";

function toRendered(beat: Beat): RenderedMessage | null {
  if (beat.kind === "customer" || beat.kind === "hira" || beat.kind === "booking") {
    return beat;
  }
  return null;
}

function phaseForBeat(beat: Beat): Phase {
  if (beat.kind === "intro") return "intro";
  if (beat.kind === "resolve") return "resolving";
  if (beat.kind === "end") return "end";
  return "conversation";
}

const STATIC_MESSAGES: RenderedMessage[] = BEATS.map(toRendered).filter(
  (m): m is RenderedMessage => m !== null,
);

// Ambient light behind the panel — always alive, even in the silent
// opening beat — and its own separate warmth shift once the story
// resolves. Deliberately a halo around the panel, not inside it: the
// message thread itself always stays perfectly legible.
function AmbientGlow({ phase }: { phase: Phase }) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-stage-breathe pointer-events-none absolute -inset-10 rounded-[3rem] blur-3xl transition-colors duration-1000",
        phase === "resolving" || phase === "end" ? "bg-success/25" : "bg-white/10",
      )}
    />
  );
}

// Deliberately not a phone mockup — no notch, no bezel, no home indicator.
// A softly bordered, backlit panel instead: it belongs to HIRA's own card
// language (rounded-2xl border bg-card, used everywhere else on this
// page), not to a device manufacturer's marketing photography.
function ConversationPanel({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative w-[min(320px,88vw)]">
      <div className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-card shadow-[0_30px_80px_-25px_rgba(0,0,0,0.7)]">
        <div className="h-px w-full bg-gradient-to-r from-transparent via-white/25 to-transparent" />
        <div className="relative h-[440px] overflow-hidden">{children}</div>
      </div>
    </div>
  );
}

function IntroPulse() {
  return (
    <div className="flex h-full items-center justify-center">
      <span className="animate-intro-pulse size-2 rounded-full bg-foreground/30" aria-hidden="true" />
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
  const [phase, setPhase] = useState<Phase>("intro");
  const [messages, setMessages] = useState<RenderedMessage[]>([]);
  const [ephemeral, setEphemeral] = useState<Ephemeral>(null);
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
        setPhase("intro");
        setEphemeral(null);
        setMessages([]);
        setBeatIndex(0);
        return;
      }
      const beat = BEATS[nextIndex];
      const rendered = toRendered(beat);
      setPhase(phaseForBeat(beat));
      if (rendered) {
        setMessages((prev) => [...prev, rendered]);
        setEphemeral(null);
      } else if (beat.kind === "typing") {
        setEphemeral({ kind: "typing" });
      } else if (beat.kind === "system") {
        setEphemeral({ kind: "system", text: beat.text });
      } else {
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
      <div role="img" aria-label={summary} className="relative w-fit">
        <ConversationPanel>
          <div aria-hidden="true" className="flex h-full flex-col gap-2 overflow-y-auto p-3">
            {STATIC_MESSAGES.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
          </div>
        </ConversationPanel>
      </div>
    );
  }

  return (
    <div
      role="group"
      aria-label={`${summary} Animation pauses while hovered or focused.`}
      tabIndex={0}
      className="relative w-fit rounded-[2rem] outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div aria-hidden="true">
        <AmbientGlow phase={phase} />
        <ConversationPanel>
          {phase === "intro" ? (
            <IntroPulse />
          ) : (
            <div
              className={cn(
                "flex h-full flex-col gap-2 overflow-y-auto p-3 scroll-smooth transition-all duration-700 ease-out",
                phase === "resolving" && "scale-[0.97] opacity-30",
              )}
              ref={scrollRef}
            >
              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
              {ephemeral?.kind === "typing" && <TypingBubble />}
              {ephemeral?.kind === "system" && <SystemNotice text={ephemeral.text} />}
            </div>
          )}
          {phase === "end" && <EndCard />}
        </ConversationPanel>
      </div>
    </div>
  );
}

// Section-level wrapper: the demo's own darkened stage, deliberately
// distinct from the page's normal background in either theme — a spotlit
// moment, not another flat card section. The panel inside still uses the
// page's own bg-card/bg-primary tokens, so it reads as a bright, lit
// screen in a dark room rather than adopting a whole separate palette.
export function SignatureDemo() {
  return (
    <section className="relative overflow-hidden bg-[#050506] py-20 sm:py-28">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_60%_50%_at_50%_35%,rgba(255,255,255,0.05),transparent_70%)]" />
      <div className="relative mx-auto max-w-6xl px-4 sm:px-6">
        <h2 className="text-center text-xs font-medium uppercase tracking-[0.2em] text-white/40">
          See it in action
        </h2>
        <div className="mt-10 flex justify-center">
          <DemoWidget />
        </div>
      </div>
    </section>
  );
}
