import { readFile, readdir, stat } from "node:fs/promises";
import path from "node:path";
import { ROOT, BASE, ORIGIN } from "./content";
const dist = path.join(ROOT, "dist");
let errors = 0,
  checked = 0;
const fail = (message: string) => {
  console.error(message);
  errors++;
};
async function files(dir: string): Promise<string[]> {
  const out: string[] = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await files(p)));
    else out.push(p);
  }
  return out;
}
const htmlFiles = (await files(dist)).filter((p) => p.endsWith(".html"));
for (const file of htmlFiles) {
  const html = await readFile(file, "utf8");
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]);
  if (new Set(ids).size !== ids.length) fail(`Duplicate IDs in ${file}`);
  if ((html.match(/<h1\b/g) || []).length !== 1)
    fail(`Expected one H1: ${file}`);
  const baseUrl = ORIGIN + "/" + path.relative(dist, file);
  for (const match of html.matchAll(/\b(?:href|src)="([^"]+)"/g)) {
    const url = new URL(match[1].replace(/&amp;/g, "&"), baseUrl);
    if (url.origin !== new URL(ORIGIN).origin) continue;
    if (!url.pathname.startsWith(BASE + "/")) {
      fail(`Escapes deployment base: ${url.href}`);
      continue;
    }
    let target = path.join(
      dist,
      decodeURIComponent(url.pathname.slice(BASE.length)),
    );
    try {
      if ((await stat(target)).isDirectory())
        target = path.join(target, "index.html");
      await stat(target);
    } catch {
      fail(`Missing ${url.pathname} linked by ${path.relative(dist, file)}`);
      continue;
    }
    if (url.hash && target.endsWith(".html")) {
      const text = await readFile(target, "utf8");
      const id = decodeURIComponent(url.hash.slice(1));
      if (!text.includes(`id="${id}"`))
        fail(
          `Missing anchor ${url.href} linked by ${path.relative(dist, file)}`,
        );
    }
    checked++;
  }
}
const search = JSON.parse(
  await readFile(path.join(dist, "assets/search.json"), "utf8"),
);
for (const item of search) {
  const url = new URL(item.href, ORIGIN);
  const target = path.join(dist, url.pathname.slice(BASE.length), "index.html");
  try {
    const html = await readFile(target, "utf8");
    if (url.hash && !html.includes(`id="${url.hash.slice(1)}"`))
      fail(`Search target missing: ${item.href}`);
  } catch {
    fail(`Search page missing: ${item.href}`);
  }
}
if (errors) process.exit(1);
console.log(
  `links: ${checked} local resources and ${search.length} search targets checked`,
);
