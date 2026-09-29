import { chromium } from "/home/cx89/Projects/agent-ops/node_modules/playwright-core/index.mjs";
import fs from "node:fs";

const BASE = "http://127.0.0.1:4174/a7-py/";
const out = { checks: [] };
const check = (name, pass, detail = "") => {
  out.checks.push({ name, pass, detail });
  console.log(`${pass ? "PASS" : "FAIL"} ${name} ${detail}`);
};
const shots = "/tmp/opencode/audit/shots";
fs.mkdirSync(shots, { recursive: true });

const browser = await chromium.launch();
try {
  // ---------- Desktop light ----------
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    permissions: ["clipboard-read", "clipboard-write"],
  });
  const page = await ctx.newPage();
  await page.goto(BASE, { waitUntil: "networkidle" });

  const h1s = await page.locator("main h1").count();
  check("home: exactly one article H1", h1s === 1, `count=${h1s}`);

  const railVisible = await page.locator(".sidebar .navigation nav").isVisible();
  check("desktop: nav rail visible", railVisible);

  const cur = await page.locator('.nav-group a[aria-current="page"]').allTextContents();
  check("desktop: current page marked in rail", cur.length === 1, cur.join("|"));

  const outline = await page.locator(".page-outline nav a").count();
  check("desktop: outline present", outline > 0, `links=${outline}`);

  // toolbar + language label
  const firstBlock = page.locator(".code-block").first();
  const lang = await firstBlock.locator(".code-language").textContent();
  check("code toolbar: language label", !!lang && lang.length > 0, lang ?? "");
  const copyVisible = await firstBlock.locator("button.copy").isVisible();
  check("code toolbar: copy button revealed by JS", copyVisible);
  const statusHidden = await firstBlock.locator(".copy-status").isHidden();
  check("code toolbar: copy status initially hidden", statusHidden);

  // copy success
  await firstBlock.locator("button.copy").click();
  await page.waitForTimeout(200);
  const label = await firstBlock.locator("[data-copy-label]").textContent();
  const statusText = await firstBlock.locator(".copy-status").textContent();
  check("copy: success feedback", label === "Copied" && /copied/i.test(statusText ?? ""), `${label}|${statusText}`);
  const clip = await page.evaluate(() => navigator.clipboard.readText());
  const codeText = await firstBlock.locator("pre code").textContent();
  check("copy: clipboard matches code", clip === codeText);

  // permalink opacity on hover
  const h2 = page.locator(".prose h2").first();
  await h2.hover();
  const anchorOp = await h2.locator(".heading-anchor").evaluate((el) => getComputedStyle(el).opacity);
  check("permalink: visible on h2 hover", Number(anchorOp) > 0.9, `opacity=${anchorOp}`);
  const href = await h2.locator(".heading-anchor").getAttribute("href");
  check("permalink: href targets heading id", href?.startsWith("#"), href ?? "");

  // theme switch persists
  await page.selectOption(".theme-control select", "dark");
  await page.reload({ waitUntil: "networkidle" });
  const theme = await page.evaluate(() => document.documentElement.dataset.theme);
  check("theme: explicit dark persists after reload", theme === "dark");
  await page.screenshot({ path: `${shots}/home-1440-dark-fresh.png`, fullPage: false });
  await page.selectOption(".theme-control select", "system");

  // search flow
  await page.keyboard.press("ControlOrMeta+k");
  await page.waitForSelector("#search[open]");
  const focused = await page.evaluate(() => document.activeElement?.id);
  check("search: dialog opens focused on input", focused === "search-input", focused ?? "");
  await page.fill("#search-input", "usize");
  await page.waitForTimeout(300);
  const statusMsg = await page.locator("#search-status").textContent();
  const resultCount = await page.locator("#search-results a").count();
  check("search: usize results render", resultCount > 0, `${resultCount} links; status="${statusMsg?.trim()}"`);
  const hasMark = await page.locator("#search-results mark").count();
  check("search: matched text highlighted", hasMark > 0, `marks=${hasMark}`);
  const contextShown = await page.locator(".search-context").first().textContent();
  check("search: result shows page context", !!contextShown && contextShown.length > 0, contextShown ?? "");
  // results area scrollable, controls fixed
  const scrollable = await page.evaluate(() => {
    const r = document.getElementById("search-results");
    return r.scrollHeight > r.clientHeight && getComputedStyle(r).overflowY !== "visible";
  });
  check("search: result list is independently scrollable", scrollable);
  await page.keyboard.press("ArrowDown");
  const inResults = await page.evaluate(() => document.activeElement?.closest("#search-results") != null);
  check("search: ArrowDown focuses a result", inResults);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(100);
  const closed = await page.evaluate(() => !document.getElementById("search").open);
  const focusBack = await page.evaluate(() => document.activeElement?.hasAttribute("data-search-open"));
  check("search: Escape closes and restores focus", closed && focusBack);

  // scoped keyboard: Tab from input stays in dialog
  await page.keyboard.press("ControlOrMeta+k");
  await page.waitForSelector("#search[open]");
  let escapedDialog = false;
  for (let i = 0; i < 30; i++) {
    await page.keyboard.press("Tab");
    const still = await page.evaluate(() => document.activeElement?.closest("dialog") != null || document.activeElement === document.body);
    if (!still) { escapedDialog = true; break; }
  }
  check("search: 30 tabs stay inside dialog (no underlying focus)", !escapedDialog);
  await page.keyboard.press("Escape");

  // outline tracking
  await page.goto(BASE + "stdlib/", { waitUntil: "networkidle" });
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(300);
  const outlineCur = await page.locator('.page-outline a[aria-current="location"]').textContent();
  check("outline: bottom scroll marks last section", !!outlineCur && outlineCur.length > 0, outlineCur ?? "");
  const mobileOutlineCur = await page.evaluate(() => {
    window.scrollTo(0, 0);
    return document.querySelectorAll('.mobile-outline a[aria-current="location"]').length >= 0;
  });
  // pager
  const pagerPrev = await page.locator(".pager a").first().getAttribute("href");
  check("pager: previous link present on stdlib", !!pagerPrev, pagerPrev ?? "");
  const pagerBg = await page.locator(".pager a").first().evaluate((el) => getComputedStyle(el).textDecorationLine);
  check("pager: no underline until hover", pagerBg === "none", pagerBg);
  await ctx.close();

  // ---------- copy failure path (clipboard permission denied) ----------
  const ctxNoClip = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const p2 = await ctxNoClip.newPage();
  await p2.goto(BASE, { waitUntil: "networkidle" });
  await p2.locator(".code-block button.copy").first().click();
  await p2.waitForTimeout(300);
  const failMsg = await p2.locator(".copy-status").first().textContent();
  check("copy: failure feedback shown outside code", /failed/i.test(failMsg ?? ""), failMsg?.trim() ?? "");
  await ctxNoClip.close();

  // ---------- search failure + retry ----------
  const ctx3 = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const p3 = await ctx3.newPage();
  await p3.route("**/assets/search.json", (r) => r.abort());
  await p3.goto(BASE, { waitUntil: "networkidle" });
  await p3.locator("[data-search-open]").click();
  await p3.waitForTimeout(300);
  const errStatus = await p3.locator("#search-status").textContent();
  const retryVisible = await p3.locator("#search-results button").isVisible();
  check("search: blocked index shows failure + retry", /could not load/i.test(errStatus ?? "") && retryVisible, errStatus?.trim() ?? "");
  await p3.unroute("**/assets/search.json");
  await p3.locator("#search-results button").click();
  await p3.waitForTimeout(500);
  const recovered = await p3.locator("#search-results a").count();
  check("search: retry recovers results", recovered > 0, `${recovered} links`);
  await ctx3.close();

  // ---------- mobile 390 ----------
  const m = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const pm = await m.newPage();
  await pm.goto(BASE, { waitUntil: "networkidle" });
  const navOpen = await pm.locator(".navigation").evaluate((el) => el.open);
  check("mobile: nav disclosure initially closed with JS", !navOpen);
  const overflowX = await pm.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  check("mobile 390: no horizontal overflow", !overflowX);
  await pm.screenshot({ path: `${shots}/home-390-fresh.png` });
  // mobile outline visible
  const mobOutline = await pm.locator(".mobile-outline").isVisible();
  check("mobile: outline disclosure visible", mobOutline);
  // 44px copy button
  const copyH = await pm.locator(".code-block button.copy").first().evaluate((el) => el.getBoundingClientRect().height);
  check("mobile: copy control at least 44px", copyH >= 43, `height=${copyH}`);
  await m.close();

  // ---------- no-JS ----------
  const nj = await browser.newContext({ viewport: { width: 1280, height: 900 }, javaScriptEnabled: false });
  const pn = await nj.newPage();
  await pn.goto(BASE, { waitUntil: "networkidle" });
  const navShown = await pn.locator(".navigation nav").isVisible();
  const copyHidden = await pn.locator(".code-block button.copy").first().isHidden();
  const searchHidden = await pn.locator("[data-search-open]").isHidden();
  const themeHidden = await pn.locator(".theme-control").isHidden();
  const contentVisible = await pn.locator(".prose h1").isVisible();
  check("no-JS: nav, content visible; copy/search/theme hidden", navShown && copyHidden && searchHidden && themeHidden && contentVisible,
    `nav=${navShown} copyHidden=${copyHidden} searchHidden=${searchHidden} themeHidden=${themeHidden} content=${contentVisible}`);
  const twinLink = await pn.locator('a[href$="/docs/index.md"]').first().isVisible();
  check("no-JS: markdown twin link works", twinLink);
  await nj.close();

  // ---------- narrow 320 ----------
  const n = await browser.newContext({ viewport: { width: 320, height: 700 } });
  const pn2 = await n.newPage();
  await pn2.goto(BASE + "compiler/", { waitUntil: "networkidle" });
  const overflow320 = await pn2.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  check("320px compiler: no horizontal overflow", !overflow320);
  const h1Size = await pn2.locator(".prose h1").evaluate((el) => getComputedStyle(el).fontSize);
  check("320px: mobile H1 32px", h1Size === "32px", h1Size);
  await pn2.screenshot({ path: `${shots}/compiler-320-fresh.png` });
  await n.close();
} finally {
  await browser.close();
}
fs.writeFileSync("/tmp/opencode/audit/fresh-browser-results.json", JSON.stringify(out, null, 2));
const failed = out.checks.filter((c) => !c.pass);
console.log(`\n${out.checks.length - failed.length}/${out.checks.length} checks passed`);
process.exit(0);
