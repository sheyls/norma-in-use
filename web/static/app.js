"use strict";
// NORMA-O explorer. One view per question; everything comes from /api (see web/app.py).

// ── helpers ──────────────────────────────────────────────────────────────────
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const OP = { Obligation: "O", Prohibition: "F", Permission: "P", Facultative: "P", Recommendation: "R", NegativeRecommendation: "R", ConstitutiveRule: "C" };
const KIND = { Obligation: "Obligation", Prohibition: "Prohibition", Permission: "Permission", Facultative: "Faculty",
  Recommendation: "Recommendation", NegativeRecommendation: "Negative recommendation", ConstitutiveRule: "Constitutive rule" };
const KIND_PLURAL = { Obligation: "Obligations", Prohibition: "Prohibitions", Permission: "Permissions", ConstitutiveRule: "Constitutive rules" };
const KIND_MEANS = { Obligation: "what it has to do", Prohibition: "what it must not do", Permission: "what it may do if it wants" };
const STATUS = { Applicable: "applies", Defeated: "overridden", NotActivated: "not triggered", Undecided: "undecided", Invalid: "not in force" };
let OV, NORM = {}, COND = {}, ACTIVATED_BY = {}, reading = "", pendingQuery = null;

async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const j = await r.json().catch(() => ({ error: `HTTP ${r.status}` }));
  if (!r.ok && !j.error) j.error = `HTTP ${r.status}`;
  return j;
}
const pill = k => `<span class="pill ${esc(k)}"><span class="op">${OP[k] || "?"}</span>${esc(KIND[k] || k)}</span>`;
const st = (s, strong) => `<span class="st ${esc(s)}${strong ? " diff" : ""}">${esc(STATUS[s] || s || "—")}</span>`;
const qbtn = (q, binds) => `<button class="qbtn" data-q="${esc(JSON.stringify({ q, binds }))}">see the query</button>`;
const sectionName = s => !s ? "No clause" : /^\d/.test(s) ? `Clause ${s}` : s;
const nameOf = id => NORM[id]?.reading || OV.labels[id] || id;
const shortOf = id => NORM[id]?.short || OV.labels[id] || id;
const readings = () => reading ? [reading] : [];
const bruteOnly = fs => fs.filter(f => !COND[f]?.institutional);
const caseLabel = id => OV.cases.find(c => c.id === id)?.label || id;

function normRow(n) {
  const conds = ACTIVATED_BY[n.id] || [], gaps = OV.gaps[n.id] || [];
  return `<button class="norm ${esc(n.kind)}" data-norm="${esc(n.id)}" title="Identifier: ${esc(n.id)}">
    <span class="r">${esc(n.reading)}</span><span class="side-tags">${pill(n.kind)}</span>
    <span class="meta"><span>${esc(sectionName(n.section))}</span>
      ${conds.length ? `<span class="tag cond" title="${esc(conds.map(c => COND[c]?.statement).join("\n"))}">only under a condition</span>` : ""}
      ${gaps.length ? `<span class="tag gap" title="${esc(gaps.map(g => g.category + ": " + g.missing).join("\n\n"))}">gap: ${esc(gaps[0].category)}</span>` : ""}
      ${n.variant ? `<span class="tag var">only in ${esc(n.variant)}</span>` : ""}
      <span class="open" style="margin-left:auto">Open →</span></span></button>`;
}

// ── routing ──────────────────────────────────────────────────────────────────
const VIEWS = { home: viewHome, role: viewRole, norms: viewNorms, annotation: viewAnnotation, cases: viewCases,
  exceptions: viewExceptions, graph: viewGraph, sparql: viewSparql, norm: id => { viewNorms(); if (id) openNorm(id); } };
function route() {
  const [name, arg] = decodeURIComponent(location.hash.slice(1)).split("/");
  const v = VIEWS[name] ? name : "home";
  const key = v === "role" ? `role/${arg || OV.roles[0].id}` : v === "norm" ? "norms" : v;
  document.querySelectorAll(".side a").forEach(a => a.classList.toggle("on", a.dataset.route === key));
  closeDrawer(); $("#main").scrollTop = 0;
  VIEWS[v](arg);
}
window.addEventListener("hashchange", route);
document.addEventListener("click", e => {
  const n = e.target.closest("[data-norm]"); if (n) { e.preventDefault(); openNorm(n.dataset.norm); return; }
  const q = e.target.closest("[data-q]"); if (q) { pendingQuery = JSON.parse(q.dataset.q); location.hash = "sparql"; if (location.hash === "#sparql") route(); return; }
  const g = e.target.closest("[data-graph]"); if (g) { location.hash = "graph/" + g.dataset.graph; return; }
  const l = e.target.closest("[data-line]"); if (l) { location.hash = "annotation/" + l.dataset.line; }
});

// ── home ─────────────────────────────────────────────────────────────────────
function ontoLine() {
  const o = OV.ontology;
  return `Ontology: <a href="${esc(o.repo)}" target="_blank" rel="noopener">${esc(o.title || "NORMA-O")} ${esc(o.version)}</a>
    · licensed under <a href="${esc(o.license)}" target="_blank" rel="noopener">${esc(o.licenseName)}</a>${o.doi ? ` · DOI <a href="https://doi.org/${esc(o.doi)}" target="_blank" rel="noopener">${esc(o.doi)}</a>` : ""}.
    This demo runs on a local copy of the release; nothing is fetched online.`;
}
function viewHome() {
  $("#main").innerHTML = `<div class="view">
    <section class="hero"><div class="eyebrow">A NORMA-O 2.0 demo</div><h2>${esc(OV.title)}</h2>
      <p>A real residential lease, anonymised and turned into a knowledge graph. Every clause was annotated with the NORMA-O ontology: who is bound, to do what, towards whom and when. From that annotation a reasoner works out what the contract does not say in so many words, and which norms apply in each situation.</p>
      <p class="small muted" style="margin-top:16px">${ontoLine()}</p></section>
    <section class="section"><h3 style="font:600 22px var(--serif)">How to read this demo</h3><div class="steps">
      <div class="step"><span class="n">1</span><h3>What was annotated</h3><p>What the contract says, as it was written into the graph. Each norm is shown as a sentence generated from its structure.</p></div>
      <div class="step"><span class="n">2</span><h3>What is derived</h3><p>What follows without anyone writing it down: if one party owes something, the other can claim it; if something is obligatory, it is permitted.</p></div>
      <div class="step"><span class="n">3</span><h3>What happens in a case</h3><p>Given what happened (late rent, a withdrawal…), which norms apply, which stop applying, and why.</p></div></div></section>
    <section class="section"><h3 style="font:600 22px var(--serif)">Where to start</h3><div class="tiles">
      ${OV.roles.map(r => `<a class="tile" href="#role/${esc(r.id)}"><span class="ti">◉</span><h3>What must and may the ${esc(r.label.toLowerCase())} do?</h3><p>Obligations, prohibitions and permissions, and what can be claimed from the other party.</p></a>`).join("")}
      <a class="tile" href="#cases/L07_withdraw_8m"><span class="ti">⇢</span><h3>What happens if…?</h3><p>Pick a case, for instance the tenants withdrawing in the eighth month, and follow the reasoning step by step.</p></a>
      <a class="tile" href="#exceptions"><span class="ti">⤼</span><h3>Which norm overrides which?</h3><p>Exceptions and the end of the agreement: what switches each norm off, and under which condition.</p></a>
      <a class="tile" href="#annotation"><span class="ti">{ }</span><h3>The annotation itself</h3><p>The hand-written Turtle file everything else is derived from.</p></a>
      <a class="tile" href="#graph"><span class="ti">◇</span><h3>The graph</h3><p>Click any node to see its properties; double-click to bring in its neighbours.</p></a></div></section>
    <section class="section"><h3 style="font:600 22px var(--serif)">Glossary</h3><div class="gloss">
      <div><b>Obligation · Prohibition · Permission</b>What a role must do, must not do, or may do, towards another role.</div>
      <div><b>Constitutive rule</b>A clause that orders no conduct but defines or brings something about: “the agreement is deemed terminated”, “late payment counts as a breach”.</div>
      <div><b>Condition</b>A norm that only applies if something happens: “if the rent is not paid within six days…”.</div>
      <div><b>Institutional fact</b>A fact that does not just happen but holds because a rule says so, such as “the agreement has ended”. The reasoner chains them.</div>
      <div><b>Overridden</b>A norm that does not apply in a case because another one sets it aside: an exception, the end of the agreement…</div>
      <div><b>Deontic closure</b>Everything that follows from a norm in logic: if paying is obligatory, not paying is forbidden and paying is permitted.</div>
      <div><b>Hohfeldian positions</b>Every duty of one party is a claim of the other; every permission, a privilege the other cannot prevent.</div>
      <div><b>Gap</b>Something in the contract the ontology cannot fully represent, or that a law outside the graph would correct.</div>
      <div><b>Legal reading</b>An alternative interpretation. Here, whether the amended art. 11.3 of the Urban Leases Act applies to this lease. Switch it at the top right.</div>
      <div><b>Annotation vs bundle</b>The annotation is the one file written by hand. The bundle is that file plus everything derived from it, rebuilt by the engine.</div></div></section></div>`;
}

