// A small, dependency-free markdown renderer for AI chat replies. Renders
// straight to JSX (never dangerouslySetInnerHTML — this codebase has no XSS
// vector via raw HTML anywhere, and this shouldn't be the first). Supports
// just enough markdown for a receptionist's replies: bold/italic/code,
// bullet + numbered lists, and paragraph breaks — not a full CommonMark
// implementation.
import { Fragment } from "react";

function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  const parts = text.split(pattern).filter((part) => part !== "");

  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 3) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 1) {
      return (
        <code key={key} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 1) {
      return <em key={key}>{part.slice(1, -1)}</em>;
    }
    return <Fragment key={key}>{part}</Fragment>;
  });
}

interface Block {
  type: "ul" | "ol" | "p";
  lines: string[];
}

function toBlocks(body: string): Block[] {
  const lines = body.split("\n");
  const blocks: Block[] = [];

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    const bullet = /^\s*[-*]\s+(.*)/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)/.exec(line);

    if (bullet) {
      const last = blocks[blocks.length - 1];
      if (last?.type === "ul") last.lines.push(bullet[1]);
      else blocks.push({ type: "ul", lines: [bullet[1]] });
    } else if (numbered) {
      const last = blocks[blocks.length - 1];
      if (last?.type === "ol") last.lines.push(numbered[1]);
      else blocks.push({ type: "ol", lines: [numbered[1]] });
    } else if (line.trim() === "") {
      blocks.push({ type: "p", lines: [""] });
    } else {
      const last = blocks[blocks.length - 1];
      if (last?.type === "p" && last.lines[last.lines.length - 1] !== "") {
        last.lines.push(line);
      } else {
        blocks.push({ type: "p", lines: [line] });
      }
    }
  }

  return blocks.filter((b) => !(b.type === "p" && b.lines.every((l) => l === "")));
}

export function MarkdownLite({ text }: { text: string }) {
  const blocks = toBlocks(text);

  return (
    <div className="space-y-2">
      {blocks.map((block, bi) => {
        if (block.type === "ul") {
          return (
            <ul key={bi} className="list-disc space-y-1 pl-5">
              {block.lines.map((line, li) => (
                <li key={li}>{renderInline(line, `${bi}-${li}`)}</li>
              ))}
            </ul>
          );
        }
        if (block.type === "ol") {
          return (
            <ol key={bi} className="list-decimal space-y-1 pl-5">
              {block.lines.map((line, li) => (
                <li key={li}>{renderInline(line, `${bi}-${li}`)}</li>
              ))}
            </ol>
          );
        }
        return (
          <p key={bi} className="whitespace-pre-wrap">
            {block.lines.map((line, li) => (
              <Fragment key={li}>
                {li > 0 && <br />}
                {renderInline(line, `${bi}-${li}`)}
              </Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}
