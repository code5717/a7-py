const navigation = document.querySelector(".navigation");
const mobileNavigation = matchMedia("(max-width: 899px)");
function adaptNavigation() {
  if (navigation) navigation.open = !mobileNavigation.matches;
}
adaptNavigation();
mobileNavigation.addEventListener("change", adaptNavigation);
const base = "/a7-py";
const known = [
  "start",
  "tour",
  "examples",
  "language",
  "stdlib",
  "compiler",
  "status",
  "release",
  "agent-usage",
  "project",
];
const legacy = location.hash.startsWith("#/")
  ? location.hash.slice(2).replace(/\/$/, "")
  : new URLSearchParams(location.search).get("from")?.replace(/^\/|\/$/g, "");
if (known.includes(legacy)) location.replace(`${base}/${legacy}/`);
const theme = document.querySelector(".theme-control");
if (theme) {
  theme.hidden = false;
  const select = theme.querySelector("select");
  select.value = document.documentElement.dataset.theme || "system";
  select.addEventListener("change", () => {
    const value = select.value;
    if (value === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = value;
    try {
      if (value === "system") localStorage.removeItem("a7-theme");
      else localStorage.setItem("a7-theme", value);
    } catch {}
  });
}
// Code controls enhance a stable, server-rendered toolbar.
document.querySelectorAll(".code-block").forEach((block) => {
  const code = block.querySelector("pre code");
  const copy = block.querySelector(".copy");
  const label = copy.querySelector("[data-copy-label]");
  const feedback = block.querySelector(".copy-status");
  let reset;
  copy.hidden = false;
  async function fallbackCopy(text) {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();
    try {
      document.execCommand("copy");
      return true;
    } catch {
      return false;
    } finally {
      area.remove();
    }
  }
  copy.addEventListener("click", async () => {
    clearTimeout(reset);
    const done = (ok) => {
      if (ok) {
        label.textContent = "Copied";
        feedback.hidden = false;
        feedback.textContent = "Code copied to clipboard.";
        reset = setTimeout(() => {
          label.textContent = "Copy";
          feedback.hidden = true;
        }, 2500);
      } else {
        label.textContent = "Copy";
        feedback.hidden = false;
        feedback.textContent =
          "Copy failed. Select the code and copy it manually, or try again.";
      }
    };
    try {
      await navigator.clipboard.writeText(code.textContent);
      done(true);
    } catch {
      done(await fallbackCopy(code.textContent));
    }
  });
});
// Scroll only the rail. Loading a page must not move the article viewport.
function revealCurrentPage() {
  if (mobileNavigation.matches || !navigation) return;
  const current = navigation.querySelector('[aria-current="page"]');
  if (!current) return;
  const item = current.getBoundingClientRect(),
    rail = navigation.getBoundingClientRect();
  if (item.bottom > rail.bottom)
    navigation.scrollTop += item.bottom - rail.bottom + 16;
  else if (item.top < rail.top)
    navigation.scrollTop -= rail.top - item.top + 16;
}
requestAnimationFrame(revealCurrentPage);
mobileNavigation.addEventListener("change", () =>
  requestAnimationFrame(revealCurrentPage),
);
const outlineLinks = [
  ...document.querySelectorAll(".page-outline a, .mobile-outline a"),
];
const outlineHeadings = [
  ...new Set(
    outlineLinks
      .map((a) => document.getElementById(a.hash.slice(1)))
      .filter(Boolean),
  ),
];
let outlineFrame = false;
function updateOutline() {
  outlineFrame = false;
  const offset =
    document.querySelector(".topbar").getBoundingClientRect().height + 32;
  let current = outlineHeadings[0];
  for (const heading of outlineHeadings) {
    if (heading.getBoundingClientRect().top <= offset) current = heading;
    else break;
  }
  if (
    Math.ceil(scrollY + innerHeight) >=
    document.documentElement.scrollHeight - 2
  )
    current = outlineHeadings.at(-1);
  outlineLinks.forEach((a) => {
    if (current && a.hash === "#" + current.id)
      a.setAttribute("aria-current", "location");
    else a.removeAttribute("aria-current");
  });
}
function scheduleOutline() {
  if (!outlineFrame) {
    outlineFrame = true;
    requestAnimationFrame(updateOutline);
  }
}
addEventListener("scroll", scheduleOutline, { passive: true });
addEventListener("resize", scheduleOutline, { passive: true });
scheduleOutline();
const dialog = document.getElementById("search");
const opener = document.querySelector("[data-search-open]");
if (opener && /(mac|iphone|ipad)/i.test(navigator.platform || "")) {
  const hint = opener.querySelector("kbd");
  if (hint) hint.textContent = "⌘K";
}
const input = document.getElementById("search-input");
const results = document.getElementById("search-results");
const status = document.getElementById("search-status");
let index,
  request,
  generation = 0;
async function loadIndex() {
  if (index) return index;
  if (!request)
    request = fetch(`${base}/assets/search.json`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Search unavailable");
        const value = await response.json();
        if (
          !Array.isArray(value) ||
          value.some(
            (v) => typeof v.text !== "string" || typeof v.href !== "string",
          )
        )
          throw new Error("Invalid index");
        return (index = value);
      })
      .finally(() => {
        request = null;
      });
  return request;
}
function highlight(element, text, terms) {
  const needle = terms.find((term) => text.toLowerCase().includes(term));
  if (!needle) {
    element.textContent = text;
    return;
  }
  const at = text.toLowerCase().indexOf(needle);
  const mark = document.createElement("mark");
  mark.textContent = text.slice(at, at + needle.length);
  element.append(text.slice(0, at), mark, text.slice(at + needle.length));
}
async function search() {
  const current = ++generation;
  status.textContent = "Loading search index…";
  results.replaceChildren();
  try {
    const items = await loadIndex();
    if (current !== generation) return;
    const query = input.value.trim().toLowerCase();
    const terms = query.split(/\s+/).filter(Boolean);
    const ranked = items
      .filter((item) => query || item.level === 1)
      .map((item) => {
        const text =
          `${item.title} ${item.section} ${item.text} ${item.features}`.toLowerCase();
        return {
          item,
          score: terms.every((t) => text.includes(t))
            ? terms.reduce(
                (score, t) =>
                  score +
                  (item.section.toLowerCase().includes(t) ? 5 : 1) +
                  (item.title.toLowerCase().includes(t) ? 3 : 0),
                0,
              ) + 1
            : 0,
        };
      })
      .filter((x) => x.score)
      .sort((a, b) => b.score - a.score);
    const matches = query ? ranked.slice(0, 20) : ranked;
    status.textContent = query
      ? ranked.length
        ? `${matches.length < ranked.length ? matches.length + " of " : ""}${ranked.length} ${ranked.length === 1 ? "result" : "results"}.`
        : "No matching documentation. Try another word."
      : "Browse documentation or type to search.";
    for (const { item } of matches) {
      const li = document.createElement("li"),
        a = document.createElement("a"),
        small = document.createElement("small");
      a.href = item.href;
      const context = document.createElement("span");
      context.className = "search-context";
      context.textContent = item.title;
      const title = document.createElement("strong");
      highlight(title, item.section, terms);
      a.append(context, title);
      const plain = item.text;
      const lower = plain.toLowerCase();
      const excerptTerm = terms.find((term) => lower.includes(term));
      const at = excerptTerm ? lower.indexOf(excerptTerm) : 0;
      const start = Math.max(0, at - 45);
      highlight(
        small,
        (start ? "…" : "") +
          plain.slice(start, start + 180) +
          (plain.length > start + 180 ? "…" : ""),
        terms,
      );
      a.append(small);
      li.append(a);
      results.append(li);
    }
  } catch {
    if (current !== generation) return;
    status.textContent =
      "Search could not load. Check your connection and retry, or use the documentation navigation.";
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Retry search";
    button.onclick = search;
    const li = document.createElement("li");
    li.append(button);
    results.append(li);
  }
}
if (dialog && typeof dialog.showModal === "function") {
  opener.hidden = false;
  function open() {
    dialog.showModal();
    input.focus();
    search();
  }
  opener.addEventListener("click", open);
  document
    .querySelector("[data-search-close]")
    .addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => opener.focus());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      const r = dialog.getBoundingClientRect();
      if (
        event.clientX < r.left ||
        event.clientX > r.right ||
        event.clientY < r.top ||
        event.clientY > r.bottom
      )
        dialog.close();
    }
  });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      if (!dialog.open) open();
    }
  });
  input.addEventListener("input", () => {
    clearTimeout(input._debounce);
    status.textContent = "Typing…";
    input._debounce = setTimeout(search, 120);
  });
  dialog.addEventListener("keydown", (event) => {
    if (
      event.altKey ||
      event.ctrlKey ||
      event.metaKey ||
      event.shiftKey ||
      event.isComposing
    )
      return;
    const inInput = event.target === input;
    const inResults = results.contains(event.target);
    if (!inInput && !inResults) return;
    const links = [...results.querySelectorAll("a")],
      i = links.indexOf(document.activeElement);
    if (event.key === "ArrowDown" && links.length) {
      event.preventDefault();
      links[Math.min(i + 1, links.length - 1)].focus();
    }
    if (event.key === "ArrowUp" && links.length && inResults) {
      event.preventDefault();
      if (i <= 0) input.focus();
      else links[i - 1].focus();
    }
    if (
      event.key === "Enter" &&
      document.activeElement === input &&
      links.length
    ) {
      event.preventDefault();
      links[0].click();
    }
  });
}
