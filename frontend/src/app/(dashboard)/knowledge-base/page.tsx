"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import {
  AlertTriangle,
  Check,
  Clock,
  Globe,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  useCreateKbEntry,
  useDeleteKbEntry,
  useImportWebsite,
  useKbDrafts,
  useKbEntries,
  usePublishKbEntry,
  useRejectKbEntry,
  useUpdateKbEntry,
} from "@/hooks/use-knowledge-base";
import { ApiError } from "@/lib/api";
import type { ImportWebsiteResult, KbDraftBatch, KbEntry } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";

const schema = z.object({
  title: z.string().trim().min(1, "Title is required"),
  content: z.string().trim().min(1, "Content is required"),
});

type FormValues = z.infer<typeof schema>;

const websiteSchema = z.object({
  url: z.string().trim().min(1, "URL is required").url("Enter a valid URL"),
});

type WebsiteFormValues = z.infer<typeof websiteSchema>;

// The dialog target: "new" for the create form, an entry for editing, or null (closed).
type DialogTarget = KbEntry | "new" | null;

function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

export default function KnowledgeBasePage() {
  const [query, setQuery] = useState("");
  const [dialogTarget, setDialogTarget] = useState<DialogTarget>(null);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<KbEntry | null>(null);

  const { toast } = useToast();
  const { data: entries, isLoading, isError, error, refetch } = useKbEntries();
  const { data: draftBatches } = useKbDrafts();
  const createEntry = useCreateKbEntry();
  const updateEntry = useUpdateKbEntry();
  const deleteEntry = useDeleteKbEntry();
  const importWebsite = useImportWebsite();
  const publishEntry = usePublishKbEntry();
  const rejectEntry = useRejectKbEntry();

  const filtered = useMemo(() => {
    if (!entries) return [];
    const q = query.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter(
      (e) => e.title.toLowerCase().includes(q) || e.content.toLowerCase().includes(q),
    );
  }, [entries, query]);

  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    await deleteEntry.mutateAsync(deleteTarget.id);
    toast({ title: "Removed — HIRA won't reference this anymore." });
    setDeleteTarget(null);
  }

  async function handleSubmit(values: FormValues) {
    if (dialogTarget === "new") {
      await createEntry.mutateAsync(values);
      toast({ title: "HIRA learned this fact.", variant: "success" });
    } else if (dialogTarget) {
      await updateEntry.mutateAsync({ id: dialogTarget.id, payload: values });
      toast({ title: "Updated — HIRA will use this right away.", variant: "success" });
    }
    setDialogTarget(null);
  }

  function closeImportDialog() {
    importWebsite.reset();
    setIsImportOpen(false);
  }

  return (
    <>
      <PageHeader
        title="Business Knowledge"
        description="Everything HIRA has learned about your business so far."
        action={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setIsImportOpen(true)}>
              <Globe /> Import Website
            </Button>
            <Button size="sm" onClick={() => setDialogTarget("new")}>
              <Plus /> Add a fact
            </Button>
          </div>
        }
      />

      {draftBatches && draftBatches.length > 0 && (
        <div className="mb-6 space-y-4">
          {draftBatches.map((batch) => (
            <DraftBatchCard
              key={batch.import_batch_id}
              batch={batch}
              onApprove={(id) => publishEntry.mutate(id)}
              onReject={(id) => rejectEntry.mutate(id)}
              onApproveAll={() => {
                for (const entry of batch.entries) publishEntry.mutate(entry.id);
                toast({ title: "Published — HIRA will start using this right away." });
              }}
              isPending={publishEntry.isPending || rejectEntry.isPending}
            />
          ))}
        </div>
      )}

      <div className="relative mb-4 max-w-sm">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Search what HIRA knows…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="hidden gap-4 border-b px-5 py-3 text-xs font-medium text-muted-foreground sm:grid sm:grid-cols-[1fr_1fr_100px_88px]">
            <span>Title</span>
            <span>Content</span>
            <span>Updated</span>
            <span />
          </div>

          {isLoading && (
            <div className="space-y-3 p-5">
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-full" />
            </div>
          )}

          {isError && (
            <EmptyState
              icon={AlertTriangle}
              title="Couldn't load your business knowledge"
              description={error instanceof Error ? error.message : "Something went wrong."}
              action={
                <Button size="sm" onClick={() => refetch()}>
                  Retry
                </Button>
              }
              className="border-0"
            />
          )}

          {!isLoading && !isError && filtered.length === 0 && (
            <EmptyState
              icon={Sparkles}
              title={entries?.length ? "No matches" : "HIRA doesn't know this yet"}
              description={
                entries?.length
                  ? `Nothing matches "${query}" — try a different word.`
                  : "Add a fact, or import your website, and HIRA will start using it to answer customers immediately."
              }
              action={
                !entries?.length ? (
                  <Button size="sm" onClick={() => setDialogTarget("new")}>
                    <Plus /> Add a fact
                  </Button>
                ) : undefined
              }
              className="border-0"
            />
          )}

          {!isLoading &&
            !isError &&
            filtered.map((entry) => (
              <div
                key={entry.id}
                className="border-b px-5 py-3 text-sm transition-colors last:border-0 hover:bg-accent/50 sm:grid sm:grid-cols-[1fr_1fr_100px_88px] sm:items-center sm:gap-4"
              >
                <span className="block truncate font-medium">{entry.title}</span>
                <span className="mt-0.5 line-clamp-2 text-muted-foreground sm:mt-0 sm:truncate sm:line-clamp-none">
                  {entry.content}
                </span>
                <div className="mt-2 flex items-center justify-between sm:mt-0 sm:contents">
                  <span className="text-xs text-muted-foreground">
                    {formatRelativeTime(entry.updated_at)}
                  </span>
                  <div className="flex justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Edit entry"
                      onClick={() => setDialogTarget(entry)}
                    >
                      <Pencil />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Delete entry"
                      className="text-destructive hover:text-destructive"
                      onClick={() => setDeleteTarget(entry)}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
        </CardContent>
      </Card>

      <Dialog
        open={dialogTarget !== null}
        onOpenChange={(open) => !open && setDialogTarget(null)}
      >
        {dialogTarget !== null && (
          <KbEntryForm
            entry={dialogTarget === "new" ? null : dialogTarget}
            onSubmit={handleSubmit}
            isPending={createEntry.isPending || updateEntry.isPending}
            error={createEntry.error ?? updateEntry.error}
          />
        )}
      </Dialog>

      <Dialog
        open={isImportOpen}
        onOpenChange={(open) => {
          if (open) {
            setIsImportOpen(true);
          } else if (!importWebsite.isPending) {
            closeImportDialog();
          }
        }}
      >
        {isImportOpen && (
          <ImportWebsiteDialog
            onSubmit={(values) => importWebsite.mutate(values)}
            onCancel={closeImportDialog}
            onDone={closeImportDialog}
            isPending={importWebsite.isPending}
            isSuccess={importWebsite.isSuccess}
            result={importWebsite.data}
            submittedUrl={importWebsite.variables?.url}
            error={importWebsite.error}
          />
        )}
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title={deleteTarget ? `Delete "${deleteTarget.title}"?` : ""}
        description="This can't be undone."
        confirmLabel="Delete"
        onConfirm={handleConfirmDelete}
        isPending={deleteEntry.isPending}
      />
    </>
  );
}

// One website import's worth of drafts, held for review before HIRA can use
// any of it (DEC-039) — approving/rejecting is per-entry, with "Approve all"
// as a shortcut for the common case of the whole page being accurate.
function DraftBatchCard({
  batch,
  onApprove,
  onReject,
  onApproveAll,
  isPending,
}: {
  batch: KbDraftBatch;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onApproveAll: () => void;
  isPending: boolean;
}) {
  const factWord = batch.entries.length === 1 ? "fact" : "facts";
  return (
    <Card className="border-warning/40 bg-warning/5">
      <CardHeader className="flex-row items-center justify-between gap-4 space-y-0">
        <div className="flex items-center gap-2">
          <Clock className="size-4 text-warning" />
          <CardTitle className="text-sm">
            {batch.entries.length} {factWord} imported from {batch.entries[0]?.title} — pending
            your review
          </CardTitle>
        </div>
        <Button size="sm" onClick={onApproveAll} disabled={isPending}>
          <Check /> Approve all
        </Button>
      </CardHeader>
      <CardContent className="space-y-2 pt-0">
        {batch.entries.map((entry) => (
          <div
            key={entry.id}
            className="flex items-start justify-between gap-4 rounded-lg border bg-background p-3"
          >
            <p className="text-sm text-muted-foreground">{entry.content}</p>
            <div className="flex shrink-0 gap-1">
              <Button
                variant="ghost"
                size="icon"
                aria-label="Approve fact"
                onClick={() => onApprove(entry.id)}
                disabled={isPending}
              >
                <Check className="text-success" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Reject fact"
                className="text-destructive hover:text-destructive"
                onClick={() => onReject(entry.id)}
                disabled={isPending}
              >
                <X />
              </Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function KbEntryForm({
  entry,
  onSubmit,
  isPending,
  error,
}: {
  entry: KbEntry | null;
  onSubmit: (values: FormValues) => Promise<void>;
  isPending: boolean;
  error: unknown;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { title: entry?.title ?? "", content: entry?.content ?? "" },
  });

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>{entry ? "Edit fact" : "Teach HIRA a fact"}</DialogTitle>
        <DialogDescription>
          {entry
            ? "HIRA relearns this fact right away, so future answers stay accurate."
            : "HIRA turns this into something it can find instantly the next time a customer asks something related."}
        </DialogDescription>
      </DialogHeader>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Title</span>
          <Input placeholder="Office hours" {...register("title")} />
          {errors.title && (
            <span className="block text-xs text-destructive">{errors.title.message}</span>
          )}
        </label>

        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Content</span>
          <Textarea
            placeholder="We are open Monday to Friday, 9am to 6pm."
            {...register("content")}
          />
          {errors.content && (
            <span className="block text-xs text-destructive">{errors.content.message}</span>
          )}
        </label>

        {error != null && (
          <p className="text-sm text-destructive">
            {error instanceof ApiError
              ? error.message
              : "Something went wrong — please try again."}
          </p>
        )}

        <DialogFooter>
          <Button type="submit" disabled={isPending}>
            {isPending ? "Saving…" : entry ? "Save changes" : "Teach HIRA"}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
}

// What HIRA is actually doing, in order — reading the page (the real HTTP
// fetch), extracting the readable text from it, organizing it into chunks
// (the real chunking step), then embedding those chunks so replies can use
// them (the real indexing step). All four are genuinely part of the one
// backend request; there's no server-sent progress signal to confirm timing
// precisely, so this advances on a timer and simply holds on the last line
// until the real response arrives — it never claims done before HIRA is.
const IMPORT_STAGES = [
  "Reading your website…",
  "Extracting useful information…",
  "Organizing business knowledge…",
  "Preparing AI responses…",
];

function useImportStageCaption(active: boolean): string {
  const [stageIndex, setStageIndex] = useState(0);

  useEffect(() => {
    if (!active) {
      setStageIndex(0);
      return;
    }
    const interval = setInterval(() => {
      setStageIndex((i) => Math.min(i + 1, IMPORT_STAGES.length - 1));
    }, 1300);
    return () => clearInterval(interval);
  }, [active]);

  return IMPORT_STAGES[stageIndex];
}

function ImportWebsiteDialog({
  onSubmit,
  onCancel,
  onDone,
  isPending,
  isSuccess,
  result,
  submittedUrl,
  error,
}: {
  onSubmit: (values: WebsiteFormValues) => void;
  onCancel: () => void;
  onDone: () => void;
  isPending: boolean;
  isSuccess: boolean;
  result: ImportWebsiteResult | undefined;
  submittedUrl: string | undefined;
  error: unknown;
}) {
  const caption = useImportStageCaption(isPending);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<WebsiteFormValues>({
    resolver: zodResolver(websiteSchema),
    defaultValues: { url: "" },
  });

  if (isSuccess && result) {
    const factWord = result.entries_created === 1 ? "fact" : "facts";
    const preview = result.entries.slice(0, 5);
    return (
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Pending your review</DialogTitle>
          <DialogDescription>
            Found {result.entries_created} new {factWord}
            {submittedUrl ? ` from ${hostnameOf(submittedUrl)}` : ""} — HIRA won&apos;t use any of
            it until you approve it below.
          </DialogDescription>
        </DialogHeader>
        {preview.length > 0 && (
          <ul className="space-y-2.5 rounded-lg border p-4">
            {preview.map((entry) => (
              <li key={entry.id} className="flex items-start gap-2 text-sm">
                <Clock className="mt-0.5 size-4 shrink-0 text-warning" />
                <span className="line-clamp-2 text-muted-foreground">{entry.content}</span>
              </li>
            ))}
          </ul>
        )}
        {result.entries.length > preview.length && (
          <p className="mt-2 text-xs text-muted-foreground">
            +{result.entries.length - preview.length} more
          </p>
        )}
        <DialogFooter>
          <Button onClick={onDone}>Done</Button>
        </DialogFooter>
      </DialogContent>
    );
  }

  if (isPending) {
    return (
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Teaching HIRA about your business</DialogTitle>
          <DialogDescription>This usually takes a few seconds.</DialogDescription>
        </DialogHeader>
        <div className="flex items-center gap-3 rounded-lg border p-4">
          <RefreshCw className="size-5 shrink-0 animate-spin text-muted-foreground" />
          <p key={caption} className="animate-fade-in text-sm text-muted-foreground">
            {caption}
          </p>
        </div>
      </DialogContent>
    );
  }

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Teach HIRA from your website</DialogTitle>
        <DialogDescription>
          HIRA will read the page, pull out the useful parts, and remember them the way it
          remembers everything else you&apos;ve taught it.
        </DialogDescription>
      </DialogHeader>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Website URL</span>
          <Input placeholder="https://example.com" {...register("url")} />
          {errors.url && (
            <span className="block text-xs text-destructive">{errors.url.message}</span>
          )}
        </label>

        {error != null && (
          <p className="text-sm text-destructive">
            {error instanceof ApiError
              ? error.message
              : "Something went wrong — please try again."}
          </p>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit">
            <Globe /> Teach HIRA
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
}
