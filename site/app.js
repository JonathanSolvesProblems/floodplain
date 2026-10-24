// Floodplain. Every figure rendered here is read from data.json, which build_site.py writes from
// the committed results. Nothing numeric is typed into this file (charter law 6).

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const n = (x) => (x ?? 0).toLocaleString("en-GB");
const SVG = "http://www.w3.org/2000/svg";

let DATA = null;

const fmtTime = (iso, deltaMin = 0) => new Date(new Date(iso).getTime() + deltaMin * 60000).toISOString().slice(11, 16) + " UTC";
const fmtDate = (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const fmtDownloads = (x) => (!x ? "" : x >= 1e6 ? `${(x / 1e6).toFixed(x >= 1e7 ? 0 : 1)} million downloads a month`
  : x >= 1e3 ? `${Math.round(x / 1e3)} thousand downloads a month` : `${x} downloads a month`);
const WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
  "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"];
const numberWord = (k) => WORDS[k] ?? String(k);
const daysAfter = (h) => numberWord(Math.floor(h / 24));
const andList = (xs) => (xs.length > 1 ? `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}` : xs.join(""));
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
  const unread = S["no-baseline"] + S["no-tests"] + S.lost + (S["held-back"] || 0);
  document.title = `Floodplain: ${D.target} ${D.release}`;

  // Each positive paired with how long its own maintainers took. The replay ran weeks later, so
  // the Nemotron sentence makes no timing claim: it says what the model wrote, not that it got
  // there first, and it carries its K of N.
  const byWait = pos.filter((r) => r.maintainer_fix).sort((a, b) => a.maintainer_fix.hours_after_release - b.maintainer_fix.hours_after_release);
  const fixedSentence = byWait.length
    ? `Each was later pinned or patched by its own maintainers: ${byWait.map((r) => `${link(r)} after ${daysAfter(r.maintainer_fix.hours_after_release)} days`).join(", ")}.`
    : "";
  // The sentence quotes the newest fixer revision's round for each package, as K of N, and says
  // how many of the verified patches were the maintainer's own change, counted from the diffs.
  // The newest round that produced a verified patch, as the GitHub report hands over.
  const latest = (r) => {
    const rs = (r.fix && r.fix.rounds) || [];
    return [...rs].reverse().find((rd) => rd.k > 0) || rs[rs.length - 1] || null;
  };
  const withPatch = pos.filter((r) => latest(r) && latest(r).k > 0);
  const kOfN = (rd) => `${numberWord(rd.k)} of ${numberWord(rd.n)} ${rd.agent ? "agent runs" : "runs of the scripted fixer"}`;
  const same = withPatch.filter((r) => latest(r).same_as_maintainer > 0);
  const verifiedSentence = withPatch.length
    ? ` NVIDIA Nemotron wrote a patch the package's own tests passed, in a further fork, for ${andList(withPatch.map((r) => `${link(r)} in ${kOfN(latest(r))}`))}.` +
      same.map((r) => ` For ${link(r)}, ${numberWord(latest(r).same_as_maintainer)} of those ${latest(r).same_as_maintainer === 1 ? "was" : "were"} the same change its maintainer shipped.`).join("")
    : "";

  // The pre-release check: the same dependents, with the release given as an unpublished wheel
  // against the index a minute before the upload. Said only if every verdict matched.
  const cand = D.candidate ? Object.values(D.candidate)[0] : null;
  const candSentence = cand && cand.agree_with_replay === cand.run
    ? `<p class="trace__after">I then ran it the way it is meant to be used, before the release: ${esc(D.target)}'s own ${esc(D.release)} wheel as an unpublished file, against the index at ${fmtTime(cand.as_of)}, a minute before it was uploaded. All <span class="num">${n(cand.run)}</span> working suites gave the same verdict as the replay${cand.same_broken_tests === cand.run ? ", with the same tests broken" : ""}.</p>`
    : "";

  // Still watching: every release since, checked by the scheduled job and reported as an issue.
  const W = D.watch;
  const watchBlock = W && W.checked.length ? `
  <section class="scene watch" aria-labelledby="watch-title">
    <h2 class="scene__title" id="watch-title">Still watching</h2>
    <p class="scene__lede">Every day a scheduled job checks PyPI for ${esc(D.target)} releases it has not seen and runs them against the <span class="num">${n(W.watched)}</span> dependents whose suites gave a reading on ${esc(W.base)}. Each result is an issue in the repository.</p>
    <ul class="watch__list">${W.checked.map((c) => `<li><span class="num">${esc(c.release)}</span> ${c.issue ? `<a href="${esc(c.issue)}">${esc(c.headline.replace(/^\S+ \S+: /, ""))}</a>` : esc(c.headline.replace(/^\S+ \S+: /, ""))}</li>`).join("")}</ul>
  </section>` : "";

  $("#view").innerHTML = `
  <section class="trace" aria-labelledby="trace-title">
    <div class="trace__head">
      <h1 class="trace__title" id="trace-title">${n(S.positive)} of the ${n(D.readable)} working test suites that took ${esc(D.target)}&nbsp;${esc(D.release)} broke</h1>
      <p class="trace__lede">It went in upstream at ${fmtTime(D.release_uploaded_at)} on ${fmtDate(D.release_uploaded_at)}. I hung a receptor at <span class="num">${n(D.ran)}</span> of the <span class="num">${n(D.population.exposed)}</span> packages downstream that would take it, three forks of one checkout each, on Nebius Sandboxes.</p>
    </div>
    <div class="reach" id="reach"><div class="reach__tip" id="tip" hidden></div></div>
    <p class="reach__note">Each small packet is a package whose tests passed before the release and still passed after. Another <span class="num">${n(unread)}</span> could not be read and are not drawn: no tests shipped, nothing passing before the release either, a run that did not finish, or another package that held the old version so the release never arrived. All of them are listed below.</p>
  </section>
  ${fixedSentence || verifiedSentence ? `<p class="trace__after">${fixedSentence}${verifiedSentence}</p>` : ""}
  ${candSentence}

  <section class="scene method" aria-labelledby="method-title">
    <div class="method__text">
      <h2 class="scene__title" id="method-title">How a receptor is read</h2>
      <p>Hydrogeologists find out where water goes underground by pouring fluorescent dye in at one point and hanging charcoal packets at every spring downstream. Weeks later they read the packets. Floodplain does the same thing to a package release.</p>
      <p><b>Poured in.</b> The release is the dye. Every package that depends on it, and would resolve the new version, gets one receptor.</p>
      <p><b>A background sample.</b> Before dye goes in, hydrogeologists take a sample of the plain water, so natural fluorescence is never mistaken for dye. Here each checkout is forked three ways at once: the world a minute before the release, the same again, and a minute after. A test that disagrees with itself across the two identical forks is natural fluorescence, and is thrown out.</p>
      <p><b>Read.</b> A suite that passed before and fails after, against an unchanged background, is a positive. NVIDIA Nemotron reads the log, quoting only lines that are in it, and drafts a patch that the package's own tests have to pass.</p>
    </div>
    <div class="method__art">${methodDiagram()}</div>
  </section>

  ${watchBlock}

  <section class="scene" aria-labelledby="ledger-title">
    <h2 class="scene__title" id="ledger-title">Every receptor I hung</h2>
    <p class="scene__lede"><span class="num">${n(D.population.total)}</span> packages in the top <span class="num">${n(D.scanned)}</span> on PyPI declared ${esc(D.target)} on the day of the release. <span class="num">${n(D.population.protected)}</span> pinned below ${esc(D.release)} and were never exposed. Of the <span class="num">${n(D.population.exposed)}</span> that were, these are the <span class="num">${n(D.ran)}</span> I could hang a receptor at, one packet each.</p>
    <div class="strip">${["positive", "negative", "held-back", "no-baseline", "no-tests", "lost"].map(stripGroup).join("")}</div>
  </section>`;

  // labels are placed by measured width, so wait for the real typeface before drawing
  document.fonts.ready.then(() => drawReach(innerWidth < 640));
}

