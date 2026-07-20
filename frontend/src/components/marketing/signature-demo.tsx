"use client";

import {
  CalendarCheck,
  CalendarSearch,
  Check,
  CheckCheck,
  CheckCircle2,
  PackageSearch,
  Search,
  UserCheck,
  Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

// Two panels, one story: the left shows what the customer sees; the right
// shows what HIRA is actually doing to produce it. Neither works alone —
// the left without the right is just a chat animation; the right without
// the left is an abstract checklist. Together, even on a single paused
// frame, they answer "is this AI actually doing work?" without needing
// any copy outside the widget itself.
//
// Grounded in the real Velocity Luxe Motors demo knowledge
// (beta/DEMO_BUSINESS_KNOWLEDGE_VELOCITY_LUXE_MOTORS.md §2/§5): the
// dealership's actual SUV lineup (BMW X7, Mercedes-Benz G-Class, Audi Q8)
// and its real financing terms (12–84 month tenures).
type StepId = "search" | "found" | "financing" | "calendar" | "booking" | "escalate";
type StepStatus = "pending" | "active" | "done";

type RenderedMessage =
  | { kind: "customer"; id: string; text: string; time: string }
  | { kind: "hira"; id: string; text: string; time: string }
  | { kind: "booking"; id: string; day: string; clockTime: string };

type Beat = {
  hold: number;
  message?: RenderedMessage;
  typing?: boolean;
  steps?: Partial<Record<StepId, StepStatus>>;
  payoff?: boolean;
};

const STEP_DEFS: { id: StepId; label: string; icon: typeof Search }[] = [
  { id: "search", label: "Searching Business Knowledge", icon: Search },
  { id: "found", label: "Found matching inventory", icon: PackageSearch },
  { id: "financing", label: "Explaining financing", icon: Wallet },
  { id: "calendar", label: "Checking calendar availability", icon: CalendarSearch },
  { id: "booking", label: "Booking appointment", icon: CalendarCheck },
  { id: "escalate", label: "Escalating to sales specialist", icon: UserCheck },
];

const PENDING_STEPS: Record<StepId, StepStatus> = {
  search: "pending",
  found: "pending",
  financing: "pending",
  calendar: "pending",
  booking: "pending",
  escalate: "pending",
};

const DONE_STEPS: Record<StepId, StepStatus> = {
  search: "done",
  found: "done",
  financing: "done",
  calendar: "done",
  booking: "done",
  escalate: "done",
};

const BEATS: Beat[] = [
  {
    hold: 1400,
    message: { kind: "customer", id: "c1", text: "Hi! Looking for a luxury SUV 👀", time: "9:41 AM" },
    steps: { search: "active" },
  },
  { hold: 700, typing: true },
  {
    hold: 2200,
    message: {
      kind: "hira",
      id: "h1",
      text: "We've got the BMW X7, Mercedes G-Class, and Audi Q8 in stock. Want a quick comparison?",
      time: "9:41 AM",
    },
    steps: { search: "done", found: "done" },
  },
  { hold: 1200, message: { kind: "customer", id: "c2", text: "Can I finance the X7?", time: "9:42 AM" } },
  { hold: 650, typing: true, steps: { financing: "active" } },
  {
    hold: 2000,
    message: { kind: "hira", id: "h2", text: "Yes — up to 84 months. Want an estimate?", time: "9:42 AM" },
    steps: { financing: "done" },
  },
  {
    hold: 1200,
    message: { kind: "customer", id: "c3", text: "Book me a test drive tomorrow", time: "9:43 AM" },
  },
  { hold: 750, typing: true, steps: { calendar: "active" } },
  { hold: 1300, typing: true, steps: { calendar: "done", booking: "active" } },
  {
    hold: 2200,
    message: { kind: "booking", id: "b1", day: "Tomorrow", clockTime: "4:00 PM" },
    steps: { booking: "done" },
  },
  {
    hold: 1200,
    message: { kind: "customer", id: "c4", text: "Can I talk to someone directly?", time: "9:44 AM" },
  },
  { hold: 650, typing: true, steps: { escalate: "active" } },
  {
    hold: 2200,
    message: {
      kind: "hira",
      id: "h3",
      text: "Of course — Priya from our sales team will call you shortly.",
      time: "9:44 AM",
    },
    steps: { escalate: "done" },
  },
  { hold: 3400, payoff: true },
];

const STATIC_MESSAGES: RenderedMessage[] = BEATS.map((b) => b.message).filter(
  (m): m is RenderedMessage => m !== undefined,
);

function MessageBubble({ message }: { message: RenderedMessage }) {
  if (message.kind === "customer") {
    return (
      <div className="animate-message-in max-w-[85%] rounded-2xl rounded-bl-sm bg-secondary px-3 py-2 text-[13px] leading-snug">
        <p>{message.text}</p>
        <p className="mt-1 text-[10px] text-muted-foreground">{message.time}</p>
      </div>
    );
  }

  if (message.kind === "hira") {
    return (
      <div className="animate-message-in ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-[13px] leading-snug text-primary-foreground">
        <p>{message.text}</p>
        <div className="mt-1 flex items-center justify-end gap-1 text-[10px] text-primary-foreground/70">
          {message.time}
          <CheckCheck className="size-3 shrink-0" aria-hidden="true" />
        </div>
      </div>
    );
  }

  return (
    <div className="animate-bubble-in ml-auto flex max-w-[85%] items-center gap-2 rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-[13px] text-primary-foreground">
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

// The left panel: exactly what the customer sees on WhatsApp, nothing more.
function ConversationPanel({
  messages,
  showTyping,
}: {
  messages: RenderedMessage[];
  showTyping: boolean;
}) {
  return (
    <div className="flex h-full min-h-[420px] flex-col rounded-2xl border border-white/10 bg-card shadow-[0_30px_80px_-25px_rgba(0,0,0,0.7)]">
      <div className="flex items-center gap-2 border-b border-border/60 px-5 py-4">
        <span className="size-2 rounded-full bg-success" />
        <span className="text-xs font-medium text-muted-foreground">WhatsApp · Velocity Luxe Motors</span>
      </div>
      <div className="flex flex-1 flex-col justify-end gap-2 overflow-hidden p-4">
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {showTyping && <TypingBubble />}
      </div>
    </div>
  );
}

// The right panel: what "answering a customer" actually requires — never
// shown as a single instant reply, always shown as work with steps.
function StepIndicator({ status }: { status: StepStatus }) {
  return (
    <span
      className={cn(
        "relative z-10 mt-0.5 flex size-[18px] shrink-0 items-center justify-center rounded-full border bg-card transition-colors duration-300",
        status === "pending" && "border-border",
        status === "active" && "border-primary",
        status === "done" && "border-success bg-success/10",
      )}
    >
      {status === "done" && <Check className="size-3 text-success" aria-hidden="true" />}
      {status === "active" && (
        <span className="size-1.5 animate-pulse rounded-full bg-primary" aria-hidden="true" />
      )}
    </span>
  );
}

function IntelligencePanel({
  stepStatuses,
  payoffVisible,
}: {
  stepStatuses: Record<StepId, StepStatus>;
  payoffVisible: boolean;
}) {
  return (
    <div className="flex h-full min-h-[420px] flex-col rounded-2xl border border-white/10 bg-card p-6 shadow-[0_30px_80px_-25px_rgba(0,0,0,0.7)]">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        What HIRA is doing
      </p>
      <ol className="relative mt-6 flex-1 space-y-6">
        <span
          aria-hidden="true"
          className="absolute left-[9px] top-1 bottom-1 w-px bg-border"
        />
        {STEP_DEFS.map((step) => {
          const status = stepStatuses[step.id];
          return (
            <li key={step.id} className="relative flex items-start gap-3">
              <StepIndicator status={status} />
              <div className="flex items-center gap-2">
                <step.icon
                  className={cn(
                    "size-4 shrink-0 transition-colors duration-300",
                    status === "pending" ? "text-muted-foreground/30" : "text-muted-foreground",
                  )}
                  aria-hidden="true"
                />
                <p
                  className={cn(
                    "text-sm transition-colors duration-300",
                    status === "pending" && "text-muted-foreground/40",
                    status === "active" && "font-medium text-foreground",
                    status === "done" && "text-muted-foreground",
                  )}
                >
                  {step.label}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
      <div
        className={cn(
          "mt-6 border-t pt-4 text-sm font-medium text-foreground transition-opacity duration-700",
          payoffVisible ? "opacity-100" : "opacity-0",
        )}
      >
        You didn&apos;t have to lift a finger.
      </div>
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
  const [messages, setMessages] = useState<RenderedMessage[]>(() =>
    BEATS[0].message ? [BEATS[0].message] : [],
  );
  const [showTyping, setShowTyping] = useState(false);
  const [stepStatuses, setStepStatuses] = useState<Record<StepId, StepStatus>>({
    ...PENDING_STEPS,
    ...BEATS[0].steps,
  });
  const [payoffVisible, setPayoffVisible] = useState(false);
  const [paused, setPaused] = useState(false);
  const [tabHidden, setTabHidden] = useState(false);

  useEffect(() => {
    const onVisibility = () => setTabHidden(document.hidden);
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  useEffect(() => {
    if (paused || tabHidden || reducedMotion) {
      return;
    }
    const timer = setTimeout(() => {
      const nextIndex = beatIndex + 1;
      if (nextIndex >= BEATS.length) {
        setMessages(BEATS[0].message ? [BEATS[0].message] : []);
        setShowTyping(false);
        setStepStatuses({ ...PENDING_STEPS, ...BEATS[0].steps });
        setPayoffVisible(false);
        setBeatIndex(0);
        return;
      }
      const beat = BEATS[nextIndex];
      if (beat.message) {
        setMessages((prev) => [...prev, beat.message as RenderedMessage]);
      }
      setShowTyping(!!beat.typing);
      if (beat.steps) {
        setStepStatuses((prev) => ({ ...prev, ...beat.steps }));
      }
      setPayoffVisible(!!beat.payoff);
      setBeatIndex(nextIndex);
    }, BEATS[beatIndex].hold);
    return () => clearTimeout(timer);
  }, [beatIndex, paused, tabHidden, reducedMotion]);

  const summary =
    "Demo: a customer asks about SUVs on WhatsApp. On the right, watch HIRA search its business knowledge, explain financing, check calendar availability, book a test drive, and escalate to a sales specialist — six automated steps the business never had to do by hand.";

  if (reducedMotion) {
    return (
      <div
        role="img"
        aria-label={summary}
        className="grid gap-6 lg:grid-cols-2 lg:gap-8"
      >
        <div aria-hidden="true">
          <ConversationPanel messages={STATIC_MESSAGES} showTyping={false} />
        </div>
        <div aria-hidden="true">
          <IntelligencePanel stepStatuses={DONE_STEPS} payoffVisible />
        </div>
      </div>
    );
  }

  return (
    <div
      role="group"
      aria-label={`${summary} Animation pauses while hovered or focused.`}
      tabIndex={0}
      className="rounded-2xl outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div aria-hidden="true" className="grid gap-6 lg:grid-cols-2 lg:gap-8">
        <ConversationPanel messages={messages} showTyping={showTyping} />
        <IntelligencePanel stepStatuses={stepStatuses} payoffVisible={payoffVisible} />
      </div>
    </div>
  );
}

// Section-level wrapper: its own darkened stage, distinct from every flat
// section around it in either theme, so it reads as the one deliberate
// spotlit moment on the page rather than another card block.
export function SignatureDemo() {
  return (
    <section className="relative overflow-hidden bg-[#050506] py-20 sm:py-28">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_70%_60%_at_50%_20%,rgba(255,255,255,0.05),transparent_70%)]" />
      <div className="relative mx-auto max-w-5xl px-4 sm:px-6">
        <h2 className="text-center text-xs font-medium uppercase tracking-[0.2em] text-white/40">
          Here&apos;s HIRA, actually working
        </h2>
        <div className="mt-10">
          <DemoWidget />
        </div>
      </div>
    </section>
  );
}
