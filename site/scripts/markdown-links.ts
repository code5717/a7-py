import MarkdownIt from "markdown-it";

/** Rewrite inline link destinations without changing fenced, indented, or inline code. */
export function rewriteMarkdownLinks(
  source: string,
  destination: (href: string) => string,
) {
  const offsets = [0];
  for (let i = 0; i < source.length; i++)
    if (source[i] === "\n") offsets.push(i + 1);
  const protectedRanges: Array<[number, number]> = [];
  for (const token of new MarkdownIt({ html: false }).parse(source, {})) {
    if (!token.map) continue;
    const start = offsets[token.map[0]],
      end = offsets[token.map[1]] ?? source.length;
    if (token.type === "fence" || token.type === "code_block") {
      protectedRanges.push([start, end]);
    } else if (
      token.type === "inline" &&
      token.children?.some((child) => child.type === "code_inline")
    ) {
      const segment = source.slice(start, end);
      const runs = [...segment.matchAll(/`+/g)];
      for (let i = 0; i < runs.length; i++) {
        const open = runs[i];
        let slashes = 0;
        for (let at = open.index! - 1; at >= 0 && segment[at] === "\\"; at--)
          slashes++;
        if (slashes % 2) continue;
        const closeIndex = runs.findIndex(
          (run, j) => j > i && run[0].length === open[0].length,
        );
        if (closeIndex < 0) continue;
        const close = runs[closeIndex];
        protectedRanges.push([
          start + open.index!,
          start + close.index! + close[0].length,
        ]);
        i = closeIndex;
      }
    }
  }
  return source.replace(
    /\]\(([^)]+)\)/g,
    (match, href: string, offset: number) => {
      if (
        protectedRanges.some(([start, end]) => offset >= start && offset < end)
      )
        return match;
      return `](${destination(href)})`;
    },
  );
}
