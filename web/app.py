"""NORMA-O explorer: a local web demo over the test contract.

    ../.venv/bin/python app.py BUNDLE --annotation lease.ttl --variant "Name=variant.ttl"
    ../.venv/bin/python app.py      # defaults: the test contract in ../residential-lease

Modules: text.py (all generated wording), model.py (the loaded bundle and its
read-only views), reasoner.py (case simulation with the real derive.py and its
step-by-step explanation). This file only wires them to HTTP.
NORMA-O comes from the installed norma-o package: its IRIs resolve to the
package's files, so nothing is fetched from the network.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from model import Model  # noqa: E402
from reasoner import Simulator  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
LEASE = ROOT / "residential-lease"
ap.add_argument("bundle", nargs="?", type=Path, default=LEASE / "generated" / "lease.bundle.ttl")
ap.add_argument("--annotation", type=Path, default=LEASE / "annotation" / "lease.ttl", help="the hand-written Turtle, shown in the explorer")
ap.add_argument("--variant", action="append", default=[], metavar="NAME=FILE.ttl", help="an alternative legal reading")
ap.add_argument("--title")
ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5050)))
ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"), help="0.0.0.0 inside a container")
ARGS = ap.parse_args()
if not ARGS.bundle.exists():
    sys.exit(f"No bundle at {ARGS.bundle}. Generate it first, from the project root:\n"
             "  .venv/bin/norma residential-lease/annotation/lease.ttl --out residential-lease/generated")


def reading_name(p: Path) -> str:
    first = p.read_text(encoding="utf-8").splitlines()[0]
    return first[len("# Reading:"):].strip() if first.startswith("# Reading:") else p.stem


# Alternative readings: given with --variant, or (as the engine does) every variant-*.ttl next to the annotation.
variants = {}
for v in ARGS.variant:
    name, _, path = v.rpartition("=")
    variants[name or Path(path).stem] = Path(path).resolve()
if not ARGS.variant and ARGS.annotation:
    variants = {reading_name(p): p.resolve() for p in sorted(ARGS.annotation.parent.glob("variant-*.ttl"))}

# ── load ─────────────────────────────────────────────────────────────────────
t0 = time.time()
M = Model(ARGS.bundle.resolve(), ARGS.annotation.resolve() if ARGS.annotation else None, variants, ARGS.title)
S = Simulator(M)
OVERVIEW = M.overview()
CASES = {c["id"]: c for c in OVERVIEW["cases"]}
# The reference a case is compared with: the described case with the fewest brute facts.
REF = min(OVERVIEW["cases"], key=lambda c: len(c["facts"]))
BUNDLE_STATUS = M.bundle_statuses()


def reference(readings: list[str]) -> dict:
    return S.run(REF["facts"], REF["roleAssignments"], readings)


# Self-check: re-deriving every described case must reproduce the bundle.
SELF_CHECK = {c["id"]: sorted(n for n, s in BUNDLE_STATUS[c["id"]].items()
                              if S.run(c["facts"], c["roleAssignments"], [])["status"].get(n) != s)
              for c in OVERVIEW["cases"]}
SELF_CHECK = {k: v for k, v in SELF_CHECK.items() if v}
for r in variants:                    # warm the per-reading runs the norm sheets show
    for c in OVERVIEW["cases"]:
        S.run(c["facts"], c["roleAssignments"], [r])
print(f"[norma-web] {M.bundle.name}: {len(M.G)} triples, {len(CASES)} cases, readings {list(variants) or '-'}; "
      f"ready in {time.time() - t0:.1f}s; self-check: {'all cases reproduced' if not SELF_CHECK else SELF_CHECK}")


def statuses_of(norm_id: str) -> dict:
    """norm's status in every described case, per reading."""
    out = {"Base reading": {c: BUNDLE_STATUS[c].get(norm_id, "—") for c in CASES}}
    for r in variants:
        out[r] = {c: S.run(CASES[c]["facts"], CASES[c]["roleAssignments"], [r])["status"].get(norm_id, "—") for c in CASES}
    return out