// ── role ─────────────────────────────────────────────────────────────────────
async function viewRole(id) {
  id = id || OV.roles[0].id;
  $("#main").innerHTML = `<div class="view"><p class="faint">Loading…</p></div>`;
  const r = await api("/api/role/" + encodeURIComponent(id));
  if (r.error) { $("#main").innerHTML = `<div class="view"><div class="note">${esc(r.error)}</div></div>`; return; }
  const byKind = k => r.norms.filter(n => (k === "Permission" ? ["Permission", "Facultative"] : [k]).includes(n.kind));
  const P = k => r.positions.filter(p => p.kind === k);
  const the = s => "the " + (s || "").toLowerCase();
  const from = p => `<div class="from">derived from the ${esc((KIND[p.normKind] || "norm").toLowerCase())}: <button data-norm="${esc(p.norm)}" title="${esc(p.norm)}">${esc(p.normShort)}</button></div>`;
  const quad = (title, hint, list, fmt, cls) => `<div class="quad ${cls}"><h3>${title}<span class="faint">${list.length}</span></h3><p class="hint">${hint}</p>
    <ul>${list.map(p => `<li>${fmt(p)}${from(p)}</li>`).join("") || `<li class="faint">None.</li>`}</ul></div>`;
  $("#main").innerHTML = `<div class="view">
    <div class="vhead"><div class="eyebrow">Role</div><h2>${esc(r.label)}</h2>
      <p class="lede">${r.parties.length ? `Played by ${r.parties.map(esc).join(" and ")} in the cases.` : "No case assigns this role to a party."}
      First, what the contract imposes on or allows this role, as annotated. Then, what the reasoner derives from it.</p></div>
    <section class="section"><div class="shead"><div><h3>Annotated in the contract</h3>
      <p class="muted">Norms addressed to ${esc(the(r.label))}. Each sentence is generated from the annotated structure (kind, addressee, counterparty, action), not copied from the contract.</p></div>${qbtn(r.queries.norms, { role: r.id })}</div>
      <div class="groups">${["Obligation", "Prohibition", "Permission"].map(k => byKind(k).length ? `<div class="list"><div class="ghead">${pill(k)}<span class="n">${byKind(k).length}</span><span class="what">${KIND_MEANS[k]}</span></div>${byKind(k).map(normRow).join("")}</div>` : "").join("")
        || `<p class="faint">No annotated norm is addressed to this role.</p>`}</div></section>
    <section class="section"><div class="shead"><div><h3>Derived: legal positions</h3>
      <p class="muted">Every obligation or prohibition gives a duty to its addressee and the matching claim to the other party; every permission, a privilege and the matching no-right. Computed by <code>derive.py</code> (rules 04a–04d); nobody annotated them.</p></div>${qbtn(r.queries.positions, { role: r.id })}</div>
      <div class="explain"><span class="i">i</span><span>If the other party is bound to something towards this role, this role has a <b>claim</b> to it. If the other party has a permission, this role <b>cannot stop</b> it. Each line says which norm it comes from.</span></div>
      <div class="square">
        ${quad("Duties", "What it must do or refrain from, and towards whom.", P("Duty"), p => `${esc(p.content)} <span class="faint">towards ${esc(the(p.other))}</span>`, "duty")}
        ${quad("Claims", "What it can demand from the other party: the other side of the other party's duties.", P("Claim"), p => `can demand that ${esc(the(p.other))}: ${esc(p.content)}`, "claim")}
        ${quad("Privileges", "What it is free to do, because a permission allows it.", P("Privilege"), p => `${esc(p.content)} <span class="faint">towards ${esc(the(p.other))}</span>`, "priv")}
        ${quad("No-rights", "What it cannot stop: the other side of the other party's privileges.", P("NoRight"), p => `cannot stop ${esc(the(p.other))} from: ${esc(p.content)}`, "noright")}
      </div></section></div>`;
}

