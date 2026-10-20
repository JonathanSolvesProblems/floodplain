// Floodplain. Every figure rendered here is read from data.json, which build_site.py writes from
// the committed results. Nothing numeric is typed into this file (charter law 6).

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const n = (x) => (x ?? 0).toLocaleString("en-GB");
const SVG = "http://www.w3.org/2000/svg";

let DATA = null;

const fmtTime = (iso, deltaMin = 0) => {
  const d = new Date(new Date(iso).getTime() + deltaMin * 60000);
  return d.toISOString().slice(11, 16) + " UTC";
};
const fmtDate = (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const fmtDownloads = (x) => {
  if (!x) return "";
  if (x >= 1e6) return `${(x / 1e6).toFixed(x >= 1e7 ? 0 : 1)}M a month`;
  if (x >= 1e3) return `${Math.round(x / 1e3)}k a month`;
  return `${x} a month`;
};
const hoursToWords = (h) => {
  const d = Math.floor(h / 24), r = Math.round(h - d * 24);
  const words = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
  const dw = d <= 10 ? words[d] : String(d);
  return r ? `${dw} days and ${r} hours` : `${dw} days`;
};
const numberWord = (k) => (["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"][k] ?? String(k));

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
  $("#run-line").innerHTML =
    `<span class="powder" aria-hidden="true"></span>A dye trace of <b>${esc(DATA.target)} ${esc(DATA.release)}</b>, poured ${fmtDate(DATA.release_uploaded_at)}`;
  window.addEventListener("hashchange", route);
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

// ------------------------------------------------------------------ the trace
function renderTrace() {
  const D = DATA, S = D.states;
  const pos = D.receptors.filter((r) => r.state === "positive");
  const fixed = pos.filter((r) => r.maintainer_fix);
  const verified = pos.filter((r) => r.fix && r.fix.verified);
  document.title = `Floodplain: ${D.target} ${D.release}`;

  // Pair each positive with how long its own maintainers took, shortest first. The replay ran
  // weeks later, so the Nemotron sentence makes no timing claim: it says what the model wrote
  // from the failing log, not that it got there first.
  const link = (r) => `<a href="#/${encodeURIComponent(r.name)}">${esc(r.name)}</a>`;
  const byWait = [...fixed].sort((a, b) => a.maintainer_fix.hours_after_release - b.maintainer_fix.hours_after_release);
  const fixedSentence = byWait.length
    ? `Their own maintainers fixed them by hand: ${byWait.map((r) => `${link(r)} after ${numberWord(Math.floor(r.maintainer_fix.hours_after_release / 24))} days`).join(", ")}.`
    : "";
  const sameFix = verified.filter((r) => r.maintainer_fix && r.maintainer_fix.kind === "release");
  const verifiedSentence = sameFix.length
    ? ` For ${sameFix.map(link).join(" and ")}, NVIDIA Nemotron wrote the same patch the maintainer shipped, from the failing log alone, and the package's own tests passed it.`
    : verified.length ? ` NVIDIA Nemotron wrote a patch that the package's own tests passed for ${verified.map(link).join(" and ")}.` : "";

  $("#view").innerHTML = `
  <section class="trace" aria-labelledby="trace-title">
    <div class="trace__head">
      <p class="trace__kicker"><b>${esc(D.target)} ${esc(D.release)}</b> went in upstream at ${fmtTime(D.release_uploaded_at)} on ${fmtDate(D.release_uploaded_at)}</p>
      <h1 class="trace__title" id="trace-title"><span class="pour num">${n(S.positive)}</span> of ${n(D.readable)} readable packages broke</h1>
      <p class="trace__lede">I hung a receptor at <strong class="num">${n(D.ran)}</strong> of the <strong class="num">${n(D.population.exposed)}</strong> packages downstream that would take it, each one three forks of the same checkout on Nebius Sandboxes. Only <strong class="num">${n(D.readable)}</strong> could be read.</p>
    </div>
    <figure class="trace__art">
      <img src="art/positive.webp" width="660" height="854" alt="Watercolour of a charcoal receptor packet hanging from a cord over a dark stream, its lower third soaked fluorescent yellow-green and dripping into a green pool among the stones." fetchpriority="high">
      <figcaption>A positive: the receptor came back green.</figcaption>
    </figure>
    <div class="reach" id="reach"><div class="reach__tip" id="tip" hidden></div></div>
  </section>
  <div class="reach__key" aria-label="How to read the reach">
    ${keyItem("positive", "broke")}${keyItem("negative", "read clean")}${keyItem("no-baseline", "no working baseline")}${keyItem("no-tests", "no tests to read")}${keyItem("lost", "came back unreadable")}
  </div>
  ${fixedSentence || verifiedSentence ? `<p class="trace__after">${fixedSentence}${verifiedSentence}</p>` : ""}

  <section class="scene" aria-labelledby="method-title">
    <h2 class="scene__title" id="method-title">How a receptor is read</h2>
    <p class="scene__lede">Hydrogeologists find where water goes underground by pouring fluorescent dye in at one point and hanging charcoal packets at every spring downstream. Floodplain does the same thing to a package release.</p>
    <div class="method">
      <figure>
        <img src="art/injection.webp" width="644" height="800" loading="lazy" alt="Watercolour of a white funnel wedged between stones, holding a heap of dark rust-red dye powder, with a thin green trickle reaching the stream below.">
        <figcaption><b>Poured in</b><span>The release is the dye. Every package that depends on it and would resolve the new version gets one receptor.</span></figcaption>
      </figure>
      <figure>
        <img src="art/sample.webp" width="656" height="554" loading="lazy" alt="Watercolour of a corked glass bottle half full of plain grey stream water, standing on a stone.">
        <figcaption><b>A background sample</b><span>Each checkout is forked three ways at once: the world a minute before the release, the same again, and a minute after. A test that disagrees with itself across the two identical forks is natural fluorescence, and is thrown out.</span></figcaption>
      </figure>
      <figure>
        <img src="art/negative.webp" width="660" height="854" loading="lazy" alt="Watercolour of the same charcoal receptor packet hanging over the stream, wet and grey with no dye on it.">
        <figcaption><b>Read</b><span>A suite that passed before and fails after, against an unchanged background, is a positive. Nemotron reads the log, quoting only what is in it, and drafts a patch that the package's own tests have to pass.</span></figcaption>
      </figure>
    </div>
  </section>

  <section class="scene" aria-labelledby="ledger-title">
    <h2 class="scene__title" id="ledger-title">Every receptor I hung</h2>
    <p class="scene__lede">${n(D.population.total)} packages in the top ${n(D.scanned)} on PyPI declared ${esc(D.target)} on the day of the release. ${n(D.population.protected)} pinned below ${esc(D.release)} and were safe. Of the ${n(D.population.exposed)} that were not, these are the ${n(D.ran)} I could hang a receptor at.</p>
    <div class="ledger">${["positive", "negative", "no-baseline", "no-tests", "lost"].map(ledgerRow).join("")}</div>
  </section>`;

  drawReach();
}

function keyItem(state, label) {
  return `<span><svg viewBox="0 0 14 22" aria-hidden="true">${receptorGlyph(state, 7, 2, true)}</svg>${label}</span>`;
}

function ledgerRow(state) {
  const items = DATA.receptors.filter((r) => r.state === state);
  const names = items.map((r) => (state === "positive" ? `<a href="#/${encodeURIComponent(r.name)}">${esc(r.name)}</a>` : esc(r.name)));
  const list = names.length > 18
    ? `${names.slice(0, 18).join(", ")} <details><summary>and ${n(names.length - 18)} more</summary>${names.slice(18).join(", ")}</details>`
    : names.join(", ");
  return `
    <div class="ledger__row ledger__row--${state}">
      <p class="ledger__n num"><span>${n(items.length)}</span></p>
      <p class="ledger__state">${{ positive: "Positive", negative: "Negative", "no-baseline": "No working baseline", "no-tests": "No tests shipped", lost: "Unreadable" }[state]}<small>${esc(DATA.state_text[state])}</small></p>
      <div class="ledger__names">${list || "none"}</div>
    </div>`;
}

// One glyph per state: a cord and a packet. Shapes encode the state, so it never rests on colour.
function receptorGlyph(state, x, y, small = false) {
  const s = small ? 1 : 1;
  const cord = `<line class="cord" x1="${x}" y1="${y}" x2="${x}" y2="${y + 7 * s}"/>`;
  const bag = `<path class="bag" d="M${x - 4.5} ${y + 7} h9 l1.1 9.2 a2 2 0 0 1 -2 2.3 h-7.2 a2 2 0 0 1 -2 -2.3 z"/>`;
  if (state === "positive") {
    const dye = `<path class="bag-dye" d="M${x - 5.1} ${y + 12.4} h10.2 l.6 3.8 a2 2 0 0 1 -2 2.3 h-7.4 a2 2 0 0 1 -2 -2.3 z"/>`;
    return `<g class="rcp rcp--positive">${cord}${bag}${dye}</g>`;
  }
  return `<g class="rcp rcp--${state}">${cord}${bag}</g>`;
}

// ------------------------------------------------------------------ the reach
function drawReach() {
  const host = $("#reach");
  const W = 1200, H = 250, padL = 90, padR = 2;
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `A stream running left to right. The release is poured in at the left. ${DATA.ran} receptors hang along it, most downloaded first. ${DATA.states.positive} are poured green.`);

  // one meander, upstream at the left; a channel wash under a single line
  // ends low at the right edge, where the painting's own green pool sits: the reach runs into it
  const d = `M ${padL} 150 C 260 70, 360 210, 520 140 S 760 60, 880 140 S 1090 120, ${W - padR} 214`;
  svg.innerHTML = `<path class="stream" d="${d}"/><path class="stream-line" d="${d}" id="stream-path"/>`;
  host.prepend(svg);
  const path = $("#stream-path", svg);
  const L = path.getTotalLength();

  // injection point
  const p0 = path.getPointAtLength(0);
  svg.insertAdjacentHTML("beforeend", `
    <circle class="inject" cx="${p0.x}" cy="${p0.y}" r="7"/>
    <text class="inject-label" x="${p0.x - 6}" y="${p0.y + 30}">${esc(DATA.target)} ${esc(DATA.release)}</text>
    <text class="inject-sub" x="${p0.x - 6}" y="${p0.y + 46}">poured ${fmtTime(DATA.release_uploaded_at)}</text>`);

  const tip = $("#tip");
  const placed = [];
  const placedPos = [];
  const labelled = [];
  // non-positives first so the poured ones sit on top
  const order = [...DATA.receptors].sort((a, b) => (a.state === "positive") - (b.state === "positive"));
  for (const r of order) {
    const t = 0.05 + r.reach * 0.93;
    const pt = path.getPointAtLength(t * L);
    // Hang receptors on alternate banks and slide crowded ones sideways along the stream rather
    // than stacking them upward, so every packet stays on a bank instead of floating above it.
    const near = placed.filter((q) => Math.abs(q.x - pt.x) < 11).length;
    const side = near % 2 ? 1 : -1;
    // positives near an earlier positive slide downstream far enough that the two pools read
    // as two; position along the reach is a log-rank encoding, so a nudge does not change meaning
    const posNear = r.state === "positive" ? placedPos.filter((q) => Math.abs(q - pt.x) < 60).length : 0;
    const slide = r.state === "positive" ? posNear * 64 : Math.ceil(near / 2) * 7 * (near % 4 < 2 ? 1 : -1);
    if (r.state === "positive") placedPos.push(pt.x);
    const ptS = slide ? path.getPointAtLength(Math.min(Math.max(t * L + slide, 0), L)) : pt;
    const lift = r.state === "positive" ? -4 : 16 * side;
    const x = ptS.x, y = ptS.y + lift - 10;
    placed.push({ x: pt.x });

    const g = document.createElementNS(SVG, "g");
    g.innerHTML = receptorGlyph(r.state, x, y);
    const node = g.firstElementChild;
    node.setAttribute("tabindex", "0");
    node.setAttribute("role", r.state === "positive" ? "link" : "img");
    node.setAttribute("aria-label", `${r.name} ${r.version}: ${stateLabel(r.state)}`);
    if (r.state === "positive") {
      node.insertAdjacentHTML("afterbegin", `<ellipse class="pool" cx="${x}" cy="${y + 21}" rx="${16 + Math.min(r.newly_failing.length + r.new_collection_errors.length, 120) / 6}" ry="5.5"/>`);
      // labels near the mouth flip to the left so they never run off the reach; a positive that
      // lands near an earlier one takes the opposite bank, so the two labels never overlap
      const flip = x > W * 0.62;
      const crowded = labelled.some((q) => Math.abs(q - x) < 170);
      labelled.push(x);
      const lx = flip ? x - 18 : x + 18, ly = crowded ? y + 62 : y - 18, anchor = flip ? "end" : "start";
      node.insertAdjacentHTML("beforeend",
        `<text class="label" x="${lx}" y="${ly}" text-anchor="${anchor}">${esc(r.name)}</text>
         <text class="label-sub" x="${lx}" y="${ly + 16}" text-anchor="${anchor}">${n(r.newly_failing.length || r.new_collection_errors.length)} ${r.newly_failing.length ? "tests broke" : "modules could not import"}</text>`);
      node.addEventListener("click", () => (location.hash = `#/${encodeURIComponent(r.name)}`));
      node.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); location.hash = `#/${encodeURIComponent(r.name)}`; } });
    }
    const show = () => {
      const box = host.getBoundingClientRect(), sb = svg.getBoundingClientRect();
      tip.innerHTML = `<b>${esc(r.name)}</b> ${esc(r.version)}<br>${esc(r.state === "positive" ? DATA.state_text.positive : r.why || DATA.state_text[r.state])}`;
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

  // the dye pours once, when the reach comes into view
  const io = new IntersectionObserver((es) => {
    if (es.some((e) => e.isIntersecting)) { svg.classList.add("poured"); io.disconnect(); }
  }, { threshold: 0.35 });
  io.observe(svg);
}

