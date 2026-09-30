import { mkdir, rm, cp, writeFile } from "node:fs/promises";
import path from "node:path";
import { icon } from "./icons";
import { searchEntries } from "./search";
import {
  BASE,
  ORIGIN,
  ROOT,
  GROUPS,
  readRegistry,
  exportsFor,
  escapeHtml as e,
  docHref,
  type Doc,
} from "./content";

const docs = await readRegistry();
const DIST = path.join(ROOT, "dist");
function navigation(active: string) {
  return GROUPS.map(
    (group) =>
      `<section class="nav-group"><h2>${e(group)}</h2>${docs
        .filter((d) => d.group === group)
        .map(
          (d) =>
            `<a href="${docHref(d.slug)}"${d.slug === active ? ' aria-current="page"' : ""}>${e(d.nav)}</a>`,
        )
        .join("")}</section>`,
  ).join("");
}
function page(doc: Doc) {
  const outline = doc.headings
    .filter((h) => h.level === 2)
    .map((h) => `<a href="#${h.id}">${e(h.text)}</a>`)
    .join("");
  const i = docs.indexOf(doc);
  const neighbor = (d: Doc | undefined, label: string) =>
    d
      ? `<a class="pager-link" href="${docHref(d.slug)}"><small>${label === "Previous" ? icon("left") : ""}${label}${label === "Next" ? icon("right") : ""}</small><span>${e(d.nav)}</span></a>`
      : "<span></span>";
  let articleHtml = doc.html;
  for (const id of doc.aliases) {
    const target =
      id === "exit-codes" ? "diagnostics-and-exit-codes" : doc.headings[0].id;
    articleHtml = articleHtml.replace(
      new RegExp(`(<h[1-6] id="${target}")`),
      `<span id="${e(id)}" class="legacy-anchor" aria-hidden="true"></span>$1`,
    );
  }
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${e(doc.title)}${doc.slug === "index" ? "" : " · A7"}</title><meta name="description" content="${e(doc.summary)}">
<meta name="color-scheme" content="light dark"><meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#171819" media="(prefers-color-scheme: dark)">
<meta property="og:title" content="${e(doc.title)}"><meta property="og:description" content="${e(doc.summary)}"><meta property="og:type" content="website"><meta property="og:url" content="${ORIGIN + docHref(doc.slug).slice(BASE.length)}"><meta name="twitter:card" content="summary">
<link rel="canonical" href="${ORIGIN + docHref(doc.slug).slice(BASE.length)}"><link rel="alternate" type="text/markdown" href="${BASE}/docs/${doc.slug}.md" title="Markdown"><link rel="icon" href="${BASE}/favicon.svg">
<link rel="preload" href="${BASE}/fonts/inter-latin-opsz-normal.woff2" as="font" type="font/woff2" crossorigin>
<script>try{var t=localStorage.getItem('a7-theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch{}</script>
<link rel="stylesheet" href="${BASE}/assets/site.css"></head><body data-slug="${e(doc.slug)}">
<a class="skip" href="#main">Skip to content</a>
<header class="topbar"><a class="brand" href="${BASE}/">A7 <span>Documentation</span><span class="brand-tag">Experimental</span></a><div class="tools"><button type="button" data-search-open hidden>${icon("search")}<span>Search</span><kbd>Ctrl K</kbd></button><label class="theme-control" hidden>Theme <select aria-label="Color theme"><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label><a href="https://github.com/code5717/a7-py">GitHub</a></div></header>
<div class="shell"><aside class="sidebar"><details class="navigation" open><summary><span>Documentation navigation</span><span class="navigation-current">${e(doc.nav)}</span></summary><nav aria-label="Documentation">${navigation(doc.slug)}</nav></details></aside>
<main id="main" tabindex="-1"><article><header class="article-meta"><span>${e(doc.group)}</span><a href="${BASE}/docs/${doc.slug}.md">Read Markdown</a></header>

<details class="mobile-outline"><summary>On this page</summary><nav aria-label="Page outline">${outline}</nav></details>
<div class="prose">${articleHtml}</div>
<nav class="pager" aria-label="Previous and next pages">${neighbor(docs[i - 1], "Previous")}${neighbor(docs[i + 1], "Next")}</nav>
<footer><a href="${BASE}/docs/${doc.slug}.md">Markdown</a><a href="${BASE}/llms.txt">Agent index</a><a href="${BASE}/docs/manifest.json">Manifest</a><a href="${doc.sources[0]}">Page source</a><a href="https://github.com/code5717/a7-py">GitHub</a></footer></article></main>
<aside class="page-outline"><nav aria-label="On this page"><h2>On this page</h2>${outline}</nav></aside></div>
<dialog id="search" aria-labelledby="search-title"><div class="search-top"><h2 id="search-title">Search documentation</h2><button data-search-close type="button">Close</button></div><label for="search-input">Words, features, or identifiers</label><input id="search-input" type="search" autocomplete="off" spellcheck="false" placeholder="Types, generics, exit codes…" aria-controls="search-results"><p id="search-status" role="status" aria-live="polite"></p><ul id="search-results" aria-label="Search results"></ul><p class="search-help"><span><kbd>↑</kbd> <kbd>↓</kbd> Navigate</span><span><kbd>Enter</kbd> Open</span><span><kbd>Esc</kbd> Close</span></p></dialog>
<script src="${BASE}/assets/site.js" defer></script></body></html>`;
}
await rm(DIST, { recursive: true, force: true });
await cp(path.join(ROOT, "public"), DIST, { recursive: true });
await mkdir(path.join(DIST, "assets"), { recursive: true });
await cp(path.join(ROOT, "src/site.js"), path.join(DIST, "assets/site.js"));
await mkdir(path.join(DIST, "fonts"), { recursive: true });
for (const [pkg, file, target] of [
  [
    "@fontsource-variable/inter",
    "files/inter-latin-opsz-normal.woff2",
    "inter-latin-opsz-normal.woff2",
  ],
  [
    "@fontsource/jetbrains-mono",
    "files/jetbrains-mono-latin-400-normal.woff2",
    "jetbrains-mono-latin-400-normal.woff2",
  ],
  ["@fontsource-variable/inter", "LICENSE", "Inter-LICENSE.txt"],
  ["@fontsource/jetbrains-mono", "LICENSE", "JetBrainsMono-LICENSE.txt"],
])
  await cp(
    path.join(ROOT, "node_modules", pkg, file),
    path.join(DIST, "fonts", target),
  );
for (const doc of docs) {
  const dir = doc.slug === "index" ? DIST : path.join(DIST, doc.slug);
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, "index.html"), page(doc));
}
for (const [file, value] of Object.entries(exportsFor(docs)))
  await writeFile(path.join(DIST, file), value);
const search = searchEntries(docs);
await writeFile(path.join(DIST, "assets/search.json"), JSON.stringify(search));
console.log(`built ${docs.length} pages with Markdown, search, and manifest`);