// ── all norms ────────────────────────────────────────────────────────────────
const normFilter = { kinds: new Set(Object.keys(KIND_PLURAL)), q: "" };
function viewNorms() {
  $("#main").innerHTML = `<div class="view">
    <div class="vhead"><div class="eyebrow">The contract</div><h2>All norms, clause by clause</h2>
      <p class="lede">Each row is an annotated norm, read in plain words from its representation. Open one to see its conditions, exceptions, deontic closure, positions, provenance and status in every case.</p></div>
    <div class="filters" id="nf">${Object.keys(KIND_PLURAL).map(k => `<button class="chip" data-k="${k}" aria-pressed="${normFilter.kinds.has(k)}">${OP[k]} · ${KIND_PLURAL[k]}</button>`).join("")}
      <input type="search" id="nq" placeholder="Search the norms" value="${esc(normFilter.q)}" aria-label="Search the norms"><span class="faint small" id="nn"></span></div>
    <div class="groups" id="nl"></div></div>`;
  const draw = () => {
    const q = normFilter.q.toLowerCase();
    const list = OV.norms.filter(n => normFilter.kinds.has(n.kind === "Facultative" ? "Permission" : n.kind)
      && (!q || [n.id, n.reading, n.statement].some(x => (x || "").toLowerCase().includes(q))));
    $("#nn").textContent = `${list.length} of ${OV.norms.length}`;
    const groups = {}; list.forEach(n => (groups[(n.section || "").split(",")[0].trim()] ||= []).push(n));
    $("#nl").innerHTML = Object.entries(groups).sort((a, b) => a[0].localeCompare(b[0], "en", { numeric: true }))
      .map(([s, ns]) => `<div class="clause"><div class="ch">${esc(sectionName(s))}</div>${ns.map(normRow).join("")}</div>`).join("");
  };
  $("#nf").addEventListener("click", e => { const b = e.target.closest(".chip"); if (!b) return;
    normFilter.kinds.has(b.dataset.k) ? normFilter.kinds.delete(b.dataset.k) : normFilter.kinds.add(b.dataset.k);
    b.setAttribute("aria-pressed", normFilter.kinds.has(b.dataset.k)); draw(); });
  $("#nq").addEventListener("input", e => { normFilter.q = e.target.value; draw(); });
  draw();
}

// ── norm sheet ───────────────────────────────────────────────────────────────
function closeDrawer() { $("#drawer").hidden = true; $("#scrim").hidden = true; }
$("#drawerClose").onclick = closeDrawer;
const setMenu = open => { document.body.classList.toggle("menu-open", open); $("#menuBtn").setAttribute("aria-expanded", open); };
document.body.addEventListener("click", e => { if (e.target === document.body) setMenu(false); });
$("#menuBtn").onclick = () => setMenu(!document.body.classList.contains("menu-open"));
$(".side").addEventListener("click", e => { if (e.target.closest("a")) setMenu(false); }); $("#scrim").onclick = () => { closeDrawer(); setMenu(false); };
document.addEventListener("keydown", e => { if (e.key === "Escape") closeDrawer(); });
const REVIEW = { Approved: "approved", PendingReview: "pending review", NotReviewed: "not reviewed", UnderReview: "under review", Disputed: "disputed" };
const METHOD = { LLMExtraction: "extraction with a language model", ManualAnalyst: "by hand (analyst)", ManualLawyer: "by hand (lawyer)", RuleBased: "rule-based", PatternMatching: "pattern matching" };
const FORCE = { Contractual: "contractual: binding because the parties agreed to it", HardLaw: "mandatory law", SoftLaw: "soft law (not binding)", InternalPolicy: "internal policy" };
async function openNorm(id) {
  $("#drawer").hidden = false; $("#scrim").hidden = false; $("#drawerBody").innerHTML = `<p class="faint">Loading…</p>`;
  const n = await api("/api/norm/" + encodeURIComponent(id));
  if (n.error) { $("#drawerBody").innerHTML = `<div class="note">${esc(n.error)}</div>`; return; }
  const other = d => `<button class="link" data-norm="${esc(d.other.id)}">${esc(d.other.reading)}</button>${d.gate ? `<div class="faint small">only when: ${esc(d.gate)}</div>` : ""}${d.onlyIn ? ` <span class="tag var">only in ${esc(d.onlyIn)}</span>` : ""}`;
  const by = n.defeat.filter(d => d.direction === "overridden by"), over = n.defeat.filter(d => d.direction === "overrides");
  const pv = n.provenance;
  const facts = [
    n.agent && ["Addressed to", `${esc(n.agent)}${n.counterparty ? ` <span class="faint">→ towards</span> ${esc(n.counterparty)}` : ""}`],
    n.action && ["Action", esc(n.action)],
    ["Applies", n.when.length ? n.when.map(w => `when «${esc(w.text)}» ${w.holds ? "holds" : "does not hold"}${w.institutional ? ` <span class="tag var">institutional fact</span>` : ""}`).join("<br>") : "always: it depends on no condition"],
    n.deadline && ["Deadline", esc(n.deadline)],
    ["Unless", by.length ? by.map(other).join("<br>") : "nothing overrides it"],
    over.length && ["Overrides", over.map(other).join("<br>")],
    n.establishes.length && ["Establishes", n.establishes.map(esc).join("<br>")],
    ["Binding force", n.bindingForce ? esc(FORCE[n.bindingForce] || n.bindingForce) : `<span class="faint">${n.kind === "ConstitutiveRule" ? "not applicable to constitutive rules" : "not annotated"}</span>`],
    ["Defeasibility", n.strength ? esc(n.strength) : `defeasible <span class="faint">(the default)</span>`],
  ].filter(Boolean);
  const prov = [
    ["Source", pv.source ? esc(pv.source) + (pv.rank ? ` <span class="faint">· ${esc(pv.rank)}</span>` : "") : `<span class="faint">not annotated</span>`],
    pv.versions.length && ["Versions", pv.versions.map(esc).join("<br>")],
    ["Status", pv.status ? esc(pv.status === "Active" ? "in force" : pv.status) : `<span class="faint">not annotated</span>`],
    ["Review", pv.review ? esc(REVIEW[pv.review] || pv.review) : `<span class="faint">not annotated</span>`],
    ["Annotated by", pv.annotators.length ? pv.annotators.map(esc).join("<br>") : `<span class="faint">not annotated</span>`],
    ["Method", pv.method ? esc(METHOD[pv.method] || pv.method) : `<span class="faint">not annotated</span>`],
    pv.activity && ["Annotation activity", esc(pv.activity) + (pv.date ? ` <span class="faint">· ${esc(pv.date)}</span>` : "")],
    ["Identifier", `<code>${esc(n.id)}</code>`],
  ].filter(Boolean);
  const readingsKeys = Object.keys(n.statuses);
  const dl = rows => `<dl class="facts">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>`;
  $("#drawerBody").innerHTML = `<div class="sheet">
    <div style="display:grid;gap:8px"><div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">${pill(n.kind)}<span class="faint">${esc(sectionName(n.section))}</span>${n.variant ? `<span class="tag var">only in ${esc(n.variant)}</span>` : ""}</div>
      <p class="big">${esc(n.reading)}</p>${n.statement && n.statement !== n.reading ? `<p class="quote">${esc(n.statement)}</p>` : ""}</div>
    <div class="btnrow"><button class="btn" data-graph="${esc(n.id)}">Show in the graph</button>${n.sourceLine ? `<button class="btn" data-line="${n.sourceLine}">Show in the annotation (line ${n.sourceLine})</button>` : ""}</div>
    ${n.gaps.map(g => `<div class="note"><b>Gap · ${esc(g.category)}</b><br>${esc(g.missing)}</div>`).join("")}
    ${dl(facts)}${n.comment ? `<p class="small muted">${esc(n.comment)}</p>` : ""}
    <div style="display:grid;gap:8px"><div class="sub-h"><h3>Status in every case</h3>${qbtn(n.queries.caseStatus, { case: OV.cases[0].id })}</div>
      <table class="t"><thead><tr><th>Case</th>${readingsKeys.map(k => `<th>${esc(k)}</th>`).join("")}</tr></thead><tbody>
      ${OV.cases.map(c => { const v = readingsKeys.map(k => n.statuses[k][c.id]); const diff = new Set(v).size > 1;
        return `<tr class="${diff ? "hl" : ""}"><td><a href="#cases/${esc(c.id)}">${esc(c.label)}</a></td>${v.map(s => `<td>${st(s, diff)}</td>`).join("")}</tr>`; }).join("")}</tbody></table></div>
    ${n.closure.length ? `<div style="display:grid;gap:8px"><div class="sub-h"><h3>Deontic closure</h3>${qbtn(n.queries.closure, { norm: n.id })}</div>
      <p class="small muted">Everything that follows from the norm in standard deontic logic. Only the first row was annotated; rules 02a–02f derive the rest.</p>
      <table class="t"><tbody>${n.closure.map(c => `<tr><td class="f">${esc(c.symbol)}</td><td>${esc(c.action)}: <b>${esc(c.meaning)}</b></td><td>${c.annotated ? `<span class="tag ann">annotated</span>` : `<span class="tag der">derived</span>`}</td></tr>`).join("")}</tbody></table></div>` : ""}
    ${n.positions.length ? `<div style="display:grid;gap:8px"><div class="sub-h"><h3>Legal positions (derived)</h3>${qbtn(n.queries.positions, { norm: n.id })}</div>
      ${n.positions.map(p => `<p class="small"><b>${esc(p.kind)}</b> of ${esc(p.holder)}: ${esc(p.content)}<br><span class="muted">${p.correlative ? `↔ its correlative: ${esc(p.correlative)}` : "no correlative: the norm names no counterparty"}</span></p>`).join("")}</div>` : ""}
    ${n.relations.length ? `<div style="display:grid;gap:8px"><div class="sub-h"><h3>Relations with other norms (derived)</h3>${qbtn(n.queries.relations, { norm: n.id })}</div>
      ${n.relations.map(r => `<p class="small">${esc(r.relation)} <button class="link" data-norm="${esc(r.other.id)}">${esc(r.other.reading)}</button></p>`).join("")}
      <p class="small faint">Derived between the norms as written; whether the clash actually arises depends on the case.</p></div>` : ""}
    <div style="display:grid;gap:8px"><div class="sub-h"><h3>Source and provenance</h3></div>${dl(prov)}</div></div>`;
}

