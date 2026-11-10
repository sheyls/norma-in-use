"""Case simulation with the REAL rule set (deriv/derive.py of the installed norma-o package).

A case is a set of brute facts (conditions that hold) and role assignments,
under one legal reading. The simulator builds that case, derives it, and
returns the status of every norm together with a step-by-step explanation of
how the result was reached.
"""
from __future__ import annotations

import sys
import tempfile
import threading
import time
from collections import defaultdict
from pathlib import Path

import norma_o
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS

from model import NORMA, NORMAD, NORM_KINDS, Model


class Simulator:
    def __init__(self, model: Model):
        sys.path.insert(0, str(norma_o.HOME / "deriv"))
        import derive  # the release's rule set, used as is
        self.derive, self.m = derive, model
        self.lock, self.cache, self.lookups = threading.Lock(), {}, {}
        abox = Graph()
        for t in model.abox:
            abox.add(t)
        for case in list(abox.subjects(RDF.type, NORMA.FactPattern)):   # a run evaluates only the simulated case
            abox.remove((case, None, None))
        self.abox_ttl = abox.serialize(format="turtle")
        self.variant_ttl = {k: p.read_text(encoding="utf-8") for k, p in model.variants_path.items()}
        self._memo_05a(norma_o.HOME)
        self.reference = None

    def _memo_05a(self, ontology_dir: Path) -> None:
        """Rule 05a (deontic equivalence) is ~95% of a run and never looks at a
        case, so its result is computed once per reading. derive.py is untouched."""
        rule = (ontology_dir / "deriv" / "rules" / "05a-deontic-equivalence.rq").read_text(encoding="utf-8")
        original, memo, current = Graph.query, {}, self

        def query(g, q, *a, **k):
            if isinstance(q, str) and q == rule:
                key = current._reading
                if key not in memo:
                    memo[key] = list(original(g, q, *a, **k))
                return memo[key]
            return original(g, q, *a, **k)
        self._reading = ()
        Graph.query = query
        self.raw_query = original

    def lookup(self, readings: tuple) -> Graph:
        if readings not in self.lookups:
            g = Graph()
            for t in self.m.G:
                g.add(t)
            for r in readings:
                for t in self.m.variant_g[r]:
                    g.add(t)
            self.lookups[readings] = g
        return self.lookups[readings]

    def run(self, facts: list[str], roles: list[str], readings: list[str]) -> dict:
        readings = tuple(sorted(r for r in readings if r in self.m.variant_g))
        key = (frozenset(facts), frozenset(roles), readings)
        if key not in self.cache:
            self.cache[key] = self._run(facts, roles, readings)
        return self.cache[key]

    def _run(self, facts, roles, readings) -> dict:
        m, t0 = self.m, time.time()
        look = self.lookup(readings)
        case = URIRef(m.sim_ns + "SimCase")
        cg = Graph()
        cg.add((case, RDF.type, NORMA.FactPattern)); cg.add((case, RDFS.label, Literal("simulated case")))
        for f in facts:
            for te in look.objects(m.full(f), NORMA.hasTrigger):
                if look.value(te, NORMA.hasOutcome) == NORMA.TrueOutcome:
                    cg.add((case, NORMA.holdsTrigger, te))
        for ra in roles:
            cg.add((case, NORMA.holdsRoleAssignment, m.full(ra)))
        with self.lock, tempfile.TemporaryDirectory() as td:
            a, c = Path(td) / "abox.ttl", Path(td) / "case.ttl"
            a.write_text(self.abox_ttl + "".join("\n" + self.variant_ttl[r] for r in readings), encoding="utf-8")
            cg.serialize(c, format="turtle")
            self._reading = readings
            res = self.derive.derive([a, c], False, m.sim_ns)
        derived, chained, unsound_roles = res[0], res[11], res[12]

        order = URIRef(m.sim_ns + "ordering_SimCase")
        status, reach = {}, defaultdict(set)
        for ev in derived.subjects(NORMAD.inOrdering, order):
            n = m.short(derived.value(ev, NORMAD.evaluatedNorm))
            status[n] = m.short(derived.value(ev, NORMAD.hasApplicabilityStatus)).split(":")[-1]
            reach[n] |= {m.short(p) for p in derived.objects(ev, NORMAD.reachesParty)}
        held = set(cg.objects(case, NORMA.holdsTrigger))
        cond_of = lambda te: next(look.subjects(NORMA.hasTrigger, te), None)
        institutional = sorted({m.short(cond_of(te)) for te in chained if cond_of(te) is not None}
                               - {m.short(cond_of(te)) for te in held if cond_of(te) is not None})
        attackers = defaultdict(set)
        for a_, b_ in look.subject_objects(NORMA.isExceptionTo):
            attackers[m.short(b_)].add(m.short(a_))
        for d in look.subjects(NORMA.defeatingNorm, None):
            for b_ in look.objects(d, NORMA.defeatedNorm):
                attackers[m.short(b_)].add(m.short(look.value(d, NORMA.defeatingNorm)))
        why = {n: sorted(x for x in attackers.get(n, ()) if status.get(x) == "Applicable")
               for n, s in status.items() if s in ("Defeated", "Undecided")}
        # What activated each activated norm in this case (a brute or an institutional fact).
        activated_by = defaultdict(set)
        for te in held | set(chained):
            n, c = look.value(te, NORMA.activatesNorm), cond_of(te)
            if n is not None and c is not None:
                activated_by[m.short(n)].add(m.short(c))
        established_by = defaultdict(set)
        for te in chained:
            c = cond_of(te)
            for r in look.subjects(NORMA.establishesTrigger, te):
                if status.get(m.short(r)) == "Applicable" and c is not None:
                    established_by[m.short(c)].add(m.short(r))

        positions = defaultdict(list)
        for n, s in status.items():
            if s != "Applicable":
                continue
            nu, agent = m.full(n), look.value(m.full(n), NORMA.hasLegalAgent)
            for pos in derived.objects(nu, NORMA.confersLegalPosition):
                kind = m.short(derived.value(pos, RDF.type)).split(":")[-1]
                if kind in ("Duty", "Privilege") and derived.value(pos, NORMA.hasPositionHolder) == agent:
                    act = derived.value(pos, NORMA.concernsLegalAction)
                    for party in sorted(reach.get(n, ())):
                        positions[party].append({"kind": kind, "norm": n, "action": m.action_label(act, look) or m.action_label(act)})
        weak = defaultdict(list)
        for wp in derived.subjects(RDF.type, NORMA.WeakPermission):
            weak[m.short(derived.value(wp, NORMA.forAgent))].append(m.action_label(derived.value(wp, NORMA.aboutAction), look))
        return {"status": status, "institutional": institutional, "why": why,
                "activatedBy": {k: sorted(v) for k, v in activated_by.items()},
                "establishedBy": {k: sorted(v) for k, v in established_by.items()},
                "positions": {k: sorted(v, key=lambda x: (x["kind"], x["norm"])) for k, v in positions.items()},
                "weak": {k: sorted(v) for k, v in weak.items()}, "readings": list(readings),
                "warnings": [f"The role assignment {m.label(m.full(ra))} rests on a rule that is {st.lower()} in this case."
                             for _, ra, rule, st in unsound_roles],
                "seconds": round(time.time() - t0, 2)}

    def explain(self, r: dict, reference: dict) -> list:
        """The result as numbered steps a reader can follow."""
        m, base = self.m, reference["status"]
        changed = lambda n: r["status"].get(n) != base.get(n)
        fired = sorted({x for xs in r["establishedBy"].values() for x in xs}
                       | {a for n, xs in r["why"].items() if changed(n) for a in xs})
        steps = []
        if r["institutional"] or fired:
            steps.append({"title": "Rules that fire", "items": [
                {"id": f, "text": m.reading(m.full(f)), "because": [m.label(m.full(c)) for c in r["activatedBy"].get(f, [])]}
                for f in fired]})
        if r["institutional"]:
            steps.append({"title": "Facts they establish", "items": [
                {"id": c, "text": m.label(m.full(c)), "because": [m.reading(m.full(x)) for x in r["establishedBy"].get(c, [])],
                 "fact": True} for c in r["institutional"]]})
        starts = sorted(n for n, s in r["status"].items() if s == "Applicable" and base.get(n) != "Applicable" and m.kind(m.full(n)) != "ConstitutiveRule")
        stops = sorted(n for n, s in r["status"].items() if s != "Applicable" and base.get(n) == "Applicable" and m.kind(m.full(n)) != "ConstitutiveRule")
        steps.append({"title": "Consequences", "starts": [
            {"id": n, "text": m.reading(m.full(n)), "because": [m.label(m.full(c)) for c in r["activatedBy"].get(n, [])]} for n in starts],
            "stops": [{"id": n, "text": m.reading(m.full(n)), "status": r["status"][n],
                       "because": [m.reading(m.full(a)) for a in r["why"].get(n, [])]} for n in stops]})
        return steps