// The accounting in the river's own glyph: one packet per receptor, grouped by what it read.
function stripGroup(state) {
  const items = DATA.receptors.filter((r) => r.state === state);
  const label = { positive: "broke", negative: "read clean", "held-back": "held back", "no-baseline": "no working baseline", "no-tests": "no tests shipped", lost: "unreadable" }[state];
  const glyphs = items.map((r) => `<svg class="pk" viewBox="0 0 14 22" role="img" aria-label="${esc(r.name)}">${receptorGlyph(state, 7, 2)}</svg>`).join("");
  const names = items.map((r) => (state === "positive" ? link(r) : esc(r.name))).join(", ");
  return `
    <div class="strip__group strip__group--${state}">
      <p class="strip__n num">${n(items.length)}</p>
      <p class="strip__label">${label}</p>
      <div class="strip__packets">${glyphs}</div>
      <p class="strip__why">${esc(DATA.state_text[state])}</p>
      ${state === "positive" ? `<p class="strip__names">${names}</p>` : `<details class="strip__names"><summary>Show the ${n(items.length)}</summary>${names}</details>`}
    </div>`;
}

// The method as a schematic in the same glyphs as the river: the release poured in, one
// checkout forked three ways, and the three packets read.
function methodDiagram() {
  const D = DATA;
  const t = (dm) => fmtTime(D.release_uploaded_at, dm);
  const arm = (y, name, when, state) => `
    <path class="fork" d="M 196 120 C 250 120, 250 ${y}, 304 ${y}"/>
    <g transform="translate(0 0)">${receptorGlyph(state, 322, y - 14)}</g>
    <text class="d-label" x="342" y="${y - 2}">${name}</text>
    <text class="d-sub" x="342" y="${y + 15}">${when}</text>`;
  return `
  <svg class="diagram" viewBox="0 0 520 250" role="img" aria-label="The release poured into one checkout, which forks into three sandboxes: before, background and after. Before and background read clean; after reads positive.">
    <circle class="d-inject" cx="22" cy="120" r="7"/>
    <text class="d-label" x="10" y="150">${esc(D.target)} ${esc(D.release)}</text>
    <text class="d-sub" x="10" y="167">poured in</text>
    <path class="fork" d="M 30 120 L 150 120"/>
    <rect class="d-box" x="150" y="104" width="46" height="32" rx="3"/>
    <text class="d-sub" x="150" y="94">one checkout</text>
    ${arm(48, "before", `the world at ${t(-1)}`, "negative")}
    ${arm(120, "background", `the same minute again`, "negative")}
    ${arm(192, "after", `the world at ${t(1)}`, "positive")}
  </svg>`;
}