function stateLabel(s) {
  return { positive: "broke, open the receptor", negative: "read clean", "no-baseline": "no working baseline", "no-tests": "no tests shipped", lost: "came back unreadable" }[s];
}

// ------------------------------------------------------------------ a receptor
function renderReceptor(r) {
  const D = DATA, b = r.before, c = r.control, a = r.after;
  const broke = r.newly_failing.length || r.new_collection_errors.length;
  const unit = r.newly_failing.length ? "tests" : "collection errors";
  document.title = `Floodplain: ${r.name} broke on ${D.target} ${D.release}`;

  const lede = r.newly_failing.length
    ? `<strong class="num">${n(broke)}</strong> of the <strong class="num">${n(b.passed)}</strong> tests that passed before ${esc(D.target)} ${esc(D.release)} fail after it.`
    : `The suite collected <strong class="num">${n(b.collected)}</strong> tests before ${esc(D.target)} ${esc(D.release)}. After it, it could not import: <strong class="num">${n(broke)}</strong> collection errors.`;
  const bg = r.flaky_excluded.length
    ? ` ${n(r.flaky_excluded.length)} tests disagreed with themselves across the identical forks and were thrown out.`
    : " The background sample read identical to the before, so none of this is a flaky test.";

  $("#view").innerHTML = `
  <article class="rcp-page" aria-labelledby="rcp-title">
    <div class="rcp-page__head">
      <div>
        <p class="crumb"><a href="#/">The trace</a>, receptor at rank ${n(r.rank)} on PyPI, ${esc(fmtDownloads(r.downloads))}</p>
        <h1 id="rcp-title">${esc(r.name)}<span class="ver">${esc(r.version)}</span></h1>
        <p class="rcp-page__lede">${lede}${bg}</p>
      </div>
      <img class="rcp-page__art" src="art/positive.webp" width="660" height="854" alt="Watercolour of a charcoal receptor packet soaked fluorescent yellow-green, dripping into a green pool.">
    </div>

    <div class="samples">
      ${sampleCol("Before", "the world one minute before", fmtTime(D.release_uploaded_at, -1), b, null)}
      ${sampleCol("Background", "the same minute, again", fmtTime(D.release_uploaded_at, -1), c, null)}
      ${sampleCol("After", "the world one minute after", fmtTime(D.release_uploaded_at, 1), a, { n: broke, unit })}
    </div>

    ${triageBlock(r)}
    ${patchBlock(r)}
  </article>`;
}