// ── cases ────────────────────────────────────────────────────────────────────
let caseState = { id: null, facts: new Set(), roles: [], editing: false };
function viewCases(id) {
  const c = OV.cases.find(x => x.id === id) || OV.cases.find(x => x.id === OV.referenceCase);
  if (id !== "custom") caseState = { id: c.id, facts: new Set(bruteOnly(c.facts)), roles: c.roleAssignments, editing: false };
  $("#main").innerHTML = `<div class="cases">
    <div class="caselist" role="group" aria-label="Cases"><div class="h">Pick a case</div>${OV.cases.map(x => { const m = /^(\S+)\s+(.*)$/.exec(x.label) || [0, "", x.label];
      return `<button data-case="${esc(x.id)}" aria-pressed="${x.id === caseState.id}"><span class="code">${esc(m[1])}</span><span>${esc(m[2])}</span></button>`; }).join("")}
      <button data-case="custom" aria-pressed="${!caseState.id}"><span class="code">＋</span><span>Your own case: tick the facts yourself</span></button></div>
    <div class="view" id="caseView"><p class="faint">Deriving…</p></div></div>`;
  $(".caselist").addEventListener("click", e => { const b = e.target.closest("[data-case]"); if (!b) return;
    if (b.dataset.case === "custom") { caseState = { id: null, facts: new Set(caseState.facts), roles: caseState.roles, editing: true }; history.replaceState(null, "", "#cases/custom"); viewCases("custom"); }
    else location.hash = "cases/" + b.dataset.case; });
  renderCase();
}
async function renderCase() {
  $("#busy").hidden = false;
  const facts = [...caseState.facts];
  const others = ["", ...OV.variants].filter(v => v !== reading);
  const [r, ...alt] = await Promise.all([api("/api/simulate", { facts, roles: caseState.roles, readings: readings() }),
    ...others.map(v => api("/api/simulate", { facts, roles: caseState.roles, readings: v ? [v] : [] }))]);
  $("#busy").hidden = true;
  const c = OV.cases.find(x => x.id === caseState.id);
  const ref = caseLabel(OV.referenceCase);
  const conseq = r.steps.find(s => s.title === "Consequences");
  const rulesStep = r.steps.find(s => s.title === "Rules that fire"), instStep = r.steps.find(s => s.title === "Facts they establish");
  const because = (label, xs) => xs.length ? `<div class="because"><b>${label}</b>${xs.map(esc).join("; ")}</div>` : "";
  const list = (items, render, max = 6) => {
    const shown = items.slice(0, max).map(render).join("");
    return items.length > max ? shown + `<details><summary class="more-btn">Show the other ${items.length - max}</summary><div class="body" style="margin-top:8px">${items.slice(max).map(render).join("")}</div></details>` : shown;
  };
  const conflicts = Object.keys(r.status).filter(n => r.status[n] === "Applicable" && (OV.gaps[n] || []).some(g => /conflict/i.test(g.category)));
  const altDiff = alt.map((o, i) => ({ v: others[i] || "Base reading", d: Object.keys(r.status).filter(n => n in o.status && r.status[n] !== o.status[n]), o }));
  let n = 0;
  const step = (cls, title, sub, body) => `<div class="step-v ${cls}"><span class="dot">${++n}</span><div><h3>${title}</h3><p class="sub">${sub}</p><div class="body">${body}</div></div></div>`;
  $("#caseView").innerHTML = `
    <div class="vhead"><div class="eyebrow">${c ? "Test case" : "Your own case"} · ${esc(reading || "Base reading")}</div><h2>${esc(c ? c.label : "Your own case")}</h2>
      <p class="lede">A case only states plain facts. The reasoner does the rest: it triggers the norms that depend on those facts, works out the facts that rules establish, and settles the exceptions. Changes are shown against «${esc(ref)}».</p></div>
    <div class="summary-bar"><div class="sb on"><b>${conseq.starts.length}</b><span>norms start to apply</span></div><div class="sb off"><b>${conseq.stops.length}</b><span>norms stop applying</span></div>
      <div class="sb"><b>${r.institutional.length}</b><span>facts established by rules</span></div>${altDiff.map(x => `<div class="sb alt"><b>${x.d.length}</b><span>differ under «${esc(x.v)}»</span></div>`).join("")}</div>
    <div class="card"><div class="shead"><h3>How the result is reached</h3><div class="btnrow"><button class="btn" id="editFacts">${caseState.editing ? "Done editing" : "Change the facts"}</button>${c ? qbtn(OV.queries.find(q => q.binds.includes("case")).sparql, { case: c.id }) : ""}</div></div>
      ${caseState.editing ? `<div class="editfacts" id="factEdit">${factChecklist()}</div>` : ""}
      <div class="steps-v">
        ${step("facts", "What happened", "The facts of the case, as stated. Nothing else is assumed.", facts.map(f => `<div class="sitem fact">${esc(COND[f]?.statement || f)}</div>`).join("") || `<p class="faint">No facts: nothing has happened.</p>`)}
        ${rulesStep ? step("rules", "Rules that fire", "Constitutive rules whose condition the facts meet.", list(rulesStep.items, i => `<button class="sitem" data-norm="${esc(i.id)}">${esc(i.text)}${because("because", i.because)}</button>`)) : ""}
        ${instStep ? step("inst", "Facts they establish", "Institutional facts: nobody stated them; the rules above bring them about.", list(instStep.items, i => `<div class="sitem inst">${esc(i.text)}${because("established by", i.because)}</div>`)) : ""}
        ${step("result", "What changes", `Compared with «${esc(ref)}».`, `<div class="split">
          <div><h4 class="on">✓ Start to apply (${conseq.starts.length})</h4><div class="body">${list(conseq.starts, i => `<button class="sitem on" data-norm="${esc(i.id)}">${esc(i.text)}${because("because", i.because)}</button>`) || `<p class="faint small">None.</p>`}</div></div>
          <div><h4 class="off">✕ Stop applying (${conseq.stops.length})</h4><div class="body">${list(conseq.stops, i => `<button class="sitem off" data-norm="${esc(i.id)}">${esc(i.text)}${because(i.because.length ? "overridden by" : "because", i.because.length ? i.because : [i.status === "NotActivated" ? "its condition no longer holds" : STATUS[i.status]])}</button>`) || `<p class="faint small">None.</p>`}</div></div></div>`)}
      </div></div>
    ${altDiff.map(x => `<div class="card chg alt"><h3>Under «${esc(x.v)}»</h3>${x.d.length ? x.d.map(id => `<div class="item"><button class="link" data-norm="${esc(id)}">${esc(nameOf(id))}</button><span class="why">${st(r.status[id])} → ${st(x.o.status[id])}</span></div>`).join("")
      : `<p class="faint small">Both readings give the same result in this case.</p>`}</div>`).join("")}
    ${conflicts.length ? `<div class="card chg warn"><h3>Applied in the graph, but at odds with mandatory law (${conflicts.length})</h3><p class="small muted">The graph only holds the contract. The annotation records that a law outside the graph would correct the result.</p>
      ${conflicts.map(id => `<div class="item"><button class="link" data-norm="${esc(id)}">${esc(nameOf(id))}</button>${OV.gaps[id].map(g => `<span class="why">${esc(g.missing)}</span>`).join("")}</div>`).join("")}</div>` : ""}
    ${r.warnings.map(w => `<div class="note">${esc(w)}</div>`).join("")}
    <details class="card"><summary>What each party must and may do in this case</summary><div class="cols2" style="margin-top:12px">${OV.roles.map(role => {
      const parties = Object.entries(r.positions).filter(([p]) => role.parties.includes(OV.labels[p] || p));
      return parties.length ? `<div><div class="eyebrow" style="margin-bottom:6px">${esc(role.label)}</div>${parties.map(([p, ps]) => `<div style="margin-bottom:16px"><h3>${esc(OV.labels[p] || p)}</h3>
      ${ps.map(x => `<p class="small" style="padding-top:6px;border-top:1px solid var(--line)"><b>${x.kind === "Duty" ? "Must" : "May"}</b>: <button class="link" data-norm="${esc(x.norm)}">${esc(x.action)}</button></p>`).join("")}</div>`).join("")}</div>` : ""; }).join("")}</div></details>`;
  $("#editFacts").onclick = () => { caseState.editing = !caseState.editing; renderCase(); };
  $("#factEdit")?.addEventListener("change", e => { const f = e.target.dataset.f; if (!f) return; e.target.checked ? caseState.facts.add(f) : caseState.facts.delete(f);
    caseState.id = null; history.replaceState(null, "", "#cases/custom");
    document.querySelectorAll(".caselist button").forEach(b => b.setAttribute("aria-pressed", b.dataset.case === "custom")); renderCase(); });
}
function factChecklist() {
  let last = null, h = "";
  for (const c of OV.conditions.filter(c => !c.institutional)) {
    const s = sectionName((c.sections[0] || "").split(",")[0]);
    if (s !== last) { h += `<div class="sec">${esc(s)}</div>`; last = s; }
    h += `<label><input type="checkbox" data-f="${esc(c.id)}"${caseState.facts.has(c.id) ? " checked" : ""}><span>${esc(c.statement)}</span></label>`;
  }
  return h;
}

