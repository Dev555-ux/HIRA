"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Bot, BookOpen, Send, Sparkles, User } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useSendPlaygroundMessage } from "@/hooks/use-playground";
import { ApiError } from "@/lib/api";
import type { PlaygroundKbEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

const schema = z.object({
  message: z.string().trim().min(1, "Type a message to test"),
});

type FormValues = z.infer<typeof schema>;

interface Turn {
  role: "user" | "assistant";
  text: string;
}

export default function PlaygroundPage() {
  const [transcript, setTranscript] = useState<Turn[]>([]);
  const [retrieved, setRetrieved] = useState<PlaygroundKbEntry[] | null>(null);
  const sendMessage = useSendPlaygroundMessage();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    const userText = values.message.trim();
    try {
      const result = await sendMessage.mutateAsync(userText);
      setTranscript((prev) => [
        ...prev,
        { role: "user", text: userText },
        { role: "assistant", text: result.reply },
      ]);
      setRetrieved(result.retrieved);
      reset();
    } catch {
      // surfaced below via sendMessage.isError
    }
  });

  return (
    <>
      <PageHeader
        title="Playground"
        description="Test-drive your AI receptionist. Every message runs through the exact same pipeline a real WhatsApp customer would hit — knowledge base retrieval, then the LLM."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <User className="size-4" /> Customer message
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col gap-4">
            {transcript.length > 0 && (
              <div className="max-h-96 space-y-3 overflow-y-auto rounded-md border p-3">
                {transcript.map((turn, i) => (
                  <div
                    key={i}
                    className={cn(
                      "rounded-md px-3 py-2 text-sm",
                      turn.role === "user"
                        ? "ml-6 bg-secondary text-secondary-foreground"
                        : "mr-6 bg-muted",
                    )}
                  >
                    {turn.text}
                  </div>
                ))}
              </div>
            )}

            <form onSubmit={onSubmit} className="mt-auto space-y-2" noValidate>
              <Textarea
                placeholder="What are your opening hours?"
                disabled={sendMessage.isPending}
                {...register("message")}
              />
              {errors.message && (
                <p className="text-xs text-destructive">{errors.message.message}</p>
              )}
              {sendMessage.isError && (
                <p className="text-sm text-destructive">
                  {sendMessage.error instanceof ApiError
                    ? sendMessage.error.message
                    : "Something went wrong — please try again."}
                </p>
              )}
              <Button type="submit" disabled={sendMessage.isPending} className="w-full">
                {sendMessage.isPending ? (
                  "Thinking…"
                ) : (
                  <>
                    <Send /> Send
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Bot className="size-4" /> AI response
              </CardTitle>
            </CardHeader>
            <CardContent>
              {sendMessage.isPending && (
                <div className="space-y-2">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/4" />
                </div>
              )}
              {!sendMessage.isPending && transcript.length === 0 && (
                <EmptyState
                  icon={Sparkles}
                  title="No messages yet"
                  description="Send a customer message on the left to see how your AI receptionist responds."
                  className="border-0 py-8"
                />
              )}
              {!sendMessage.isPending && transcript.length > 0 && (
                <p className="whitespace-pre-wrap text-sm">
                  {transcript[transcript.length - 1].text}
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <BookOpen className="size-4" /> Retrieved Knowledge Base entries
              </CardTitle>
            </CardHeader>
            <CardContent>
              {sendMessage.isPending && (
                <div className="space-y-2">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-5/6" />
                </div>
              )}
              {!sendMessage.isPending && retrieved !== null && retrieved.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No matching knowledge base entries were found for the last message.
                </p>
              )}
              {!sendMessage.isPending && retrieved === null && (
                <p className="text-sm text-muted-foreground">
                  Retrieved entries will appear here after you send a message.
                </p>
              )}
              {!sendMessage.isPending && retrieved && retrieved.length > 0 && (
                <ul className="space-y-3">
                  {retrieved.map((entry) => (
                    <li key={entry.id} className="rounded-md border p-3 text-sm">
                      <p className="font-medium">{entry.title}</p>
                      <p className="mt-1 text-muted-foreground">{entry.content}</p>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
