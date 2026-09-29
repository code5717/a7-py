import MarkdownIt from "markdown-it";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import legacy from "../content/legacy-anchors.json";
import { diagrams } from "../content/diagrams";
import { icon } from "./icons";
import { rewriteMarkdownLinks } from "./markdown-links";

export const ROOT = path.resolve(import.meta.dir, "..");
export const BASE = "/a7-py";
export const ORIGIN = "https://code5717.github.io" + BASE;
export const SOURCE = "https://github.com/code5717/a7-py/blob/master/";
export const GROUPS = ["Getting started", "Reference", "Project", "Agents"];
export type Heading = { level: number; id: string; text: string };
export type Feature = {
  id: string;
  status: "supported" | "limited" | "unavailable" | "planned" | "unverified";
  qualification: string;
  topic: string;
  evidence: string[];
};
export type Doc = {
  slug: string;
  title: string;
  nav: string;
  group: string;
  summary: string;
  order: number;
  markdown: string;
  html: string;
  headings: Heading[];
  aliases: string[];
  sources: string[];
  features: Feature[];
  examples: string[];
};
export const escapeHtml = (s: string) =>
  s.replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );
export const slugify = (s: string) =>
  s
    .toLowerCase()
    .replace(/`([^`]+)`/g, "$1")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 72) || "section";
export const docHref = (slug: string) =>
  `${BASE}/${slug === "index" ? "" : slug + "/"}`;
export function markdownHref(href: string): string {
  if (!href.startsWith(BASE + "/") && !href.startsWith(ORIGIN + "/"))
    return href;
  const local = href.replace(ORIGIN, BASE);
  const [pathname, hash] = local.split("#");
  if (pathname.includes("/docs/") || /\.[a-z]+$/.test(pathname)) return href;
  const slug = pathname.slice(BASE.length).replace(/^\/|\/$/g, "") || "index";
  return `${BASE}/docs/${slug}.md${hash ? "#" + hash : ""}`;
}
export function renderMarkdown(markdown: string, slug = "index") {
  const md = new MarkdownIt({
    html: false,
    linkify: false,
    typographer: false,
  });
  const codeBlock = (source: string, language: string) => {
    const label =
      (
        {
          a7: "A7",
          bash: "Terminal",
          sh: "Terminal",
          json: "JSON",
          text: "Plain text",
          markdown: "Markdown",
        } as Record<string, string>
      )[language] || language;
    return `<div class="code-block"><div class="code-toolbar"><span class="code-language">${escapeHtml(label)}</span><button type="button" class="copy" aria-label="Copy ${escapeHtml(label)} code" hidden>${icon("copy")}<span data-copy-label>Copy</span></button></div><pre tabindex="0" aria-label="${escapeHtml(label)} code"><code class="language-${escapeHtml(language)}">${escapeHtml(source)}</code></pre><p class="copy-status" role="status" aria-live="polite" hidden></p></div>\n`;
  };
  md.renderer.rules.fence = (tokens, idx) =>
    codeBlock(
      tokens[idx].content,
      tokens[idx].info.trim().split(/\s+/)[0] || "text",
    );
  md.renderer.rules.code_block = (tokens, idx) =>
    codeBlock(tokens[idx].content, "text");
  const tokens = md.parse(markdown, {});
  const headings: Heading[] = [];
  const used = new Set<string>();
  let currentHeading = "";
  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i];
    if (token.type === "heading_open") {
      const text =
        tokens[i + 1].children?.map((t) => t.content).join("") ||
        tokens[i + 1].content;
      const base = slugify(text);
      let id = base,
        n = 0;
      while (used.has(id)) id = `${base}-${++n}`;
      used.add(id);
      token.attrSet("id", id);
      currentHeading = id;
      headings.push({ level: Number(token.tag.slice(1)), id, text });
    }
    const diagram = diagrams[slug]?.[currentHeading];
    if (token.type === "ordered_list_open" && token.level === 0 && diagram) {
      token.attrSet("class", diagram.layout);
      token.attrSet("aria-label", diagram.label);
    }
    for (const child of token.children ?? []) {
      if (child.type !== "link_open") continue;
      const href = String(child.attrGet("href") || "");
      // Markdown twins remain canonical in source; HTML gets equivalent page links.
      const url = new URL(href, `${ORIGIN}/docs/${slug}.md`);
      if (
        url.origin === new URL(ORIGIN).origin &&
        url.pathname.startsWith(BASE + "/docs/") &&
        url.pathname.endsWith(".md")
      ) {
        child.attrSet(
          "href",
          docHref(url.pathname.slice((BASE + "/docs/").length, -3)) + url.hash,
        );
      }
    }
  }
  let headingIndex = 0;
  md.renderer.rules.heading_close = (tokens, idx) => {
    const heading = headings[headingIndex++];
    const permalink =
      heading.level === 2 || heading.level === 3
        ? `<a class="heading-anchor" href="#${heading.id}" aria-label="Link to ${escapeHtml(heading.text)}">${icon("link")}</a>`
        : "";
    return `${permalink}</${tokens[idx].tag}>\n`;
  };
  const html = md.renderer
    .render(tokens, md.options, {})
    .replace(
      /<table>/g,
      '<div class="table-wrap" tabindex="0" role="region" aria-label="Scrollable table"><table>',
    )
    .replace(/<\/table>/g, "</table></div>");
  return { html, headings };
}
export function parseFrontmatter(raw: string) {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n/.exec(raw);
  const data: Record<string, string> = {};
  if (match)
    for (const line of match[1].split("\n")) {
      const i = line.indexOf(":");
      if (i >= 0)
        data[line.slice(0, i).trim()] = line
          .slice(i + 1)
          .trim()
          .replace(/^["']|["']$/g, "");
    }
  return { data, body: raw.slice(match?.[0].length ?? 0).trim() };
}
async function discover(dir: string, prefix = ""): Promise<string[]> {
  const files: string[] = [];
  for (const e of await readdir(dir, { withFileTypes: true })) {
    if (e.isDirectory())
      files.push(
        ...(await discover(path.join(dir, e.name), prefix + e.name + "/")),
      );
    else if (e.name.endsWith(".md")) files.push(prefix + e.name);
  }
  return files.sort();
}
export async function readRegistry(): Promise<Doc[]> {
  let features: Feature[] = [];
  try {
    features = JSON.parse(
      await readFile(path.join(ROOT, "content/features.json"), "utf8"),
    );
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== "ENOENT") throw e;
  }
  const docs: Doc[] = [];
  for (const file of await discover(path.join(ROOT, "public/docs"))) {
    const slug = file.slice(0, -3);
    const { data, body } = parseFrontmatter(
      await readFile(path.join(ROOT, "public/docs", file), "utf8"),
    );
    const rendered = renderMarkdown(body, slug);
    if (rendered.headings.filter((h) => h.level === 1).length !== 1)
      throw new Error(`${slug}: expected exactly one H1`);
    const aliases = ((legacy as Record<string, string[]>)[slug] ?? []).filter(
      (id) => !rendered.headings.some((h) => h.id === id),
    );
    docs.push({
      slug,
      title: data.title || rendered.headings[0].text,
      nav: data.nav || data.title || rendered.headings[0].text,
      group: data.group || "Reference",
      summary: data.summary || "",
      order: Number(data.order ?? 50),
      markdown: body,
      ...rendered,
      aliases,
      sources: [
        SOURCE + "site/public/docs/" + file,
        ...new Set(
          Array.from(
            body.matchAll(
              /https:\/\/github\.com\/code5717\/a7-py\/(?:blob|tree)\/[^\s)]+/g,
            ),
            (m) => m[0],
          ),
        ),
      ],
      features: features.filter((f) => f.topic === slug),
      examples: [
        ...new Set(
          Array.from(body.matchAll(/examples\/([\w/.-]+\.a7)/g), (m) => m[1]),
        ),
      ],
    });
  }
  const ordered = docs.sort(
    (a, b) => a.order - b.order || a.slug.localeCompare(b.slug),
  );
  for (const f of features)
    if (!ordered.some((d) => d.slug === f.topic))
      throw new Error(`Unknown feature topic ${f.topic}`);
  return ordered;
}
export function exportsFor(docs: Doc[]) {
  const index = [
    "# A7 documentation",
    "",
    "Experimental A7 compiler and language reference. Start with the relevant pages below. Retrieve the full corpus only when needed.",
    "",
  ];
  for (const group of GROUPS) {
    index.push(`## ${group}`, "");
    for (const d of docs.filter((d) => d.group === group))
      index.push(`- [${d.title}](${ORIGIN}/docs/${d.slug}.md): ${d.summary}`);
    index.push("");
  }
  index.push(
    `## Optional`,
    "",
    `- [Full corpus](${ORIGIN}/llms-full.txt)`,
    `- [Structured manifest](${ORIGIN}/docs/manifest.json)`,
    "",
  );
  const markdown = (source: string, slug: string) =>
    rewriteMarkdownLinks(source, (href) => {
      const converted = markdownHref(href);
      const url = new URL(converted, `${ORIGIN}/docs/${slug}.md`);
      return url.origin === new URL(ORIGIN).origin
        ? url.pathname + url.hash
        : converted;
    });
  const full = [
    "# A7 full documentation",
    "",
    ...docs.flatMap((d) => [
      `Source: ${ORIGIN}/docs/${d.slug}.md`,
      "",
      markdown(d.markdown, d.slug),
      "",
      "---",
      "",
    ]),
  ].join("\n");
  const revision = createHash("sha256")
    .update(JSON.stringify(docs.map(({ html, ...source }) => source)))
    .digest("hex");
  const manifest = {
    schemaVersion: 1,
    sourceRevision: { kind: "documentation-sha256", value: revision },
    qualification:
      "Documentation content digest, not a compiler verification result. Evidence links identify the source authority.",
    pages: docs.map((d) => ({
      id: d.slug,
      title: d.title,
      summary: d.summary,
      group: d.group,
      url: ORIGIN + docHref(d.slug).slice(BASE.length),
      markdown: ORIGIN + "/docs/" + d.slug + ".md",
      sections: d.headings,
      aliases: d.aliases,
      sources: d.sources,
      examples: d.examples,
    })),
    features: docs.flatMap((d) =>
      d.features.map((f) => ({
        ...f,
        documentationUrl: ORIGIN + docHref(d.slug).slice(BASE.length),
        markdownUrl: ORIGIN + "/docs/" + d.slug + ".md",
      })),
    ),
  };
  return {
    "llms.txt": index.join("\n"),
    "llms-full.txt": full,
    "docs/manifest.json": JSON.stringify(manifest, null, 2) + "\n",
    "sitemap.xml": `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${docs.map((d) => `  <url><loc>${ORIGIN + docHref(d.slug).slice(BASE.length)}</loc></url>`).join("\n")}\n</urlset>\n`,
  };
}