// ── exceptions ───────────────────────────────────────────────────────────────
async function viewExceptions() {
  $("#main").innerHTML = `<div class="view"><p class="faint">Loading…</p></div>`;
  const x = await api("/api/exceptions");
  const when = g => g.when.length ? `<div class="when"><b>when</b>${[...new Set(g.when.map(w => w.text))].map(esc).join(" <i>or</i> ")}</div>` : `<div class="when"><b>when</b>always (no condition)</div>`;
  $("#main").innerHTML = `<div class="view">
    <div class="vhead"><div class="eyebrow">Reasoning</div><h2>Exceptions: which norm overrides which</h2>
      <p class="lede">Norms in a contract are defeasible: one norm can set another aside. Each box below is one overriding norm, the condition under which it is triggered, and the norms it switches off. Whether that actually happens depends on the case; see <a href="#cases">Cases</a>.</p></div>
    <section class="section">${x.groups.map(g => `<div class="exc">
      <div class="who">${pill(g.by.kind)}<button class="link" style="font-size:16.5px" data-norm="${esc(g.by.id)}">${esc(g.by.reading)}</button>${when(g)}${g.by.variant ? `<span class="tag var">only in ${esc(g.by.variant)}</span>` : ""}</div>
      <div class="arrow" aria-hidden="true">⟶</div>
      <div><div class="small muted" style="margin-bottom:8px">overrides ${g.overrides.length} norm${g.overrides.length > 1 ? "s" : ""}:</div><ul>${g.overrides.map(o => `<li><button data-norm="${esc(o.norm.id)}">${esc(o.norm.reading)}</button>${o.gate ? `<span class="gate">only when: ${esc(o.gate)}</span>` : ""}${o.onlyIn ? ` <span class="tag var">only in ${esc(o.onlyIn)}</span>` : ""}</li>`).join("")}</ul></div></div>`).join("")}</section>
    <section class="section"><div class="shead"><div><h3>The prevalence ladder</h3>
      <p class="muted">The reasoner orders the norms that take part in exceptions into tiers: a norm can only be overridden by one on a higher tier, and the order has no cycles. Computed with no case in view (the static ordering).</p></div></div>
      <div class="tiers">${x.ladder.map((t, i) => `<div class="tier"><div class="lv">Tier ${x.ladder.length - i}<span>${i === 0 ? "overrides the rest" : i === x.ladder.length - 1 ? "can be overridden" : "in between"}</span></div>
        <div class="chips">${t.norms.map(id => `<button class="tchip" data-norm="${esc(id)}">${esc(shortOf(id).slice(0, 60))}</button>`).join("")}${t.others ? `<span class="faint small" style="align-self:center">+ ${t.others} norms with no exception</span>` : ""}</div></div>`).join("")}</div></section></div>`;
}

