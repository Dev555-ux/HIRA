import { Button } from "@/components/ui/button";

/** Shared "N–M of total" + Previous/Next footer for offset-paginated list
 * cards (Leads, Customers). Renders nothing when everything already fits on
 * one page. */
export function PaginationFooter({
  total,
  offset,
  pageSize,
  onOffsetChange,
}: {
  total: number;
  offset: number;
  pageSize: number;
  onOffsetChange: (offset: number) => void;
}) {
  if (total <= pageSize) return null;

  return (
    <div className="flex items-center justify-between border-t px-4 py-3 text-xs text-muted-foreground">
      <span>
        {offset + 1}–{Math.min(offset + pageSize, total)} of {total}
      </span>
      <div className="flex gap-1">
        <Button
          variant="outline"
          size="sm"
          disabled={offset === 0}
          onClick={() => onOffsetChange(Math.max(0, offset - pageSize))}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={offset + pageSize >= total}
          onClick={() => onOffsetChange(offset + pageSize)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