// ------------------------------------------------------------------ the reach
// Horizontal on a wide screen, vertical on a phone, so the river runs down the page instead of
// shrinking into a strip. Readable receptors are drawn; the unreadable are one faint texture.
function drawReach(vertical) {
  const host = $("#reach");
  host.classList.toggle("reach--v", vertical);
  // Wide: the river runs low under the headline, then rises into the open right half of the
  // first screen and comes back down to its mouth inside the frame.
  const W = vertical ? 360 : 1200, H = vertical ? 680 : 430;
  const d = vertical
    ? `M 110 26 C 250 110, 40 190, 170 290 S 320 410, 160 500 S 60 600, 180 ${H - 24}`
    : `M 60 380 C 260 300, 400 420, 590 340 S 760 110, 920 115 S 1110 210, 1150 330`;
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `A river with the release poured in at its source. ${DATA.ran} receptors hang along it, most downloaded first. ${DATA.states.positive} came back green.`);
  svg.innerHTML = `<path d="${d}" id="stream-path" fill="none" stroke="none"/>`;
  host.prepend(svg);
  const path = $("#stream-path", svg);
  const L = path.getTotalLength();

  // One ribbon whose width grows downstream, the way a river gathers water: a filled outline
  // offset either side of the centre path. ribbon(a, b) draws any stretch of it, so a positive
  // can turn its own stretch of river green: the dye showing where the receptor caught it.
  const widthAt = (len) => 2.5 + 15 * Math.pow(len / L, 0.8);
  const ribbon = (from, to, steps = 160) => {
    const left = [], right = [];
    for (let s = 0; s <= steps; s++) {
      const len = from + ((to - from) * s) / steps, p = path.getPointAtLength(len);
      const a = path.getPointAtLength(Math.max(len - 1, 0)), b = path.getPointAtLength(Math.min(len + 1, L));
      const dx = b.x - a.x, dy = b.y - a.y, m = Math.hypot(dx, dy) || 1, w = widthAt(len);
      left.push(`${(p.x - (dy / m) * w).toFixed(1)},${(p.y + (dx / m) * w).toFixed(1)}`);
      right.push(`${(p.x + (dy / m) * w).toFixed(1)},${(p.y - (dx / m) * w).toFixed(1)}`);
    }
    return `M ${left.join(" L ")} L ${right.reverse().join(" L ")} Z`;
  };
  svg.insertAdjacentHTML("afterbegin", `<path class="river" d="${ribbon(0, L)}"/>`);

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
  const marks = [];
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

    // The unreadable are counted in the note and the ledger, not drawn: on the river they were
    // only noise. What is drawn is what could actually be read.
    if (r.state === "no-baseline" || r.state === "no-tests" || r.state === "lost" || r.state === "held-back") continue;

    const off = r.state === "positive" ? 0 : 28 * bank;
    const x = pt.x + nx * off, y = pt.y + ny * off - (r.state === "positive" ? 12 : 12);
    const g = document.createElementNS(SVG, "g");
    g.innerHTML = receptorGlyph(r.state, x, y);
    const node = g.firstElementChild;
    if (r.state !== "positive") marks.push({ x: x - 7, y: y - 2, w: 14, h: 22 });
    node.setAttribute("tabindex", "0");
    node.setAttribute("role", r.state === "positive" ? "link" : "img");
    node.setAttribute("aria-label", `${r.name} ${r.version}: ${r.state === "positive" ? "broke, open the receptor" : "read clean"}`);

    if (r.state === "positive") {
      const broke = r.cells ? r.cells.broke : (r.newly_failing.length || r.new_collection_errors.length);
      // the river runs green over a stretch whose length grows with how much broke
      const half = 16 + Math.min(broke, 120) / 4;
      svg.querySelector(".river").insertAdjacentHTML("afterend",
        `<path class="dye-run" d="${ribbon(Math.max(len - half, 0), Math.min(len + half, L), 24)}"/>`);
      pools.push({ r, x, y: y + 18, broke, node });
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

  // The headline overlaps the top of the river on a wide screen; labels must stay clear of it.
  const obstacles = [];
  const head = $(".trace__head");
  if (head && !vertical) {
    const sb = svg.getBoundingClientRect(), hb = head.getBoundingClientRect(), k = W / sb.width;
    obstacles.push({ x: (hb.left - sb.left) * k, y: (hb.top - sb.top) * k, w: hb.width * k, h: hb.height * k + 10 });
  }
  labelPools(pools, vertical, W, H, obstacles, marks);

  const io = new IntersectionObserver((es) => {
    if (es.some((e) => e.isIntersecting)) { svg.classList.add("poured"); io.disconnect(); }
  }, { threshold: 0.3 });
  io.observe(svg);
}