def query_catalogue() -> list:
    views = [("Norms addressed to a role", M.Q_ROLE_NORMS, ["role"]),
             ("Hohfeldian positions held by a role (derived)", M.Q_ROLE_POSITIONS, ["role"]),
             ("Deontic closure of a norm (derived)", M.Q_CLOSURE, ["norm"]),
             ("Positions a norm confers, with their correlatives", M.Q_POSITIONS, ["norm"]),
             ("What overrides a norm, and what it overrides", M.Q_DEFEAT, ["norm"]),
             ("Conditions that activate a norm", M.Q_ACTIVATION, ["norm"]),
             ("Deontic relations of a norm (derived)", M.Q_RELATIONS, ["norm"]),
             ("Status of every norm in a case", M.Q_CASE_STATUS, ["case"])]
    more = []
    for p in sorted((ROOT / "queries").glob("*.rq")):
        lines = p.read_text(encoding="utf-8").splitlines()
        title = lines[0].lstrip("# ").strip()
        title = re.sub(r"\s*\(--bind case=\w+\)", "", title)
        more.append((title, "\n".join(lines[1:]).strip(), ["case"] if "--bind case" in lines[0] else []))
    return ([{"group": "Behind the views", "title": t, "sparql": s.strip(), "binds": b} for t, s, b in views]
            + [{"group": "More questions", "title": t, "sparql": s, "binds": b} for t, s, b in more])


# ── HTTP ─────────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=str(HERE / "static"), static_url_path="/static")


@app.get("/")
def index():
    return send_from_directory(HERE / "static", "index.html")


@app.get("/api/overview")
def api_overview():
    return jsonify({**OVERVIEW, "referenceCase": REF["id"], "baseline": reference([]), "selfCheck": SELF_CHECK,
                    "queries": query_catalogue()})


@app.get("/api/role/<path:rid>")
def api_role(rid):
    return jsonify(M.role(rid))


@app.get("/api/norm/<path:nid>")
def api_norm(nid):
    try:
        return jsonify(M.norm(nid, statuses_of(nid)))
    except KeyError:
        abort(404, f"{nid} is not a norm of the graph")


@app.get("/api/node/<path:name>")
def api_node(name):
    try:
        return jsonify(M.node(name, request.args.get("collapse", "1") == "1", request.args.get("derived", "0") == "1",
                              {CASES[c]["label"]: s.get(name) for c, s in BUNDLE_STATUS.items() if s.get(name)}))
    except KeyError:
        abort(404, f"{name} is not in the graph")


@app.get("/api/search")
def api_search():
    return jsonify(M.search(request.args.get("q", "")) if request.args.get("q", "").strip() else [])


@app.post("/api/simulate")
def api_simulate():
    body = request.get_json(force=True)
    readings = body.get("readings", [])
    r = S.run(body.get("facts", []), body.get("roles", OVERVIEW["defaultRA"]), readings)
    return jsonify({**r, "steps": S.explain(r, reference(readings))})


@app.get("/api/exceptions")
def api_exceptions():
    return jsonify(M.exceptions())


@app.get("/api/source")
def api_source():
    return jsonify(M.source())


@app.get("/files/<which>")
def files(which):
    paths = {"annotation": M.annotation, "bundle": M.bundle, **{f"reading-{i}": p for i, p in enumerate(variants.values())}}
    if which not in paths or paths[which] is None:
        abort(404)
    return send_file(paths[which], as_attachment=True, download_name=paths[which].name, mimetype="text/turtle")


READ_ONLY = re.compile(r"^\s*(?:(?:PREFIX|BASE)\b[^\n]*\n\s*)*(?:#[^\n]*\n\s*)*(SELECT|ASK|CONSTRUCT|DESCRIBE)\b", re.I)


@app.post("/api/sparql")
def api_sparql():
    body = request.get_json(force=True)
    query = body.get("query", "")
    if not READ_ONLY.match(M.prefixes + query):
        return jsonify({"error": "Only SELECT, ASK, CONSTRUCT and DESCRIBE queries are allowed."}), 400
    t = time.time()
    try:
        res = S.raw_query(M.G, M.prefixes + query, initBindings={k: M.full(v) for k, v in (body.get("bind") or {}).items() if v})
    except Exception as e:  # syntax or evaluation error: shown to the user as is
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 400
    took = round(time.time() - t, 2)
    if res.type == "ASK":
        return jsonify({"cols": ["ask"], "rows": [[str(res.askAnswer)]], "seconds": took})
    if res.type in ("CONSTRUCT", "DESCRIBE"):
        return jsonify({"cols": ["subject", "predicate", "object"], "rows": [[M.short(s), M.short(p), M.short(o)] for s, p, o in res.graph], "seconds": took})
    cols = [str(v) for v in res.vars]
    return jsonify({"cols": cols, "rows": [[M.short(r[c]) for c in cols] for r in res], "seconds": took})


if __name__ == "__main__":
    app.run(host=ARGS.host, port=ARGS.port, debug=False, threaded=True)
