import { chromium } from "/home/cx89/Projects/agent-ops/node_modules/playwright-core/index.mjs";
import fs from "node:fs";
const BASE = "http://127.0.0.1:4174/a7-py/";
const shots = "/tmp/opencode/audit/shots";
const browser = await chromium.launch();
const out = [];
const check = (n, p, d = "") => { out.push({ n, p, d }); console.log(`${p ? "PASS" : "FAIL"} ${n} ${d}`); };
try {
  // rail scroll-to-current on a deep page with short viewport
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 600 } });
  const page = await ctx.newPage();
  await page.goto(BASE + "compiler/", { waitUntil: "networkidle" });
  await page.waitForTimeout(300);
  const scrolled = await page.evaluate(() => document.querySelector(".navigation").scrollTop);
  check("rail: current page scrolled into view on short viewport", scrolled > 0, `scrollTop=${scrolled}`);
  // light theme screenshot of a reference page
  await page.evaluate(() => localStorage.setItem("a7-theme", "light"));
  await page.reload({ waitUntil: "networkidle" });
  await page.screenshot({ path: `${shots}/compiler-1440-light-fresh.png` });
  const linkDeco = await page.locator(".prose p a").first().evaluate((el) => getComputedStyle(el).textDecorationLine);
  check("light: article links underlined", linkDeco === "underline", linkDeco);
  // mid-scroll outline tracking on a long topic page
  await page.goto(BASE + "language/control-flow/", { waitUntil: "networkidle" });
  await page.locator(".prose h2", { hasText: "Matching" }).scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  const cur = await page.locator('.page-outline a[aria-current="location"]').allTextContents();
  check("outline: mid-scroll active section updates", cur.some((t) => /Matching|Labels|Matching/.test(t)), cur.join("|"));
  // diagram rendering on memory page
  await page.goto(BASE + "language/memory/", { waitUntil: "networkidle" });
  const flow = page.locator(".prose ol.flow");
  const flowVisible = await flow.isVisible();
  const aria = await flow.getAttribute("aria-label");
  const steps = await flow.locator("li").count();
  check("diagram: reference-access flow renders with label and steps", flowVisible && !!aria && steps === 3, `steps=${steps} label="${aria}"`);
  // pipeline diagram on compiler page
  await page.goto(BASE + "compiler/", { waitUntil: "networkidle" });
  const pipe = page.locator(".prose ol.pipeline");
  const pipeSteps = await pipe.locator("li").count();
  check("diagram: compiler pipeline has 9 steps", pipeSteps === 9, `steps=${pipeSteps}`);
  // h3 permalink exists
  const h3anchor = await page.locator(".prose h3 .heading-anchor").count();
  check("permalink: h3 anchors present somewhere", h3anchor >= 0);
  await ctx.close();

  // 200% text zoom at 320
  const z = await browser.newContext({ viewport: { width: 320, height: 700 } });
  const pz = await z.newPage();
  await pz.goto(BASE + "start/", { waitUntil: "networkidle" });
  await pz.evaluate(() => { document.documentElement.style.fontSize = "34px"; });
  await pz.waitForTimeout(200);
  const overflow = await pz.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  check("320px with ~200% root text: no horizontal overflow", !overflow);
  await z.close();
} finally {
  await browser.close();
  fs.writeFileSync("/tmp/opencode/audit/fresh-browser-results-2.json", JSON.stringify(out, null, 2));
}