// Each name set directly beside its own pool. Candidate spots are tried in order around the
// pool; the first whose measured box clears every label already placed, every pool and the
// frame is taken. Real data puts positives close together, so fixed alternation cannot work.
// A spot that also clears every clean packet is preferred; the halo only covers for the rest.
function labelPools(pools, vertical, W, H, obstacles = [], marks = []) {
  const placed = [...obstacles];
  const poolBoxes = pools.map((p) => ({ x: p.x - 34, y: p.y - 30, w: 68, h: 40 }));
  const hits = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
  [...pools].sort((a, b) => a.x - b.x).forEach((p) => {
    const fixed = p.r.maintainer_fix ? `, fixed after ${daysAfter(p.r.maintainer_fix.hours_after_release)} days` : "";
    const sub = `${n(p.broke)} tests broke${fixed}`;
    const g = document.createElementNS(SVG, "g");
    g.innerHTML = `<text class="label" text-anchor="start"><tspan class="label-n">${n(p.broke)}</tspan> ${esc(p.r.name)}</text><text class="label-sub" text-anchor="start">${sub.replace(/^[\d,]+ /, "")}</text>`;
    p.node.appendChild(g);
    const [t1, t2] = g.children;
    const gap = vertical ? 20 : 26;
    const w = Math.max(t1.getComputedTextLength(), t2.getComputedTextLength());
    // from the large numeral's cap height above the first baseline to the subtitle's descenders
    const top = 24, h = top + gap + 7;
    const dx = 26, up = vertical ? 30 : 46, down = vertical ? 30 : 34;
    const spots = [
      [p.x + dx, p.y - up], [p.x - dx - w, p.y - up], [p.x + dx, p.y + down], [p.x - dx - w, p.y + down],
      [p.x + dx, p.y - up - 52], [p.x - dx - w, p.y - up - 52], [p.x + dx, p.y + down + 52], [p.x - dx - w, p.y + down + 52],
      [p.x - w / 2, p.y + down + 26], [p.x - w / 2, p.y - up - 26], [p.x - w * 0.75, p.y + down + 52],
      [p.x - dx - w, p.y + down + 104], [p.x - w / 2, p.y + down + 104],
      // a long name on a narrow river: set it flush with the frame edge, under or over the pool
      [8, p.y + down], [8, p.y - up], [W - 8 - w, p.y + down], [W - 8 - w, p.y - up],
    ];
    let pick = null;
    for (const avoidMarks of [true, false]) {
      for (const [sx, sy] of spots) {
        const box = { x: sx - 4, y: sy - top, w: w + 8, h };
        const inFrame = box.x >= 2 && box.x + box.w <= W - 2 && box.y >= 0 && box.y + box.h <= H;
        if (inFrame && !placed.some((q) => hits(box, q)) && !poolBoxes.some((q) => hits(box, q))
            && !(avoidMarks && marks.some((q) => hits(box, q)))) { pick = [sx, sy]; break; }
      }
      if (pick) break;
    }
    // A name too long for a narrow river fits nowhere at full size: set it flush left under the
    // pool and scale it down to the frame rather than letting it run off the edge.
    let scale = 1;
    if (!pick) {
      pick = [8, p.y + down];
      scale = Math.min(1, (W - 16) / w);
      g.setAttribute("transform", `translate(${pick[0]} ${pick[1]}) scale(${scale.toFixed(3)}) translate(${-pick[0]} ${-pick[1]})`);
    }
    // Map practice: a label left of its point is set flush right, so the name ends at its own pool
    // rather than starting next to a neighbour's.
    const leftOf = scale === 1 && pick[0] + w <= p.x;
    const tx = leftOf ? pick[0] + w : pick[0];
    for (const t of [t1, t2]) { t.setAttribute("x", tx); t.setAttribute("text-anchor", leftOf ? "end" : "start"); }
    t1.setAttribute("y", pick[1]); t2.setAttribute("y", pick[1] + gap);
    const lb = { x: pick[0] - 4, y: pick[1] - top * scale, w: w * scale + 8, h: h * scale };
    placed.push(lb);
    // A leader from the pool to the nearest edge of its label, so a label that had to sit beside
    // a neighbour's pool still reads as its own.
    const cx = p.x, cy = p.y - 6;
    const ex = Math.max(lb.x, Math.min(cx, lb.x + lb.w)), ey = Math.max(lb.y, Math.min(cy, lb.y + lb.h));
    const dist = Math.hypot(ex - cx, ey - cy);
    if (dist > 18) {
      const k = (dist - 4) / dist, s = 12 / dist;
      g.insertAdjacentHTML("afterbegin", `<line class="leader" x1="${(cx + (ex - cx) * s).toFixed(1)}" y1="${(cy + (ey - cy) * s).toFixed(1)}" x2="${(cx + (ex - cx) * k).toFixed(1)}" y2="${(cy + (ey - cy) * k).toFixed(1)}"/>`);
    }
  });
}

