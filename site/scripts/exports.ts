import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { ROOT, readRegistry, exportsFor } from "./content";
const sync = process.argv.includes("--write");
let stale = false;
for (const [file, text] of Object.entries(exportsFor(await readRegistry()))) {
  const target = path.join(ROOT, "public", file);
  if (sync) await writeFile(target, text);
  else if ((await readFile(target, "utf8").catch(() => null)) !== text) {
    console.error(`Stale generated export: ${file}. Run bun run sync:exports.`);
    stale = true;
  }
}
if (stale) process.exit(1);
console.log(sync ? "exports synchronized" : "exports current");
