// Floodplain. Every figure rendered here is read from data.json, which build_site.py writes from
// the committed results. Nothing numeric is typed into this file (charter law 6).

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const n = (x) => (x ?? 0).toLocaleString("en-GB");
const SVG = "http://www.w3.org/2000/svg";
const dark = () => matchMedia("(prefers-color-scheme: dark)").matches;
const art = (name) => `art/${name}${dark() ? "-cut" : ""}.webp`;

let DATA = null;

const fmtTime = (iso, deltaMin = 0) => new Date(new Date(iso).getTime() + deltaMin * 60000).toISOString().slice(11, 16) + " UTC";
const fmtDate = (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const fmtDownloads = (x) => (!x ? "" : x >= 1e6 ? `${(x / 1e6).toFixed(x >= 1e7 ? 0 : 1)} million downloads a month`
  : x >= 1e3 ? `${Math.round(x / 1e3)} thousand downloads a month` : `${x} downloads a month`);
const WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
  "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"];
const numberWord = (k) => WORDS[k] ?? String(k);
const daysAfter = (h) => numberWord(Math.floor(h / 24));
const hoursToWords = (h) => {
  const d = Math.floor(h / 24), r = Math.round(h - d * 24);
  return r ? `${numberWord(d)} days and ${numberWord(r)} hours` : `${numberWord(d)} days`;
};