// ── the annotation (Turtle) ──────────────────────────────────────────────────
let SOURCE = null;
function highlight(line) {
  if (/^\s*#/.test(line)) return `<span class="tk-c">${esc(line)}</span>`;
  return esc(line)
    .replace(/(&quot;(?:[^&]|&(?!quot;))*?&quot;(?:@[a-z-]+|\^\^[\w:]+)?)/g, '<span class="tk-s">$1</span>')
    .replace(/(^|[\s,;(])(norma:[A-Za-z]+)/g, '$1<span class="tk-p">$2</span>')
    .replace(/(^|[\s,;(])(:[A-Za-z0-9_]+)/g, '$1<span class="tk-i">$2</span>')
    .replace(/(@prefix|\ba\b)/g, '<span class="tk-k">$1</span>');
}
async function viewAnnotation(line) {
  if (!SOURCE) SOURCE = await api("/api/source");
  let fileIdx = 0;
  const render = () => {
    const f = SOURCE.files[fileIdx], lines = f.text.split("\n");
    const toc = [];
    lines.forEach((l, i) => {
      let m;
      if (i > 0 && /^# ═+$/.test(lines[i - 1]) && /^# \S/.test(l)) toc.push([i + 1, l.slice(2).split(":")[0], "sec"]);
      else if ((m = /^# =+ (\S.*)$/.exec(l))) toc.push([i + 1, m[1][0].toUpperCase() + m[1].slice(1), "sec"]);
    });
    $("#main").innerHTML = `<div class="view" style="max-width:1320px">
      <div class="vhead"><div class="eyebrow">The contract</div><h2>The annotation</h2>
        <p class="lede">This is the only file written by hand: the norms, the cases, the gaps and the provenance, in NORMA-O 2.0 Turtle. Everything else in this demo is derived from it by the NORMA-O engine (the <code>norma</code> command of the <code>norma-o</code> package).</p></div>
      <div class="filters">${SOURCE.files.map((x, i) => `<button class="chip" data-file="${i}" aria-pressed="${i === fileIdx}">${esc(x.name)} <span class="faint">· ${esc(x.role)}</span></button>`).join("")}
        <input type="search" id="tq" placeholder="Search the Turtle" aria-label="Search the Turtle"><span class="faint small" id="tn"></span>
        <a class="btn" href="/files/${fileIdx === 0 ? "annotation" : "reading-" + (fileIdx - 1)}">Download</a><a class="btn" href="/files/bundle">Download the bundle</a></div>
      <div class="ttl-wrap"><div class="toc"><div class="h">Sections</div><button data-goto="1">Header and conventions</button>${toc.map(([n, s, k]) => `<button data-goto="${n}" class="${k}">${esc(s)}</button>`).join("")}
          <div class="h">Lines</div><span class="faint small" style="padding:0 10px">${lines.length} lines · ${(f.text.length / 1024).toFixed(0)} KB</span></div>
        <div class="code" id="code"><table><tbody>${lines.map((l, i) => `<tr id="L${i + 1}"><td class="n">${i + 1}</td><td class="l">${highlight(l) || " "}</td></tr>`).join("")}</tbody></table></div></div></div>`;
    const go = n => { const tr = $("#L" + n); if (!tr) return; document.querySelectorAll("#code tr.focus").forEach(t => t.classList.remove("focus"));
      tr.classList.add("focus"); $("#code").scrollTop = tr.offsetTop - 60; };
    document.querySelector(".toc").addEventListener("click", e => { const b = e.target.closest("[data-goto]"); if (b) go(+b.dataset.goto); });
    document.querySelectorAll("[data-file]").forEach(b => b.onclick = () => { fileIdx = +b.dataset.file; render(); });
    $("#tq").addEventListener("input", e => { const q = e.target.value.toLowerCase(); let k = 0, first = null;
      document.querySelectorAll("#code tr").forEach((tr, i) => { const hit = q && lines[i].toLowerCase().includes(q); tr.classList.toggle("hit", !!hit); if (hit) { k++; first ??= i + 1; } });
      $("#tn").textContent = q ? `${k} lines` : ""; if (first) go(first); });
    if (line && fileIdx === 0) setTimeout(() => go(+line), 0);
  };
  render();
}

// ── graph ────────────────────────────────────────────────────────────────────
const GSTYLE = { Obligation: ["--O", "--O-wash"], Prohibition: ["--F", "--F-wash"], Permission: ["--P", "--P-wash"], ConstitutiveRule: ["--C", "--C-wash"],
  Condition: ["--fact", "--fact-wash"], Role: ["--inst", "--inst-wash"], Party: ["--inst", "--inst-wash"], Case: ["--accent", "--accent-wash"],
  Action: ["--ink-3", "--sunken"], Gap: ["--gap", "--gap-wash"], Source: ["--und", "--fact-wash"], Annotator: ["--ink-2", "--sunken"] };
const GSTYLE_ALIAS = { Facultative: "Permission", Expression: "Source", Activity: "Annotator", Trigger: "Condition", RoleAssignment: "Role" };
const GLEGEND = { Obligation: "Obligation", Prohibition: "Prohibition", Permission: "Permission", ConstitutiveRule: "Constitutive rule", Condition: "Condition or fact",
  Role: "Role or party", Case: "Case", Action: "Action", Gap: "Gap", Source: "Legal source", Annotator: "Annotator" };
let gcy = null, gOpts = { collapse: true, derived: false };
function viewGraph(start) {
  $("#main").innerHTML = `<div class="view gview">
    <div class="vhead"><div class="eyebrow">Explore</div><h2>The graph</h2>
      <p class="lede">Every node is an individual of the annotation. <b>Click</b> a node to see all its properties on the right; <b>double-click</b> it, or press “Bring in neighbours”, to add the nodes it is linked to.</p></div>
    <div class="gbar"><div class="search"><input type="search" id="gs" placeholder="Search a node: rent, withdrawal, deposit…" autocomplete="off" aria-label="Search a node"><div class="hits" id="gh" hidden></div></div>
      ${[...OV.roles.map(r => ({ id: r.id, label: "Role: " + r.label })), { id: "O_3_rent", label: "Paying the rent" }, { id: "c_terminated", label: "The agreement has ended" }, { id: "FCT_terminated", label: "What the end switches off" }]
        .filter(p => OV.labels[p.id] || NORM[p.id]).map(p => `<button class="chip" data-start="${esc(p.id)}">${esc(p.label)}</button>`).join("")}
      <label class="toggle"><input type="checkbox" id="gc" ${gOpts.collapse ? "checked" : ""}> condition → norm shortcuts</label>
      <label class="toggle"><input type="checkbox" id="gd" ${gOpts.derived ? "checked" : ""}> include derived nodes</label>
      <button class="btn" id="glay">Tidy up</button><button class="btn" id="gclr">Clear</button></div>
    <div class="legend">${Object.keys(GLEGEND).map(k => `<span><i style="background:${css(GSTYLE[k][1])};border:1.5px solid ${css(GSTYLE[k][0])}"></i>${GLEGEND[k]}</span>`).join("")}
      <span><i class="ln" style="background:${css("--def")}"></i>overrides</span><span><i class="ln" style="background:${css("--inst")}"></i>establishes</span></div>
    <div class="gwrap"><div id="cy"></div><aside class="ginfo" id="gi"><p class="faint">Pick a starting point above or search for a node.</p></aside></div></div>`;
  gcy = cytoscape({ container: $("#cy"), wheelSensitivity: .25, minZoom: .15, maxZoom: 2.5,
    style: [
      { selector: "node", style: { shape: "round-rectangle", width: 220, height: 64, label: "data(label)", "text-wrap": "wrap", "text-max-width": 196, "font-size": 14,
        "font-family": "IBM Plex Sans, sans-serif", "text-valign": "center", color: css("--ink"), "background-color": "data(bg)", "border-color": "data(fg)", "border-width": 1.5 } },
      { selector: "node.focus", style: { "border-width": 4 } },
      { selector: "edge", style: { width: 1.5, "curve-style": "bezier", "line-color": css("--line-strong"), "target-arrow-color": css("--line-strong"), "target-arrow-shape": "triangle",
        label: "data(label)", "font-size": 11, color: css("--ink-2"), "text-background-color": css("--surface"), "text-background-opacity": 1, "text-background-padding": 2 } },
      { selector: "edge[label = 'overrides']", style: { "line-color": css("--def"), "target-arrow-color": css("--def"), "line-style": "dashed", width: 2.2 } },
      { selector: "edge[label ^= 'establishes']", style: { "line-color": css("--inst"), "target-arrow-color": css("--inst"), width: 2.2 } },
    ] });
  gcy.on("tap", "node", e => show(e.target.id(), false));
  gcy.on("dbltap", "node", e => show(e.target.id(), true));
  $(".gbar").addEventListener("click", e => { const b = e.target.closest("[data-start]"); if (b) { gcy.elements().remove(); show(b.dataset.start, true); } });
  const reset = () => { const f = gcy.$("node.focus").id(); gcy.elements().remove(); if (f) show(f, true); };
  $("#gc").onchange = e => { gOpts.collapse = e.target.checked; reset(); };
  $("#gd").onchange = e => { gOpts.derived = e.target.checked; reset(); };
  $("#glay").onclick = glayout; $("#gclr").onclick = () => gcy.elements().remove();
  let t = null;
  $("#gs").addEventListener("input", e => { clearTimeout(t); t = setTimeout(async () => { const v = e.target.value.trim(); if (!v) { $("#gh").hidden = true; return; }
    const hits = await api("/api/search?q=" + encodeURIComponent(v));
    $("#gh").innerHTML = hits.map(h => `<button data-id="${esc(h.id)}" title="${esc(h.id)}"><span>${esc(h.label)}</span><span class="g">${esc(h.groupName)}</span></button>`).join("") || `<p class="faint small" style="padding:10px">No results.</p>`;
    $("#gh").hidden = false; }, 150); });
  $("#gh").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; $("#gh").hidden = true; $("#gs").value = ""; gcy.elements().remove(); show(b.dataset.id, true); });
  show(start || "O_3_rent", true);
}
const nodeLabel = n => { const s = NORM[n.id]?.short || n.label || n.id; return s.length > 70 ? s.slice(0, 68) + "…" : s; };
async function show(id, expand) {
  const j = await api(`/api/node/${encodeURIComponent(id)}?collapse=${gOpts.collapse ? 1 : 0}&derived=${gOpts.derived ? 1 : 0}`);
  if (j.error) { $("#gi").innerHTML = `<div class="note">${esc(j.error)}</div>`; return; }
  const d = j.details;
  if (expand || !gcy.getElementById(d.id).length) {
    let added = 0;
    j.nodes.forEach(n => { if (!gcy.getElementById(n.id).length && (expand || n.id === d.id)) { const [fg, bg] = GSTYLE[GSTYLE_ALIAS[n.group] || n.group] || ["--ink-3", "--sunken"];
      gcy.add({ data: { id: n.id, label: nodeLabel(n), fg: css(fg), bg: css(bg) } }); added++; } });
    if (expand) j.edges.forEach(e => { const eid = `${e.source}|${e.label}|${e.target}`;
      if (!gcy.getElementById(eid).length && gcy.getElementById(e.source).length && gcy.getElementById(e.target).length) gcy.add({ data: { id: eid, source: e.source, target: e.target, label: e.label } }); });
    if (added) glayout();
  }
  gcy.nodes().removeClass("focus"); gcy.getElementById(d.id).addClass("focus");
  const P = j.properties;
  const val = x => x.vocabulary ? esc(x.label) : `<button data-gx="${esc(x.id)}" title="${esc(x.id)}">${esc(x.label)}</button>`;
  const sts = Object.entries(d.statuses);
  $("#gi").innerHTML = `<div class="eyebrow">${esc(d.groupName)}</div><h3>${esc(d.reading)}</h3>
    <div class="btnrow">${NORM[d.id] ? `<button class="btn primary" data-norm="${esc(d.id)}">Open the norm</button>` : ""}<button class="btn" id="gx">Bring in neighbours</button></div>
    ${d.gaps.map(g => `<div class="note"><b>Gap · ${esc(g.category)}</b><br>${esc(g.missing)}</div>`).join("")}
    <div class="props"><div class="ph">Data</div>${P.literals.map(l => `<div class="prop"><span class="k" title="${esc(l.curie)}">${esc(l.property)}</span><span class="v">${esc(l.value)}</span></div>`).join("") || `<p class="faint small">None.</p>`}
      <div class="ph">Links from this node</div>${P.outgoing.map(x => `<div class="prop${x.derived ? " der" : ""}"><span class="k" title="${esc(x.curie)}">${esc(x.property)}</span><span class="v">${val(x)}</span></div>`).join("") || `<p class="faint small">None.</p>`}
      <div class="ph">Links to this node${P.incomingTotal > P.incoming.length ? ` (first ${P.incoming.length} of ${P.incomingTotal})` : ""}</div>${P.incoming.map(x => `<div class="prop${x.derived ? " der" : ""}"><span class="k" title="${esc(x.curie)}">${esc(x.property)}</span><span class="v">${val(x)}</span></div>`).join("") || `<p class="faint small">None.</p>`}
      ${sts.length ? `<div class="ph">Status in the cases</div>${sts.map(([c, s]) => `<div class="prop"><span class="k">${st(s)}</span><span class="v small">${esc(c)}</span></div>`).join("")}` : ""}
      <div class="ph">Identifier</div><p class="small"><code>${esc(d.id)}</code></p></div>`;
  $("#gx").onclick = () => show(d.id, true);
  $("#gi").querySelectorAll("[data-gx]").forEach(b => b.onclick = () => show(b.dataset.gx, true));
}
function glayout() { gcy.resize(); gcy.layout({ name: "dagre", rankDir: "LR", nodeSep: 18, rankSep: 90, padding: 30, animate: false }).run(); gcy.fit(undefined, 30); if (gcy.zoom() > 1.2) { gcy.zoom(1.2); gcy.center(); } }

// ── SPARQL ───────────────────────────────────────────────────────────────────
let lastRes = null;
function viewSparql() {
  const qs = OV.queries;
  let lastGroup = null;
  $("#main").innerHTML = `<div class="sq">
    <div class="qlist" id="ql">${qs.map((q, i) => (q.group !== lastGroup ? `<div class="qh">${esc(lastGroup = q.group)}</div>` : "") + `<button data-i="${i}">${esc(q.title)}</button>`).join("")}
      <div class="qh">Free</div><button data-i="free">Blank query</button></div>
    <div class="view" style="max-width:none"><div class="vhead"><div class="eyebrow">Explore</div><h2>SPARQL</h2>
      <p class="lede">The queries behind every view, over the bundle and the local NORMA-O ontology. Prefixes ready to use: <code>:</code> <code>norma:</code> <code>normad:</code> <code>gap:</code> <code>rdfs:</code> <code>xsd:</code>.</p></div>
      <div class="qbar" id="qb"></div><textarea id="qText" spellcheck="false" aria-label="SPARQL query"></textarea>
      <div class="qbar"><button class="btn primary" id="qRun">Run (⌘↵)</button><button class="btn" id="qCsv" disabled>Download CSV</button><span class="faint small" id="qMeta"></span></div>
      <div class="qres" id="qRes"></div></div></div>`;
  const load = (sparql, binds = {}) => {
    $("#qText").value = sparql;
    const need = ["role", "norm", "case"].filter(v => new RegExp("\\?" + v + "\\b").test(sparql) && !new RegExp("SELECT[^\\n]*\\?" + v + "\\b").test(sparql));
    const opts = { role: OV.roles.map(r => [r.id, r.label]), norm: OV.norms.map(n => [n.id, n.short]), case: OV.cases.map(c => [c.id, c.label]) };
    $("#qb").innerHTML = need.map(v => `<label class="toggle">${{ role: "Role", norm: "Norm", case: "Case" }[v]} <select data-bind="${v}">${opts[v].map(([k, l]) => `<option value="${esc(k)}"${binds[v] === k ? " selected" : ""}>${esc(l)}</option>`).join("")}</select></label>`).join("");
  };
  $("#ql").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return;
    document.querySelectorAll("#ql button").forEach(x => x.classList.toggle("on", x === b));
    load(b.dataset.i === "free" ? "SELECT ?s ?p ?o WHERE {\n  ?s ?p ?o\n} LIMIT 50" : qs[+b.dataset.i].sparql); runQuery(); });
  $("#qRun").onclick = runQuery;
  $("#qText").addEventListener("keydown", e => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); runQuery(); } });
  $("#qCsv").onclick = () => { const cell = v => /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(new Blob([[lastRes.cols, ...lastRes.rows].map(r => r.map(cell).join(",")).join("\n")], { type: "text/csv" })), download: "query.csv" });
    a.click(); URL.revokeObjectURL(a.href); };
  if (pendingQuery) { load(pendingQuery.q, pendingQuery.binds || {}); pendingQuery = null; runQuery(); } else { $("#ql button").click(); }
}
async function runQuery() {
  $("#qMeta").textContent = "running…";
  const bind = {}; document.querySelectorAll("[data-bind]").forEach(s => bind[s.dataset.bind] = s.value);
  const r = await api("/api/sparql", { query: $("#qText").value, bind });
  if (r.error) { $("#qRes").innerHTML = `<div class="err">${esc(r.error)}</div>`; $("#qMeta").textContent = ""; $("#qCsv").disabled = true; return; }
  lastRes = r; $("#qCsv").disabled = false; $("#qMeta").textContent = `${r.rows.length} rows · ${r.seconds}s`;
  const cell = v => NORM[v] ? `<td class="id"><button data-norm="${esc(v)}">${esc(v)}</button> <span class="faint">${esc(NORM[v].short)}</span></td>`
    : OV.labels[v] && OV.labels[v] !== v ? `<td class="id"><button data-graph="${esc(v)}">${esc(v)}</button> <span class="faint">${esc(OV.labels[v].slice(0, 90))}</span></td>` : `<td>${esc(v)}</td>`;
  $("#qRes").innerHTML = `<table><thead><tr>${r.cols.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${r.rows.slice(0, 2000).map(row => `<tr>${row.map(cell).join("")}</tr>`).join("")}</tbody></table>`;
}

