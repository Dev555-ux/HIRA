"use client";

import Link from "next/link";
import { Bot, Copy, RotateCcw, Send, Sparkles, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { MarkdownLite } from "@/components/markdown-lite";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { useKbEntries } from "@/hooks/use-knowledge-base";
import { usePlaygroundHistory, useSendPlaygroundMessage } from "@/hooks/use-playground";
import { ApiError } from "@/lib/api";
import type { Message } from "@/lib/types";
import { cn, formatMessageTime } from "@/lib/utils";

// Requirement 6 (First-Time Experience) — clicking a prompt sends it
// immediately rather than just filling the composer, since the whole point
// of Demo Chat is zero friction.
const SUGGESTED_PROMPTS = [
  "What can you help me automate?",
  "Book a meeting tomorrow.",
  "Create a lead for Rahul.",
  "Explain my uploaded business knowledge.",
  "Show today's business overview.",
];

// Sprint 56 — Demo Mode's own conversation starters. Kept separate from
// SUGGESTED_PROMPTS above (which is for businesses that already have
// Business Knowledge and must stay exactly as it was) since these are
// deliberately capability-focused rather than data-dependent — nothing here
// assumes the business has taught HIRA anything yet.
const DEMO_MODE_STARTERS = [
  { emoji: "💬", label: "What can you do?" },
  { emoji: "📅", label: "Can you schedule meetings?" },
  { emoji: "👥", label: "Can you create CRM leads?" },
  { emoji: "🧠", label: "How do I learn about my business?" },
  { emoji: "📄", label: "Explain Business Knowledge" },
] as const;

interface PendingTurn {
  text: string;
  failed: boolean;
}

function TypingIndicator() {
  return (
    <div className="mr-10 flex items-center gap-2 self-start">
      <Avatar role="assistant" />
      <div className="flex items-center gap-1 rounded-2xl rounded-tl-sm bg-muted px-4 py-3">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60"
            style={{ animationDelay: `${i * 120}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

function Avatar({ role }: { role: "user" | "assistant" }) {
  return (
    <div
      className={cn(
        "flex size-7 shrink-0 items-center justify-center rounded-full",
        role === "assistant" ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground",
      )}
      aria-hidden="true"
    >
      {role === "assistant" ? <Bot className="size-3.5" /> : <User className="size-3.5" />}
    </div>
  );
}

function ChatBubble({
  message,
  onCopy,
}: {
  message: Message;
  onCopy: (text: string) => void;
}) {
  const isUser = message.direction === "inbound";
  const role = isUser ? "user" : "assistant";

  return (
    <div
      className={cn(
        "group flex animate-fade-in-up gap-2",
        isUser ? "flex-row-reverse self-end" : "self-start",
      )}
    >
      <Avatar role={role} />
      <div className={cn("flex max-w-[80%] flex-col gap-1 sm:max-w-[70%]", isUser && "items-end")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm",
            isUser
              ? "rounded-tr-sm bg-primary text-primary-foreground"
              : "rounded-tl-sm bg-muted",
          )}
        >
          <MarkdownLite text={message.body} />
        </div>
        <div className="flex items-center gap-2 px-1 text-xs text-muted-foreground">
          <span>{formatMessageTime(message.created_at)}</span>
          {!isUser && (
            <button
              type="button"
              onClick={() => onCopy(message.body)}
              className="opacity-0 transition-opacity hover:text-foreground focus-visible:opacity-100 group-hover:opacity-100"
              aria-label="Copy response"
            >
              <Copy className="size-3" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function DemoWelcome({ onStarterClick }: { onStarterClick: (prompt: string) => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 py-8 text-center">
      <Card className="max-w-md animate-fade-in-up text-left">
        <CardContent className="flex flex-col items-center gap-3 p-6 text-center">
          <div className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-2xl" aria-hidden="true">
            👋
          </div>
          <div>
            <h2 className="text-lg font-semibold">Welcome to HIRA</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              I&apos;m your AI Business Employee. I haven&apos;t learned about your business yet,
              but I&apos;d love to show you what I can do.
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Chat with me right now, or upload Business Knowledge whenever you&apos;re ready.
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap justify-center gap-2">
        {DEMO_MODE_STARTERS.map((starter) => (
          <button
            key={starter.label}
            type="button"
            onClick={() => onStarterClick(starter.label)}
            className="rounded-full border bg-background px-3 py-1.5 text-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span aria-hidden="true">{starter.emoji}</span> {starter.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function UpgradeCard() {
  return (
    <Card className="mt-6">
      <CardContent className="flex flex-col items-start justify-between gap-3 p-5 sm:flex-row sm:items-center">
        <div>
          <p className="text-sm font-medium">Ready for production?</p>
          <p className="text-sm text-muted-foreground">
            Connect WhatsApp Business so HIRA can start replying to real customers.
          </p>
        </div>
        <Button asChild variant="outline" className="shrink-0">
          <Link href="/settings?whatsapp=connect">Connect WhatsApp Business</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

export default function DemoChatPage() {
  const { data: history, isPending: historyLoading } = usePlaygroundHistory();
  // Sprint 56: Demo Mode is detected purely on the frontend by reusing the
  // existing Business Knowledge list (already fetched on the Knowledge Base
  // page) — no backend change, no new endpoint. "No Business Knowledge
  // uploaded yet" is exactly the condition app/ai/orchestrator.py's Demo
  // Mode (Sprint 55) branches on, so this mirrors that same fact rather than
  // guessing at it independently.
  const { data: kbEntries, isPending: kbLoading } = useKbEntries();
  const isDemoMode = !kbLoading && (kbEntries?.length ?? 0) === 0;
  const sendMessage = useSendPlaygroundMessage();
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<PendingTurn | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  const messages = history?.messages ?? [];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, pending, sendMessage.isPending]);

  async function submitMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sendMessage.isPending) return;
    setDraft("");
    setPending({ text: trimmed, failed: false });
    try {
      await sendMessage.mutateAsync(trimmed);
      setPending(null);
    } catch {
      setPending({ text: trimmed, failed: true });
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    void submitMessage(draft);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submitMessage(draft);
    }
  }

  function copyText(text: string) {
    void navigator.clipboard.writeText(text);
    toast({ title: "Copied to clipboard" });
  }

  const isEmpty = !historyLoading && messages.length === 0 && !pending;

  return (
    <>
      <PageHeader
        title="Demo Chat"
        description="Chat with HIRA right now — the exact same AI that answers your customers on WhatsApp, with no setup required."
        action={
          isDemoMode ? (
            <Badge
              variant="secondary"
              title="This business hasn't uploaded Business Knowledge yet."
            >
              🧪 Demo Mode
            </Badge>
          ) : undefined
        }
      />

      <Card className="flex h-[calc(100dvh-13rem)] min-h-[28rem] flex-col overflow-hidden">
        <CardContent className="flex flex-1 flex-col gap-4 overflow-y-auto p-4 sm:p-6">
          {historyLoading && (
            <div className="space-y-3">
              <Skeleton className="ml-auto h-12 w-1/2" />
              <Skeleton className="h-12 w-2/3" />
            </div>
          )}

          {/* Sprint 56: gated on !kbLoading so neither variant flashes
              before we actually know whether this business has Business
              Knowledge — isDemoMode is only ever meaningful once that
              resolves. Everything under the `false` branch below is the
              pre-Sprint-56 empty state, untouched (requirement 6: no
              behavioural or visual change for a business that already has
              Business Knowledge). */}
          {isEmpty && !kbLoading && (isDemoMode ? (
            <DemoWelcome onStarterClick={(prompt) => void submitMessage(prompt)} />
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center gap-6 py-8 text-center">
              <div className="flex size-12 items-center justify-center rounded-full bg-muted">
                <Sparkles className="size-6 text-muted-foreground" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Start chatting with HIRA</h2>
                <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                  Experience HIRA instantly. No WhatsApp setup required.
                </p>
              </div>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => void submitMessage(prompt)}
                    className="rounded-full border bg-background px-3 py-1.5 text-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ))}

          {!historyLoading &&
            messages.map((message) => (
              <ChatBubble key={message.id} message={message} onCopy={copyText} />
            ))}

          {pending && (
            <ChatBubble
              message={{
                id: "pending",
                direction: "inbound",
                body: pending.text,
                type: "text",
                media: [],
                status: "sent",
                created_at: new Date().toISOString(),
              }}
              onCopy={copyText}
            />
          )}

          {sendMessage.isPending && <TypingIndicator />}

          {pending?.failed && (
            <div className="mr-10 flex flex-wrap items-center gap-3 self-start rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <span>
                {sendMessage.error instanceof ApiError
                  ? sendMessage.error.message
                  : "Something went wrong sending that message."}
              </span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => void submitMessage(pending.text)}
              >
                <RotateCcw /> Retry
              </Button>
            </div>
          )}

          <div ref={bottomRef} />
        </CardContent>

        <form onSubmit={onSubmit} className="flex items-end gap-2 border-t p-3 sm:p-4">
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask HIRA anything — try booking a meeting or creating a lead…"
            disabled={sendMessage.isPending}
            rows={1}
            className="min-h-10 flex-1 resize-none"
            aria-label="Message HIRA"
          />
          <Button
            type="submit"
            size="icon"
            disabled={sendMessage.isPending || !draft.trim()}
            aria-label="Send message"
          >
            <Send />
          </Button>
        </form>
      </Card>

      <UpgradeCard />
    </>
  );
}
