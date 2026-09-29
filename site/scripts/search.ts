import MarkdownIt from "markdown-it";
import { docHref, type Doc } from "./content";

// Read text from Markdown tokens so code fences cannot create false sections
// and source-link destinations never leak into the result excerpts.
export function searchEntries(docs: Doc[]) {
  const parser = new MarkdownIt({ html: false });
  return docs.flatMap((doc) => {
    let section = -1;
    const text = doc.headings.map(() => [] as string[]);
    for (const token of parser.parse(doc.markdown, {})) {
      if (token.type === "heading_open") section++;
      if (section < 0) continue;
      if (token.type === "inline") {
        text[section].push(
          (token.children ?? [])
            .map((child) => {
              if (["text", "code_inline", "image"].includes(child.type))
                return child.content;
              if (["softbreak", "hardbreak"].includes(child.type)) return " ";
              return "";
            })
            .join(""),
        );
      } else if (["fence", "code_block"].includes(token.type)) {
        text[section].push(token.content);
      }
    }
    return doc.headings.map((heading, i) => ({
      level: heading.level,
      title: doc.title,
      section: heading.text,
      href: docHref(doc.slug) + "#" + heading.id,
      text: text[i].join(" ").replace(/\s+/g, " ").trim(),
      features: doc.features.map((feature) => feature.id).join(" "),
    }));
  });
}