// ── boot ─────────────────────────────────────────────────────────────────────
(async () => {
  OV = await api("/api/overview");
  OV.norms.forEach(n => NORM[n.id] = n);
  OV.conditions.forEach(c => { COND[c.id] = c; c.activates.forEach(n => (ACTIVATED_BY[n] ||= []).push(c.id)); });
  $("#title").textContent = OV.title; document.title = "NORMA-O · " + OV.title;
  $("#navRoles").innerHTML = OV.roles.map(r => `<a href="#role/${esc(r.id)}" data-route="role/${esc(r.id)}"><span class="ic">◉</span><span>${esc(r.label)}<span class="sub">${esc(r.parties.join(", ") || "no party assigned")}</span></span></a>`).join("");
  const bad = Object.keys(OV.selfCheck).length;
  $("#navFoot").innerHTML = `${OV.norms.length} norms · ${OV.conditions.length} conditions · ${OV.cases.length} cases<br>${OV.triples.toLocaleString("en")} triples in the bundle<br>${bad ? `⚠ ${bad} case(s) not reproduced` : `<span class="ok">✓</span> re-deriving reproduces the bundle`}<br><a href="${esc(OV.ontology.repo)}" target="_blank" rel="noopener">NORMA-O ${esc(OV.ontology.version)} on GitHub</a> · <a href="${esc(OV.ontology.license)}" target="_blank" rel="noopener">${esc(OV.ontology.licenseName)}</a>`;
  if (OV.variants.length) {
    $("#readingBox").hidden = false;
    $("#readingSeg").innerHTML = ["", ...OV.variants].map(v => `<button role="radio" aria-checked="${v === reading}" data-v="${esc(v)}"><span class="lg">${esc(v || "Base reading")}</span><span class="sm">${esc(v ? v.split(":")[0] : "Base")}</span></button>`).join("");
    $("#readingSeg").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; reading = b.dataset.v;
      document.querySelectorAll("#readingSeg button").forEach(x => x.setAttribute("aria-checked", x === b)); if (location.hash.startsWith("#cases")) renderCase(); });
  }
  route();
})();
