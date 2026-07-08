"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { BookOpen, Globe, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
  useKbEntries,
  useUpdateKbEntry,
} from "@/hooks/use-knowledge-base";
import { ApiError } from "@/lib/api";
import type { KbEntry } from "@/lib/types";
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

export default function KnowledgeBasePage() {
  const [query, setQuery] = useState("");
  const [dialogTarget, setDialogTarget] = useState<DialogTarget>(null);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<KbEntry | null>(null);

  const { toast } = useToast();
  const { data: entries, isLoading } = useKbEntries();
  const createEntry = useCreateKbEntry();
  const updateEntry = useUpdateKbEntry();
  const deleteEntry = useDeleteKbEntry();
  const importWebsite = useImportWebsite();

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
    setDeleteTarget(null);
  }

  async function handleSubmit(values: FormValues) {
    if (dialogTarget === "new") {
      await createEntry.mutateAsync(values);
    } else if (dialogTarget) {
      await updateEntry.mutateAsync({ id: dialogTarget.id, payload: values });
    }
    setDialogTarget(null);
  }

  async function handleImportWebsite(values: WebsiteFormValues) {
    const result = await importWebsite.mutateAsync(values);
    setIsImportOpen(false);
    toast({
      title: "Imported successfully",
      description: `Pages imported: ${result.pages_imported}\nKnowledge entries created: ${result.entries_created}`,
      variant: "success",
    });
  }

  return (
    <>
      <PageHeader
        title="Knowledge Base"
        description="Facts your AI receptionist uses to answer customers."
        action={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setIsImportOpen(true)}>
              <Globe /> Import Website
            </Button>
            <Button size="sm" onClick={() => setDialogTarget("new")}>
              <Plus /> Add entry
            </Button>
          </div>
        }
      />

      <div className="relative mb-4 max-w-sm">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Search knowledge base…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="grid grid-cols-[1fr_1fr_100px_88px] gap-4 border-b px-5 py-3 text-xs font-medium text-muted-foreground">
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

          {!isLoading && filtered.length === 0 && (
            <EmptyState
              icon={BookOpen}
              title={entries?.length ? "No matches" : "No knowledge entries yet"}
              description={
                entries?.length
                  ? "Try a different search term."
                  : "Add FAQs and business facts here. Entries are chunked and embedded locally for semantic search."
              }
              action={
                !entries?.length ? (
                  <Button size="sm" onClick={() => setDialogTarget("new")}>
                    <Plus /> Add entry
                  </Button>
                ) : undefined
              }
              className="border-0"
            />
          )}

          {!isLoading &&
            filtered.map((entry) => (
              <div
                key={entry.id}
                className="grid grid-cols-[1fr_1fr_100px_88px] items-center gap-4 border-b px-5 py-3 text-sm last:border-0"
              >
                <span className="truncate font-medium">{entry.title}</span>
                <span className="truncate text-muted-foreground">{entry.content}</span>
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
        onOpenChange={(open) => !importWebsite.isPending && setIsImportOpen(open)}
      >
        {isImportOpen && (
          <ImportWebsiteForm
            onSubmit={handleImportWebsite}
            onCancel={() => setIsImportOpen(false)}
            isPending={importWebsite.isPending}
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
        <DialogTitle>{entry ? "Edit entry" : "Add entry"}</DialogTitle>
        <DialogDescription>
          {entry
            ? "Editing re-embeds this entry so search stays accurate."
            : "This fact is chunked and embedded automatically for semantic search."}
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
            {isPending ? "Saving…" : entry ? "Save changes" : "Add entry"}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
}

function ImportWebsiteForm({
  onSubmit,
  onCancel,
  isPending,
  error,
}: {
  onSubmit: (values: WebsiteFormValues) => Promise<void>;
  onCancel: () => void;
  isPending: boolean;
  error: unknown;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<WebsiteFormValues>({
    resolver: zodResolver(websiteSchema),
    defaultValues: { url: "" },
  });

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Import website</DialogTitle>
        <DialogDescription>
          We&apos;ll fetch the page, clean up the text, and add it to your knowledge base.
        </DialogDescription>
      </DialogHeader>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">Website URL</span>
          <Input
            placeholder="https://example.com"
            disabled={isPending}
            {...register("url")}
          />
          {errors.url && (
            <span className="block text-xs text-destructive">{errors.url.message}</span>
          )}
        </label>

        {isPending && <p className="text-sm text-muted-foreground">Importing website…</p>}

        {error != null && (
          <p className="text-sm text-destructive">
            {error instanceof ApiError
              ? error.message
              : "Something went wrong — please try again."}
          </p>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onCancel} disabled={isPending}>
            Cancel
          </Button>
          <Button type="submit" disabled={isPending}>
            {isPending ? "Importing website…" : "Import Website"}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
}