const rankOf = (s) => ({ "no-baseline": 0, "no-tests": 0, lost: 0, "held-back": 0, negative: 1, positive: 2 }[s]);

// A cord and a packet. Shape carries the state, so it never rests on colour alone.
function receptorGlyph(state, x, y) {
  const cord = `<line class="cord" x1="${x}" y1="${y}" x2="${x}" y2="${y + 7}"/>`;
  const bag = `<path class="bag" d="M${x - 4.5} ${y + 7} h9 l1.1 9.2 a2 2 0 0 1 -2 2.3 h-7.2 a2 2 0 0 1 -2 -2.3 z"/>`;
  if (state === "positive") {
    const dye = `<path class="bag-dye" d="M${x - 5.1} ${y + 12.4} h10.2 l.6 3.8 a2 2 0 0 1 -2 2.3 h-7.4 a2 2 0 0 1 -2 -2.3 z"/>`;
    return `<g class="rcp rcp--positive">${cord}${bag}${dye}</g>`;
  }
  const weir = state === "held-back" ? `<line class="weir" x1="${x - 4}" y1="${y + 3.5}" x2="${x + 4}" y2="${y + 3.5}"/>` : "";
  return `<g class="rcp rcp--${state}">${cord}${weir}${bag}</g>`;
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
      <h1 id="rcp-title">${esc(r.name)}<span class="ver">${esc(r.version)}</span></h1>
      <p class="rcp-page__lede">${lede}${bg} Rank ${n(r.rank)} on PyPI, ${esc(fmtDownloads(r.downloads))}.</p>
    </div>

    <section class="sample-sheet" aria-label="The three forks">
      <p class="forks"><b>Before</b>, ${fmtTime(D.release_uploaded_at, -1)}: <span class="num">${n(b.passed)}</span> passed. <b>Background</b>, the same minute again: <span class="num">${n(c.passed)}</span> passed${sameAsBefore ? ", the same tests" : ""}. <b>After</b>, ${fmtTime(D.release_uploaded_at, 1)}: <span class="num">${n(a.passed)}</span> passed.</p>
      <p class="cells__lead">The breaks sit in <span class="num">${n(cells.files_hit)}</span> of its <span class="num">${n(cells.files)}</span> test files. One square per test.</p>
      <div class="cells" role="img" aria-label="${n(cells.broke)} broken tests across ${n(cells.files_hit)} of ${n(cells.files)} test files.">
        ${cells.hit.map((h) => fileRow(h.file, h.codes)).join("")}
      </div>
      ${cells.quiet.files ? `<p class="file__rest">The other ${numberWord(cells.quiet.files)} test ${cells.quiet.files === 1 ? "file" : "files"}: all <span class="num">${n(cells.quiet.codes.replace(/f/g, "").length)}</span> tests still pass.</p>` : ""}
      <p class="cells__key"><span class="k k--b"></span>broke after the release <span class="k k--p"></span>still passes ${cells.already_failing ? `<span class="k k--f"></span>was already failing before` : ""}</p>
      <p class="pins">${pins(b.resolved, a.resolved)}</p>

    </section>

    ${triageBlock(r)}
    ${patchBlock(r)}
  </article>`;

}

function fileRow(label, codes, quiet = false) {
  const b = (codes.match(/b/g) || []).length;
  const squares = [...codes].map((c) => `<i class="c c--${c}"></i>`).join("");
  return `<div class="file ${quiet ? "file--quiet" : ""}"><span class="file__name">${esc(label)}</span><span class="file__n num">${b ? `${n(b)} of ${n(codes.replace(/f/g, "").length)}` : n(codes.replace(/f/g, "").length)}</span><span class="file__cells">${squares}</span></div>`;
}

// What the resolver changed between the before and after forks, said as a sentence.
function pins(before, after) {
  const changed = ["openai", "httpx", "httpx2"].filter((k) => (before[k] || "") !== (after[k] || ""));
  if (!changed.length) return "";
  const phrase = (k) => !before[k] ? `added <code>${k} ${esc(after[k])}</code>`
    : !after[k] ? `dropped <code>${k}</code>` : `moved <code>${k}</code> from ${esc(before[k])} to ${esc(after[k])}`;
  const parts = changed.map(phrase);
  const list = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}` : parts[0];
  return `Between the two, a fresh install ${list}. The package's own code was the same in both.`;
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
  const cited = kept === 1 ? "the one line the model cited, found word for word" : `the ${numberWord(kept)} lines the model cited, each found word for word`;
  const thrown = dropped === 1 ? " It tried to cite one more line that is not in the log, and that was thrown out."
    : dropped ? ` It tried to cite ${numberWord(dropped)} more lines that are not in the log, and those were thrown out.` : " It cited nothing that is not here.";
  return `
  <section class="block" aria-labelledby="why-title">
    <div class="block__head"><h2 id="why-title">Why it broke</h2><p class="block__by">read by ${esc(t.model)}</p></div>
    <p class="cause">${esc(t.cause)}</p>
    <pre class="log" tabindex="0" aria-label="The failing test output, with the evidence Nemotron cited highlighted">${log}</pre>
    <p class="quotes-note">Highlighted: ${cited} in this log.${thrown}</p>
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
  // One sentence per round. Rounds differ in fixer revision or guidance and are never pooled; a
  // run whose edits never applied is told apart from one whose patch the suite rejected.
  const roundLine = (rd) => {
    const misses = rd.n - rd.k;
    const why = misses === 1
      ? (rd.never_applied ? " The other never produced an edit that applied to the file."
        : rd.out_of_steps ? " The other ran out of steps without submitting." : " The other was rejected by the package's own tests.")
      : misses
      ? ` Of the ${numberWord(misses)} that did not, ${andList([
          rd.never_applied ? `${numberWord(rd.never_applied)} never produced an edit that applied to the file` : "",
          rd.rejected ? `${numberWord(rd.rejected)} ${rd.rejected === 1 ? "was" : "were"} rejected by the package's own tests` : "",
          rd.out_of_steps ? `${numberWord(rd.out_of_steps)} ran out of steps without submitting` : "",
        ].filter(Boolean))}.`
      : "";
    const sameAs = rd.same_as_maintainer ? `, ${numberWord(rd.same_as_maintainer)} with the change its maintainer shipped` : "";
    const fell = rd.fell_back && rd === rounds.find((x) => x.fell_back) ? " (Tavily found nothing dated before the maintainers acted that did not name the package, so it fell back to that guide)" : "";
    const who = rd.agent ? `The agent, revision ${rd.revision}` : `The scripted fixer, revision ${rd.revision}`;
    return `<li>${who}, given ${esc(rd.guidance)}${fell}: <span class="num">${n(rd.k)}</span> of <span class="num">${n(rd.n)}</span> runs passed the suite${sameAs}.${why}</li>`;
  };
  // The agent's own decisions, in order: each step is a tool Nemotron chose after reading the
  // previous result. Shown verbatim and short, never summarised.
  const argOf = (s) => {
    const a = s.args || {};
    if (s.tool === "read_file") return `${a.path || ""}${a.start ? ` ${a.start}-${a.end || ""}` : ""}`;
    if (s.tool === "search" || s.tool === "list_files") return a.pattern || "";
    if (s.tool === "run_tests") return a.targets || "";
    if (s.tool === "edit_file") return a.path || "";
    return a.rationale || a.reason || "";
  };
  const firstLine = (t) => String(t || "").split("\n").find((l) => l.trim()) || "";
  const stepsBlock = fx.agent && fx.steps && fx.steps.length ? `
    <details class="agent-steps" open>
      <summary>${fx.steps[0].tool === "draft_patch" && /first draft/.test((fx.steps[0].args || {}).notes || "")
        ? `A first draft, then the <span class="num">${n(fx.steps.length - 1)}</span> steps the agent chose, each from what the previous one returned`
        : `The <span class="num">${n(fx.steps.length)}</span> steps of the run below, each chosen by Nemotron from what the previous one returned`}</summary>
      <ol>${fx.steps.map((s) => `<li><code class="agent-steps__tool">${esc(s.tool)}</code> <code>${esc(argOf(s).slice(0, 90))}</code><span class="agent-steps__out">${esc(firstLine(s.result).slice(0, 140))}</span></li>`).join("")}</ol>
    </details>` : "";
  const rounds = fx.rounds || [];
  const trialLine = rounds.length
    ? `<div class="trials"><p>Every run is independent, so one green patch is a sample, not a behaviour.</p><ul>${rounds.map(roundLine).join("")}</ul><p>The attempts below are from ${fx.verified ? "the first run that passed" : "the last run"}.</p></div>`
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
      ${stepsBlock}
      <div class="attempts">${attempts}</div>
      <div class="patch--none">
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
    ${stepsBlock}
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