function sampleCol(name, desc, when, arm, broke) {
  const res = arm.resolved || {};
  const show = ["openai", "httpx", "httpx2"].map((k) => (res[k]
    ? `<div>${k}==${esc(res[k])}</div>`
    : (k === "httpx" ? `<div class="gone">httpx not installed</div>` : ""))).join("");
  return `
    <section class="sample" aria-label="${name} fork">
      <p class="sample__name">${name}</p>
      <p class="sample__when">${when}, ${desc}</p>
      <p class="sample__n num">${n(arm.passed)}<span class="sample__n-unit">passed</span></p>
      ${broke ? `<p class="sample__broke"><span class="num">${n(broke.n)}</span> ${broke.unit} broke</p>` : `<p class="sample__broke" aria-hidden="true">&nbsp;</p>`}
      <div class="sample__deps">${show}</div>
    </section>`;
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
    <div class="block__head"><h2 id="why-title">Why it broke</h2><p class="block__by">read by <b>${esc(t.model)}</b></p></div>
    <p class="cause">${esc(t.cause)}</p>
    <pre class="log" tabindex="0" aria-label="The failing test output, with the evidence Nemotron cited highlighted">${log}</pre>
    <p class="quotes-note">Highlighted: the ${numberWord(kept)} lines the model cited, each found word for word in this log.${dropped ? ` It tried to cite ${numberWord(dropped)} more that are not in the log, and those were thrown out.` : " It cited nothing that is not here."}</p>
  </section>`;
}

const normSpec = (s) => String(s || "").replace(/["',\s]/g, "").replace(/(\.0)+(?=[,<>=!]|$)/g, "");

function patchBlock(r) {
  const fx = r.fix || { attempts: [] };
  const attempts = fx.attempts.map((x, i) => `
    <div class="attempt ${x.verified ? "attempt--won" : ""}">
      <span class="attempt__i num">${i + 1}</span>
      <span class="attempt__tier">Nemotron ${esc(x.tier[0].toUpperCase() + x.tier.slice(1))}<small>${esc(x.model.split("/").pop())}</small></span>
      <span class="attempt__out">${x.verified
        ? `<b>passed the suite</b>, applied in a fresh fork and every test that broke now passes, with nothing else regressing`
        : x.applied ? "applied, but the suite still failed" : `did not apply: ${esc(x.apply_error || "no edit returned")}`}</span>
    </div>`).join("");

  if (!fx.verified) {
    return `
    <section class="block" aria-labelledby="patch-title">
      <div class="block__head"><h2 id="patch-title">The patch</h2></div>
      <div class="attempts">${attempts}</div>
      <p class="noverify">No patch passed this package's own tests, so Floodplain hands over the diagnosis instead of a patch it cannot prove.</p>
    </section>`;
  }

  const lines = fx.diff.split("\n").filter((l) => !/^(diff --git|index )/.test(l));
  const diff = lines.map((l) => {
    const cls = l.startsWith("@@") ? "hunk" : l.startsWith("+++") || l.startsWith("---") ? "meta" : l.startsWith("+") ? "add" : l.startsWith("-") ? "del" : "";
    return `<div class="${cls}">${esc(l) || " "}</div>`;
  }).join("");

  const added = lines.filter((l) => l.startsWith("+") && !l.startsWith("+++")).map((l) => l.slice(1).trim());
  const m = r.maintainer_fix;
  let theirs = "";
  if (m && m.kind === "release") {
    const same = m.lines.some((ml) => added.some((al) => normSpec(al) === normSpec(ml)));
    theirs = `
      <aside class="theirs" aria-labelledby="theirs-title">
        <h3 id="theirs-title">What the maintainer shipped</h3>
        <p class="theirs__line">${m.lines.map(esc).join("<br>")}</p>
        <p class="theirs__when">In <a href="${esc(m.url)}">${esc(m.repo)} ${esc(m.tag)}</a>, <b>${hoursToWords(m.hours_after_release)}</b> after the release.</p>
        ${same ? `<p class="match">The same pin, written independently.</p>` : ""}
        ${m.followup ? `<p class="theirs__then">This is the stopgap. The next day, <a href="${esc(m.followup.url)}">${esc(m.followup.tag)}</a> did the real migration, moving to <code>${esc(m.followup.lines.join(" "))}</code>. Floodplain did not write that one.</p>` : ""}
      </aside>`;
  } else if (m && m.kind === "pr") {
    theirs = `
      <aside class="theirs" aria-labelledby="theirs-title">
        <h3 id="theirs-title">What the maintainers did</h3>
        <p class="theirs__when"><a href="${esc(m.url)}">${esc(m.repo)}#${m.number}</a>, ${m.merged ? "merged" : "opened"} <b>${hoursToWords(m.hours_after_release)}</b> after the release.</p>
        <p class="theirs__then">${esc(m.title)}</p>
      </aside>`;
  }

  return `
  <section class="block" aria-labelledby="patch-title">
    <div class="block__head"><h2 id="patch-title">The patch</h2><p class="block__by">verified by the package's own tests in a further fork</p></div>
    <div class="attempts">${attempts}</div>
    <div class="patch">
      <div>
        <div class="diff" role="region" aria-label="The verified patch" tabindex="0">${diff}</div>
        <p class="diff-cap">Taken from <code>git diff</code> inside the fork that went green, not from the model's description of its own change. Floodplain does not open pull requests against repositories you do not own; it hands you this.</p>
      </div>
      ${theirs}
    </div>
  </section>`;
}

boot();