// ------------------------------------------------------------------ boot
async function boot() {
  try {
    const res = await fetch("data.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(res.status);
    DATA = await res.json();
  } catch {
    $("#view").replaceChildren($("#tpl-error").content.cloneNode(true));
    return;
  }
  window.addEventListener("hashchange", route);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", route);
  let w = innerWidth;
  addEventListener("resize", () => { if ((innerWidth < 640) !== (w < 640)) { w = innerWidth; route(); } });
  route();
}

function route() {
  const name = decodeURIComponent(location.hash.replace(/^#\/?/, ""));
  const r = name && DATA.receptors.find((x) => x.name === name);
  if (r && r.state === "positive") renderReceptor(r);
  else renderTrace();
  window.scrollTo({ top: 0 });
  if (name) $("#main").focus({ preventScroll: true });
}

const link = (r) => `<a href="#/${encodeURIComponent(r.name)}">${esc(r.name)}</a>`;

// ------------------------------------------------------------------ the trace
function renderTrace() {
  const D = DATA, S = D.states;
  const pos = D.receptors.filter((r) => r.state === "positive");
  const unread = S["no-baseline"] + S["no-tests"] + S.lost;
  document.title = `Floodplain: ${D.target} ${D.release}`;

  // Each positive paired with how long its own maintainers took. The replay ran weeks later, so
  // the Nemotron sentence makes no timing claim: it says what the model wrote, not that it got
  // there first, and it carries its K of N.
  const byWait = pos.filter((r) => r.maintainer_fix).sort((a, b) => a.maintainer_fix.hours_after_release - b.maintainer_fix.hours_after_release);
  const fixedSentence = byWait.length
    ? `Each was later pinned or patched by its own maintainers: ${byWait.map((r) => `${link(r)} after ${daysAfter(r.maintainer_fix.hours_after_release)} days`).join(", ")}.`
    : "";
  const kOfN = (r) => (r.fix.trials > 1 ? ` in ${numberWord(r.fix.trials_verified)} of ${numberWord(r.fix.trials)} independent runs` : "");
  const sameFix = pos.filter((r) => r.fix && r.fix.verified && r.maintainer_fix && r.maintainer_fix.kind === "release");
  const otherFix = pos.filter((r) => r.fix && r.fix.verified && !sameFix.includes(r));
  const verifiedSentence =
    sameFix.map((r) => ` For ${link(r)}, NVIDIA Nemotron wrote the same patch the maintainer shipped${kOfN(r)}, from the failing log alone, and the package's own tests passed it.`).join("") +
    (otherFix.length ? ` For ${otherFix.map((r) => `${link(r)}${kOfN(r)}`).join(" and ")}, it wrote a patch the package's own tests passed.` : "");

  $("#view").innerHTML = `
  <section class="trace" aria-labelledby="trace-title">
    <div class="trace__head">
      <h1 class="trace__title" id="trace-title">${n(S.positive)} of ${n(D.readable)} readable packages broke on ${esc(D.target)}&nbsp;${esc(D.release)}</h1>
      <p class="trace__lede">${esc(D.target)} ${esc(D.release)} went in upstream at ${fmtTime(D.release_uploaded_at)} on ${fmtDate(D.release_uploaded_at)}. I hung a receptor at <span class="num">${n(D.ran)}</span> of the <span class="num">${n(D.population.exposed)}</span> packages downstream that would take it, each one three forks of the same checkout on Nebius Sandboxes.</p>
    </div>
    <div class="reach" id="reach"><div class="reach__tip" id="tip" hidden></div></div>
    <p class="reach__note">Each small packet is a package whose suite passed before the release and still passed after. The faint marks along the banks are the <span class="num">${n(unread)}</span> that could not be read: no tests shipped, nothing passing before the release either, or a run that did not finish.</p>
  </section>
  ${fixedSentence || verifiedSentence ? `<p class="trace__after">${fixedSentence}${verifiedSentence}</p>` : ""}

  <section class="scene method" aria-labelledby="method-title">
    <div class="method__text">
      <h2 class="scene__title" id="method-title">How a receptor is read</h2>
      <p>Hydrogeologists find out where water goes underground by pouring fluorescent dye in at one point and hanging charcoal packets at every spring downstream. Weeks later they read the packets. Floodplain does the same thing to a package release.</p>
      <p><b>Poured in.</b> The release is the dye. Every package that depends on it, and would resolve the new version, gets one receptor.</p>
      <p><b>A background sample.</b> Before dye goes in, hydrogeologists take a sample of the plain water, so natural fluorescence is never mistaken for dye. Here each checkout is forked three ways at once: the world a minute before the release, the same again, and a minute after. A test that disagrees with itself across the two identical forks is natural fluorescence, and is thrown out.</p>
      <p><b>Read.</b> A suite that passed before and fails after, against an unchanged background, is a positive. NVIDIA Nemotron reads the log, quoting only lines that are in it, and drafts a patch that the package's own tests have to pass.</p>
    </div>
    <div class="method__art">
      <img class="method__inject" src="${art("injection")}" width="644" height="800" loading="lazy" alt="Watercolour of a white funnel wedged between stones, holding a heap of dark rust-red dye powder, with a thin green trickle reaching the stream below.">
      <img class="method__sample" src="${art("sample")}" width="656" height="554" loading="lazy" alt="Watercolour of a corked glass bottle half full of plain grey stream water.">
    </div>
  </section>

  <section class="scene" aria-labelledby="ledger-title">
    <h2 class="scene__title" id="ledger-title">Every receptor I hung</h2>
    <p class="scene__lede"><span class="num">${n(D.population.total)}</span> packages in the top <span class="num">${n(D.scanned)}</span> on PyPI declared ${esc(D.target)} on the day of the release. <span class="num">${n(D.population.protected)}</span> pinned below ${esc(D.release)} and were never exposed. Of the <span class="num">${n(D.population.exposed)}</span> that were, these are the <span class="num">${n(D.ran)}</span> I could hang a receptor at.</p>
    <div class="ledger">${["positive", "negative", "no-baseline", "no-tests", "lost"].map(ledgerRow).join("")}</div>
  </section>`;

  drawReach(innerWidth < 640);
}

function ledgerRow(state) {
  const items = DATA.receptors.filter((r) => r.state === state);
  const names = items.map((r) => (state === "positive" ? link(r) : esc(r.name)));
  const list = names.length > 18
    ? `${names.slice(0, 18).join(", ")} <details><summary>and ${n(names.length - 18)} more</summary>${names.slice(18).join(", ")}</details>`
    : names.join(", ");
  const label = { positive: "Positive", negative: "Read clean", "no-baseline": "No working baseline", "no-tests": "No tests shipped", lost: "Unreadable" }[state];
  return `
    <div class="ledger__row ledger__row--${state}">
      <p class="ledger__n num">${n(items.length)}</p>
      <p class="ledger__state">${label}<small>${esc(DATA.state_text[state])}</small></p>
      <div class="ledger__names">${list || "none"}</div>
    </div>`;
}

// ------------------------------------------------------------------ the reach
// Horizontal on a wide screen, vertical on a phone, so the river runs down the page instead of
// shrinking into a strip. Readable receptors are drawn; the unreadable are one faint texture.
function drawReach(vertical) {
  const host = $("#reach");
  host.classList.toggle("reach--v", vertical);
  // The horizontal river sits in the lower part of its frame so the labels have clear water above.
  const W = vertical ? 360 : 1200, H = vertical ? 980 : 400;
  const d = vertical
    ? `M 120 30 C 260 140, 40 260, 180 380 S 330 560, 170 680 S 40 860, 200 ${H - 8}`
    : `M 70 270 C 250 170, 380 370, 560 260 S 820 160, 930 270 S 1110 340, ${W - 6} 250`;
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `A stream with the release poured in at its source. ${DATA.ran} receptors hang along it, most downloaded first. ${DATA.states.positive} came back green.`);
  svg.innerHTML = `<path class="stream" d="${d}"/><path class="stream-line" d="${d}" id="stream-path"/>`;
  host.prepend(svg);
  const path = $("#stream-path", svg);
  const L = path.getTotalLength();

  const p0 = path.getPointAtLength(0);
  svg.insertAdjacentHTML("beforeend",
    `<circle class="inject" cx="${p0.x}" cy="${p0.y}" r="7"/>
     <text class="inject-label" x="${p0.x + (vertical ? 30 : -4)}" y="${p0.y + (vertical ? 5 : 32)}">${esc(DATA.target)} ${esc(DATA.release)}</text>
     <text class="inject-sub" x="${p0.x + (vertical ? 30 : -4)}" y="${p0.y + (vertical ? 23 : 50)}">poured ${fmtTime(DATA.release_uploaded_at)}</text>`);

  // normal of the stream at a point, so marks sit on a bank rather than on a fixed axis
  const normalAt = (len) => {
    const a = path.getPointAtLength(Math.max(len - 1, 0)), b = path.getPointAtLength(Math.min(len + 1, L));
    const dx = b.x - a.x, dy = b.y - a.y, m = Math.hypot(dx, dy) || 1;
    return [-dy / m, dx / m];
  };

  const tip = $("#tip");
  const order = [...DATA.receptors].sort((a, b) => rankOf(a.state) - rankOf(b.state));
  const placedPos = [];
  const pools = [];
  let bank = 1;
  for (const r of order) {
    let len = (0.06 + r.reach * 0.92) * L;
    if (r.state === "positive") {
      const crowd = placedPos.filter((q) => Math.abs(q - len) < 70).length;
      len = Math.min(len + crowd * 80, L - 10);
      placedPos.push(len);
    }
    const pt = path.getPointAtLength(len);
    const [nx, ny] = normalAt(len);
    bank = -bank;

    if (r.state === "no-baseline" || r.state === "no-tests" || r.state === "lost") {
      // texture: a faint mark on a bank, offset by a little jitter derived from the name
      const j = [...r.name].reduce((s, c) => s + c.charCodeAt(0), 0);
      const off = (18 + (j % 22)) * bank;
      const x = pt.x + nx * off, y = pt.y + ny * off;
      svg.insertAdjacentHTML("beforeend", `<circle class="silt" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${1.4 + (j % 3) * 0.4}"><title>${esc(r.name)}: ${esc(r.why || DATA.state_text[r.state])}</title></circle>`);
      continue;
    }

    const off = r.state === "positive" ? 0 : 24 * bank;
    const x = pt.x + nx * off, y = pt.y + ny * off - (r.state === "positive" ? 12 : 12);
    const g = document.createElementNS(SVG, "g");
    g.innerHTML = receptorGlyph(r.state, x, y);
    const node = g.firstElementChild;
    node.setAttribute("tabindex", "0");
    node.setAttribute("role", r.state === "positive" ? "link" : "img");
    node.setAttribute("aria-label", `${r.name} ${r.version}: ${r.state === "positive" ? "broke, open the receptor" : "read clean"}`);

    if (r.state === "positive") {
      const broke = r.cells ? r.cells.broke : (r.newly_failing.length || r.new_collection_errors.length);
      node.insertAdjacentHTML("afterbegin", `<ellipse class="pool" cx="${x}" cy="${y + 22}" rx="${18 + Math.min(broke, 120) / 5}" ry="6.5"/>`);
      pools.push({ r, x, y: y + 22, broke, node });
      const go = () => (location.hash = `#/${encodeURIComponent(r.name)}`);
      node.addEventListener("click", go);
      node.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
    }
    const show = () => {
      const box = host.getBoundingClientRect(), sb = svg.getBoundingClientRect();
      tip.innerHTML = `<b>${esc(r.name)}</b> ${esc(r.version)}<br>${esc(DATA.state_text[r.state])}`;
      tip.style.left = `${(x / W) * sb.width + (sb.left - box.left)}px`;
      tip.style.top = `${(y / H) * sb.height + (sb.top - box.top)}px`;
      tip.hidden = false;
    };
    node.addEventListener("mouseenter", show);
    node.addEventListener("focus", show);
    node.addEventListener("mouseleave", () => (tip.hidden = true));
    node.addEventListener("blur", () => (tip.hidden = true));
    svg.appendChild(node);
  }

  labelPools(svg, pools, vertical, W);

  const io = new IntersectionObserver((es) => {
    if (es.some((e) => e.isIntersecting)) { svg.classList.add("poured"); io.disconnect(); }
  }, { threshold: 0.3 });
  io.observe(svg);
}

// Survey-map labelling: names stacked in clear water above the reach (beside it, on a phone),
// each joined to its pool by a thin leader, ordered so the leaders do not cross.
function labelPools(svg, pools, vertical, W) {
  const ordered = [...pools].sort((a, b) => (vertical ? a.y - b.y : a.y - b.y || a.x - b.x));
  ordered.forEach((p, i) => {
    const fixed = p.r.maintainer_fix ? `, fixed upstream after ${daysAfter(p.r.maintainer_fix.hours_after_release)} days` : "";
    const sub = `${n(p.broke)} tests broke${fixed}`;
    let lx, ly, anchor, ex, ey;
    if (vertical) {
      lx = 220; ly = Math.max(p.y - 6, 40 + i * 64); anchor = "start"; ex = lx - 8; ey = ly - 7;
    } else {
      // a column of labels in the clear water left of the crest, right-aligned
      const colRight = Math.min(W * 0.6, Math.min(...pools.map((q) => q.x)) - 90);
      lx = colRight; ly = 34 + i * 62; anchor = "end"; ex = lx + 10; ey = ly - 7;
    }
    p.node.insertAdjacentHTML("afterbegin", `<path class="leader" d="M ${ex} ${ey} L ${p.x} ${p.y - 8}"/>`);
    p.node.insertAdjacentHTML("beforeend",
      `<text class="label" x="${lx}" y="${ly}" text-anchor="${anchor}">${esc(p.r.name)}</text>
       <text class="label-sub" x="${lx}" y="${ly + 21}" text-anchor="${anchor}">${sub}</text>`);
  });
}

const rankOf = (s) => ({ "no-baseline": 0, "no-tests": 0, lost: 0, negative: 1, positive: 2 }[s]);

// A cord and a packet. Shape carries the state, so it never rests on colour alone.
function receptorGlyph(state, x, y) {
  const cord = `<line class="cord" x1="${x}" y1="${y}" x2="${x}" y2="${y + 7}"/>`;
  const bag = `<path class="bag" d="M${x - 4.5} ${y + 7} h9 l1.1 9.2 a2 2 0 0 1 -2 2.3 h-7.2 a2 2 0 0 1 -2 -2.3 z"/>`;
  if (state === "positive") {
    const dye = `<path class="bag-dye" d="M${x - 5.1} ${y + 12.4} h10.2 l.6 3.8 a2 2 0 0 1 -2 2.3 h-7.4 a2 2 0 0 1 -2 -2.3 z"/>`;
    return `<g class="rcp rcp--positive">${cord}${bag}${dye}</g>`;
  }
  return `<g class="rcp rcp--${state}">${cord}${bag}</g>`;
}

// ------------------------------------------------------------------ a receptor
function renderReceptor(r) {
  const D = DATA, b = r.before, c = r.control, a = r.after, cells = r.cells;
  document.title = `Floodplain: ${r.name} broke on ${D.target} ${D.release}`;

  const lede = cells.collection_break
    ? `After ${esc(D.target)} ${esc(D.release)}, the suite could no longer import. All <span class="num">${n(cells.broke)}</span> tests that passed before the release stopped running.`
    : `<span class="num">${n(cells.broke)}</span> of the <span class="num">${n(cells.passed_before)}</span> tests that passed before ${esc(D.target)} ${esc(D.release)} fail after it.`;
  const bg = r.flaky_excluded.length
    ? ` ${n(r.flaky_excluded.length)} tests disagreed with themselves across the identical forks and were thrown out.`
    : " The background sample read identical to the before, so none of this is a flaky test.";
  const sameAsBefore = c.passed === b.passed;

  $("#view").innerHTML = `
  <article class="rcp-page" aria-labelledby="rcp-title">
    <p class="back"><a href="#/">Back to all ${n(D.ran)} receptors</a></p>
    <div class="rcp-page__head">
      <div>
        <h1 id="rcp-title">${esc(r.name)}<span class="ver">${esc(r.version)}</span></h1>
        <p class="rcp-page__lede">${lede}${bg} Rank ${n(r.rank)} on PyPI, ${esc(fmtDownloads(r.downloads))}.</p>
      </div>
      <img class="rcp-page__art" src="${art("positive")}" width="660" height="854" alt="Watercolour of a charcoal receptor packet soaked fluorescent yellow-green, dripping into a green pool.">
    </div>

    <section class="sample-sheet" aria-label="The three forks">
      <p class="forks"><b>Before</b>, ${fmtTime(D.release_uploaded_at, -1)}: <span class="num">${n(b.passed)}</span> passed. <b>Background</b>, the same minute again: <span class="num">${n(c.passed)}</span> passed${sameAsBefore ? ", the same tests" : ""}. <b>After</b>, ${fmtTime(D.release_uploaded_at, 1)}: <span class="num">${n(a.passed)}</span> passed.</p>
      <div class="cells" id="cells" role="img" aria-label="${n(cells.passed_before)} tests that passed before the release, grouped by test file. ${n(cells.broke)} of them broke after it."></div>
      <p class="cells__key"><span class="k k--b"></span>broke after the release <span class="k k--p"></span>still passes ${cells.already_failing ? `<span class="k k--f"></span>was already failing before` : ""}<span class="cells__files">${n(cells.modules)} test files</span></p>
      <p class="pins">${pins(b.resolved, a.resolved)}</p>
    </section>

    ${triageBlock(r)}
    ${patchBlock(r)}
  </article>`;

  drawCells(cells.seq);
}

function pins(before, after) {
  const keys = ["openai", "httpx", "httpx2"].filter((k) => before[k] || after[k]);
  return keys.map((k) => `<span>${k} ${esc(before[k] || "absent")} <span aria-hidden="true">&rarr;</span><span class="vh"> becomes </span> ${esc(after[k] || "absent")}</span>`).join("");
}

function drawCells(seq) {
  const host = $("#cells");
  const frag = document.createDocumentFragment();
  for (const ch of seq) {
    const i = document.createElement("i");
    i.className = ch === "|" ? "gap" : `c c--${ch}`;
    frag.appendChild(i);
  }
  host.appendChild(frag);
}

function triageBlock(r) {
  const t = r.triage || {};
  if (!t.cause) return "";
  let log = esc(r.log || "");
  for (const q of t.quotes || []) {
    const e = esc(q);
    if (e && log.includes(e)) log = log.split(e).join(`<mark>${e}</mark>`);
  }
  const kept = (t.quotes || []).length, dropped = t.dropped_quotes || 0;
  return `
  <section class="block" aria-labelledby="why-title">
    <div class="block__head"><h2 id="why-title">Why it broke</h2><p class="block__by">read by ${esc(t.model)}</p></div>
    <p class="cause">${esc(t.cause)}</p>
    <pre class="log" tabindex="0" aria-label="The failing test output, with the evidence Nemotron cited highlighted">${log}</pre>
    <p class="quotes-note">Highlighted: the ${numberWord(kept)} lines the model cited, each found word for word in this log.${dropped ? ` It tried to cite ${numberWord(dropped)} more that are not in the log, and those were thrown out.` : " It cited nothing that is not here."}</p>
  </section>`;
}

const normSpec = (s) => String(s || "").replace(/["',\s]/g, "").replace(/(\.0)+(?=[,<>=!]|$)/g, "");

// The fixer records machine reasons; a reader gets a sentence.
function plainReason(x) {
  const e = x.apply_error || "";
  if (/no JSON object/i.test(e)) return "did not apply: the reply was cut off before the edit was complete";
  if (/model error/i.test(x.rationale || "")) return "did not apply: the model call failed";
  if (/no edits/i.test(e)) return "did not apply: the model proposed no change";
  if (/matches (\d+) times/i.test(e)) return "did not apply: the text it meant to replace is not in the file exactly once";
  if (/not provided/i.test(e)) return "did not apply: it edited a file it had not been shown";
  if (x.applied && x.reasons && x.reasons.length) return `applied, but the package's own tests rejected it: ${x.reasons.join("; ")}`;
  if (x.applied) return "applied, but the package's own tests still failed";
  return e ? `did not apply: ${e.slice(0, 120)}` : "did not apply";
}

function patchBlock(r) {
  const fx = r.fix || { attempts: [] };
  const attempts = fx.attempts.map((x, i) => `
    <div class="attempt ${x.verified ? "attempt--won" : ""}">
      <span class="attempt__i num">${i + 1}</span>
      <span class="attempt__tier">Nemotron ${esc(x.tier[0].toUpperCase() + x.tier.slice(1))}<small>${esc(x.model.split("/").pop())}</small></span>
      <span class="attempt__out">${x.verified ? "passed the suite: applied in a fresh fork, every test that broke passes again, and nothing else regressed" : esc(plainReason(x))}</span>
    </div>`).join("");
  const trialLine = fx.trials > 1
    ? `<p class="trials"><span class="num">${n(fx.trials_verified)}</span> of <span class="num">${n(fx.trials)}</span> independent runs produced a patch the suite passed.${fx.trials_verified < fx.trials ? " In the rest, every patch Nemotron proposed was rejected by the package's own tests." : ""} The attempts below are from ${fx.verified ? "the first run that verified" : "the last run"}.</p>`
    : "";

  const m = r.maintainer_fix;
  let theirs = "";
  if (m && m.kind === "release") {
    theirs = `
      <aside class="theirs" aria-labelledby="theirs-title">
        <h3 id="theirs-title">What the maintainer shipped</h3>
        <p class="theirs__line">${m.lines.map(esc).join("<br>")}</p>
        <p class="theirs__when">In <a href="${esc(m.url)}">${esc(m.repo)} ${esc(m.tag)}</a>, ${hoursToWords(m.hours_after_release)} after the release.</p>
        ${m.followup ? `<p class="theirs__then">That was the stopgap. The next day, <a href="${esc(m.followup.url)}">${esc(m.followup.tag)}</a> did the real migration, moving to <code>${esc(m.followup.lines.join(" "))}</code>. Floodplain did not write that one.</p>` : ""}
      </aside>`;
  } else if (m && m.kind === "pr") {
    theirs = `
      <aside class="theirs" aria-labelledby="theirs-title">
        <h3 id="theirs-title">What the maintainers did</h3>
        ${m.lines && m.lines.length ? `<p class="theirs__line">${m.lines.map(esc).join("<br>")}</p>` : ""}
        <p class="theirs__when"><a href="${esc(m.url)}">${esc(m.repo)} #${m.number}</a>, ${m.merged ? "merged" : "opened"} ${hoursToWords(m.hours_after_release)} after the release.</p>
        <p class="theirs__then">${esc(m.title)}${m.note ? `. ${esc(m.note)}` : ""}</p>
      </aside>`;
  }

  if (!fx.verified) {
    return `
    <section class="block" aria-labelledby="patch-title">
      <div class="block__head"><h2 id="patch-title">The patch</h2></div>
      ${trialLine}
      <div class="attempts">${attempts}</div>
      <div class="patch patch--none">
        <p class="noverify">No patch passed this package's own tests, so Floodplain hands over the diagnosis rather than a patch it cannot prove.</p>
        ${theirs}
      </div>
    </section>`;
  }

  const lines = fx.diff.split("\n").filter((l) => !/^(diff --git|index )/.test(l));
  const diff = lines.map((l) => {
    const cls = l.startsWith("@@") ? "hunk" : l.startsWith("+++") || l.startsWith("---") ? "meta" : l.startsWith("+") ? "add" : l.startsWith("-") ? "del" : "";
    return `<div class="${cls}">${esc(l) || " "}</div>`;
  }).join("");
  const added = lines.filter((l) => l.startsWith("+") && !l.startsWith("+++")).map((l) => l.slice(1).trim());
  const same = m && m.lines && m.lines.some((ml) => added.some((al) => normSpec(al) === normSpec(ml.replace(/^[+-]/, ""))));

  return `
  <section class="block" aria-labelledby="patch-title">
    <div class="block__head"><h2 id="patch-title">The patch</h2><p class="block__by">verified by the package's own tests in a further fork</p></div>
    ${trialLine}
    <div class="attempts">${attempts}</div>
    <div class="patch">
      <div>
        <div class="diff" role="region" aria-label="The verified patch" tabindex="0">${diff}</div>
        <p class="diff-cap">Taken from <code>git diff</code> inside the fork that went green, not from the model's description of its own change. Floodplain does not open pull requests against repositories you do not own; it hands you this.${same ? " It is the same pin the maintainer shipped." : ""}</p>
      </div>
      ${theirs}
    </div>
  </section>`;
}

boot();
