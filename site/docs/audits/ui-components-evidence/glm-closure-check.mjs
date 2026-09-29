import { chromium } from "/home/cx89/Projects/agent-ops/node_modules/playwright-core/index.mjs";
import fs from "node:fs";
const BASE = "http://127.0.0.1:4174/a7-py/";
const out = [];
const check = (n, p, d = "") => { out.push({ n, p, d }); console.log(`${p ? "PASS" : "FAIL"} ${n} ${d}`); };
const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  // --- 404 page served unchanged ---
  const r404 = await page.goto(BASE + "not-a-page/", { waitUntil: "load" });
  check("404 route returns 404 with styled page", r404.status() === 404 && await page.locator(".not-found h1").isVisible());

  // --- search excerpt: new algorithm (first term present in section text) ---
  await page.goto(BASE, { waitUntil: "networkidle" });
  const index = await (await fetch(BASE + "assets/search.json")).json();
  // find entries where term A is only in title/features, term B in text
  const candidates = index.filter((e) => {
    const t = e.text.toLowerCase();
    const meta = `${e.title} ${e.features}`.toLowerCase();
    return meta.includes("stdlib") && !t.includes("stdlib") && t.includes("println");
  });
  check("fixture exists: entries with 'stdlib' only in metadata and 'println' in text", candidates.length > 0, `${candidates.length} entries`);
  // drive the real UI
  await page.keyboard.press("ControlOrMeta+k");
  await page.waitForSelector("#search[open]");
  await page.fill("#search-input", "stdlib println");
  await page.waitForTimeout(400);
  const rendered = await page.evaluate(() => {
    return [...document.querySelectorAll("#search-results li")].slice(0, 8).map((li) => {
      const small = li.querySelector("small");
      return {
        text: small?.textContent ?? "",
        marks: [...(small?.querySelectorAll("mark") ?? [])].map((m) => m.textContent),
        href: li.querySelector("a")?.getAttribute("href") ?? "",
      };
    });
  });
  const statusMsg = await page.locator("#search-status").textContent();
  check("query 'stdlib println' returns results", rendered.length > 0, `status="${statusMsg?.trim()}" results=${rendered.length}`);
  // recompute the new algorithm for the same hrefs and compare
  const terms = ["stdlib", "println"];
  let mismatched = 0, leadingEllipsis = 0, marked = 0;
  for (const r of rendered) {
    const entry = index.find((e) => e.href === r.href);
    if (!entry) { mismatched++; continue; }
    const plain = entry.text;
    const lower = plain.toLowerCase();
    const excerptTerm = terms.find((t) => lower.includes(t));
    const at = excerptTerm ? lower.indexOf(excerptTerm) : 0;
    const start = Math.max(0, at - 45);
    const expected = (start ? "…" : "") + plain.slice(start, start + 180) + (plain.length > start + 180 ? "…" : "");
    if (r.text !== expected) mismatched++;
    if (r.text.startsWith("…")) leadingEllipsis++;
    if (r.marks.length) marked++;
  }
  check("rendered excerpts match new first-in-text-term algorithm", mismatched === 0, `${rendered.length} compared, ${mismatched} mismatched`);
  check("excerpt offsets into text (leading ellipsis) present", leadingEllipsis > 0, `${leadingEllipsis}/${rendered.length}`);
  check("matched term highlighted in excerpts", marked > 0, `${marked}/${rendered.length}`);
  // metadata-only term still matches via features (results exist) and excerpt never contains the raw id noise
  check("no raw feature ids leak into excerpts", rendered.every((r) => !r.text.includes("stdlib-")));
  await page.keyboard.press("Escape");

  // --- computed CSS regression spots (desktop) ---
  await page.goto(BASE + "start/", { waitUntil: "networkidle" });
  const borderCol = await page.locator(".theme-control select").evaluate((el) => getComputedStyle(el).borderColor);
  const muted = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--muted").trim());
  const rgb = await page.evaluate((v) => {
    const d = document.createElement("div"); d.style.color = v; document.body.append(d);
    const c = getComputedStyle(d).color; d.remove(); return c;
  }, muted);
  check("control border uses --muted", borderCol === rgb, `${borderCol} vs ${rgb}`);
  const underline = await page.locator(".prose p a").first().evaluate((el) => getComputedStyle(el).textDecorationLine);
  check("prose links underlined", underline === "underline", underline);
  const toolbarH = await page.locator(".code-toolbar").first().evaluate((el) => getComputedStyle(el).minHeight);
  check("desktop toolbar min-height 3.25rem", toolbarH === "52px", toolbarH);
  // active outline after clicking a permalink
  await page.locator(".prose h2 .heading-anchor").first().click();
  await page.waitForTimeout(400);
  const cur = await page.locator('.page-outline a[aria-current="location"]').allTextContents();
  const mobCur = await page.evaluate(() => 1); // mobile outline hidden on desktop; checked below
  check("outline highlights clicked section", cur.length === 1, cur.join("|"));
  const copyDeskH = await page.locator(".code-block button.copy").first().evaluate((el) => el.getBoundingClientRect().height);
  check("desktop copy button 32px (2rem)", Math.round(copyDeskH) === 32, `${copyDeskH}`);
  await ctx.close();

  // --- mobile 390: copy height, toolbar height, outline aria-current ---
  const m = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const pm = await m.newPage();
  await pm.goto(BASE + "start/", { waitUntil: "networkidle" });
  const copyH = await pm.locator(".code-block button.copy").first().evaluate((el) => el.getBoundingClientRect().height);
  check("mobile copy control >= 44px", copyH >= 44, `${copyH}`);
  const mToolbarH = await pm.locator(".code-toolbar").first().evaluate((el) => getComputedStyle(el).minHeight);
  check("mobile toolbar min-height 3.75rem (60px)", mToolbarH === "60px", mToolbarH);
  // open mobile outline, click a link, verify aria-current moves there
  await pm.locator(".mobile-outline summary").click();
  await pm.locator(".mobile-outline a").first().click();
  await pm.waitForTimeout(500);
  const mCur = await pm.locator('.mobile-outline a[aria-current="location"]').allTextContents();
  check("mobile outline marks active section after link click", mCur.length >= 1, mCur.join("|"));
  const overflow = await pm.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  check("mobile 390 no horizontal overflow", !overflow);
  await pm.screenshot({ path: "/tmp/opencode/audit/shots/closure-390-start.png" });
  await m.close();

  // --- light theme prose underline + outline ---
  const l = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const pl = await l.newPage();
  await pl.goto(BASE + "language/arrays-strings/", { waitUntil: "networkidle" });
  const lu = await pl.locator(".prose p a").first().evaluate((el) => getComputedStyle(el).textDecorationLine);
  check("light theme prose link underlined", lu === "underline", lu);
  const borderL = await pl.locator("[data-search-open]").evaluate((el) => getComputedStyle(el).borderColor);
  check("light theme control border renders", borderL.length > 0, borderL);
  await pl.screenshot({ path: "/tmp/opencode/audit/shots/closure-1440-light-arrays.png" });
  await l.close();
} finally {
  await browser.close();
  fs.writeFileSync("/tmp/opencode/audit/closure-browser-results.json", JSON.stringify(out, null, 2));
}
