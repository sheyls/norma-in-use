"""The loaded example: the bundle (annotation + derivation), its alternative
readings and its Turtle source, and every read-only view the explorer shows.

All views come from the graph. Those a reader may want to reproduce return the
SPARQL query that computes them (`queries`), so the explorer can open it.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

import norma_o
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS

import text
from extract_abox import DERIVED_PREDICATES, extract

NORMA = Namespace("https://w3id.org/def/norma-o#")
NORMAD = Namespace("https://w3id.org/def/norma-o/deriv#")
GAP = Namespace("https://example.org/norma-gap#")
REGULATIVE = ["Obligation", "Prohibition", "Permission", "Facultative", "Recommendation", "NegativeRecommendation"]
NORM_KINDS = REGULATIVE + ["ConstitutiveRule"]
DERIVED_GROUPS = {"Evaluation", "WeakPermission", "Ordering", "Duty", "Claim", "Privilege", "NoRight"}
GROUPS = [(NORMA.LegalCondition, "Condition"), (NORMA.TriggerEvent, "Trigger"), (NORMA.LegalAction, "Action"),
          (NORMA.LegalRole, "Role"), (NORMA.LegalParty, "Party"), (NORMA.RoleAssignment, "RoleAssignment"),
          (NORMA.FactPattern, "Case"), (NORMA.Duty, "Duty"), (NORMA.Claim, "Claim"), (NORMA.Privilege, "Privilege"),
          (NORMA.NoRight, "NoRight"), (NORMA.ExceptionDefeater, "Defeater"), (NORMA.ConflictDefeater, "Defeater"),
          (NORMA.TemporalDefeater, "Defeater"), (NORMA.WeakPermission, "WeakPermission"),
          (NORMAD.NormEvaluation, "Evaluation"), (NORMAD.PrevalenceOrdering, "Ordering"), (GAP.Gap, "Gap"),
          (NORMA.LegalObject, "Object"), (NORMA.LegalSource, "Source"), (NORMA.LegalSourceExpression, "Expression"),
          (NORMA.AnnotatorAgent, "Annotator"), (NORMA.AnnotationActivity, "Activity")]
GROUP_NAME = {"Obligation": "Obligation", "Prohibition": "Prohibition", "Permission": "Permission", "Facultative": "Faculty",
              "Recommendation": "Recommendation", "NegativeRecommendation": "Negative recommendation",
              "ConstitutiveRule": "Constitutive rule", "Condition": "Condition", "Trigger": "Trigger", "Action": "Action",
              "Role": "Role", "Party": "Party", "RoleAssignment": "Role assignment", "Case": "Case", "Duty": "Duty",
              "Claim": "Claim", "Privilege": "Privilege", "NoRight": "No-right", "Defeater": "Defeater",
              "WeakPermission": "Weak permission", "Evaluation": "Evaluation", "Ordering": "Prevalence ordering",
              "Gap": "Gap", "Object": "Object", "Source": "Legal source", "Expression": "Source version",
              "Annotator": "Annotator", "Activity": "Annotation activity", "Other": "Other"}


def natural(s: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def section_key(s: str | None):
    nums = re.findall(r"\d+", (s or "").split(",")[0])
    return tuple(int(x) for x in nums[:3]) or (999,)


class Model:
    def __init__(self, bundle: Path, annotation: Path | None, variants: dict[str, Path], title: str | None):
        self.bundle, self.annotation, self.variants_path = bundle, annotation, variants
        self.tbox = [norma_o.ONTOLOGY, norma_o.MODULE]      # what the bundle imports, from the installed package
        self.G = Graph()
        for p in self.tbox + [bundle]:
            self.G.parse(p, format="turtle")
        self.tbox_subjects = set()
        for p in self.tbox:
            self.tbox_subjects |= set(Graph().parse(p).subjects())
        ns = lambda u: str(u)[: str(u).rfind("#") + 1]
        self.base = Counter(ns(n) for k in NORM_KINDS for n in self.G.subjects(RDF.type, NORMA[k])).most_common(1)[0][0]
        dg = next(self.G.objects(None, NORMAD.derivedGraph), None)
        self.derived_ns = (str(dg).rstrip("#") + "#") if dg is not None else self.base.rstrip("#") + "/derived#"
        self.sim_ns = self.base.rstrip("#") + "/sim#"
        for pre, n in (("", self.base), ("der", self.derived_ns), ("gap", str(GAP)), ("normad", str(NORMAD))):
            self.G.bind(pre, Namespace(n), override=True)
        self.prefixes = "".join(f"PREFIX {p}: <{n}>\n" for p, n in (
            ("", self.base), ("der", self.derived_ns), ("norma", NORMA), ("normad", NORMAD), ("gap", GAP),
            ("rdf", RDF), ("rdfs", RDFS), ("owl", OWL), ("skos", "http://www.w3.org/2004/02/skos/core#"),
            ("prov", "http://www.w3.org/ns/prov#"), ("xsd", "http://www.w3.org/2001/XMLSchema#")))
        self.abox = extract(bundle)                       # the annotation, without what derive.py produced
        self.variant_g = {k: Graph().parse(p) for k, p in variants.items()}
        self.full_g = Graph()                             # bundle + every reading, for labels and lookups
        for t in self.G:
            self.full_g.add(t)
        for g in self.variant_g.values():
            for t in g:
                self.full_g.add(t)
        onto = next((s for s in self.abox.subjects(RDF.type, OWL.Ontology)), None)
        self.title = title or (str(self.abox.value(onto, RDFS.label)) if onto is not None and self.abox.value(onto, RDFS.label)
                               else bundle.stem)

    # ── identifiers and names ────────────────────────────────────────────────
    def short(self, u) -> str:
        if u is None:
            return ""
        if isinstance(u, Literal):
            return str(u)
        s = str(u)
        for pre in (self.derived_ns, self.base, self.sim_ns):
            if s.startswith(pre):
                return s[len(pre):]
        try:
            return self.G.namespace_manager.curie(u)
        except Exception:
            return s

    def full(self, name: str) -> URIRef:
        if name.startswith("http"):
            return URIRef(name)
        if ":" in name:
            pre, local = name.split(":", 1)
            n = dict(self.G.namespaces()).get(pre)
            if n is not None:
                return URIRef(str(n) + local)
        return URIRef(self.base + name)

    def label(self, u, g: Graph | None = None) -> str:
        """A readable name for any node; an identifier only when the graph says nothing else."""
        g = g or self.full_g
        pos_kind = next((k for k in ("Duty", "Claim", "Privilege", "NoRight") if (u, RDF.type, NORMA[k]) in g), None)
        if pos_kind:                                   # "duty of Tenant: pay the rent"
            holder = g.value(u, NORMA.hasPositionHolder)
            act = g.value(u, NORMA.concernsLegalAction) or g.value(g.value(u, NORMA.isCorrelativeOf), NORMA.concernsLegalAction)
            return f"{text.POSITION[pos_kind]} of {self.label(holder, g) if holder is not None else '?'}" + (f": {self.action_label(act, g)}" if act is not None else "")
        for p in (RDFS.label, NORMA.regulationName, NORMA.normStatement, NORMA.factStatement, NORMA.conditionStatement):
            v = g.value(u, p)
            if v is not None:
                return str(v)
        if (u, RDF.type, NORMA.RoleAssignment) in g:
            p_, r_ = g.value(u, NORMA.hasAssignedParty), g.value(u, NORMA.hasAssignedRole)
            if p_ is not None and r_ is not None:
                return f"{self.label(p_, g)} as {self.label(r_, g)}"
        if (u, RDF.type, GAP.Gap) in g and g.value(u, GAP.category) is not None:
            return f"{g.value(u, GAP.category)}: {g.value(u, GAP.missing) or ''}".rstrip(": ")
        if (u, RDF.type, NORMA.TriggerEvent) in g:
            c = next(g.subjects(NORMA.hasTrigger, u), None)
            if c is not None:
                n = g.value(u, NORMA.activatesNorm)
                what = (self.action_label(g.value(n, NORMA.hasLegalAction), g) or self.label(n, g)[:60]) if n is not None else ""
                return ("if " if g.value(u, NORMA.hasOutcome) != NORMA.FalseOutcome else "if not: ") + self.label(c, g) + (f" → activates: {what}" if what else "")
        return self.short(u)

    def action_label(self, u, g: Graph | None = None) -> str:
        """An action's label; the negation the rule set mints reads 'not …'."""
        if u is None:
            return ""
        g = g or self.full_g
        lab = g.value(u, RDFS.label)
        if lab is not None and not str(lab).startswith("not "):
            return str(lab)
        pos = g.value(u, NORMA.isNegationOf)
        if pos is not None and str(u).endswith("_neg"):
            return "not " + self.action_label(pos, g)
        return str(lab) if lab is not None else self.short(u)

    def kind(self, u, g: Graph | None = None) -> str:
        g = g or self.full_g
        return next((k for k in NORM_KINDS if (u, RDF.type, NORMA[k]) in g), "")

    def group(self, u) -> str:
        types = set(self.full_g.objects(u, RDF.type))
        k = next((k for k in NORM_KINDS if NORMA[k] in types), None)
        return k or next((g for t, g in GROUPS if t in types), "Other")

    def reading(self, u, g: Graph | None = None) -> str:
        g = g or self.full_g
        k = self.kind(u, g)
        if k == "ConstitutiveRule":
            return str(g.value(u, NORMA.factStatement) or self.short(u))
        lab = lambda p: self.label(g.value(u, p), g) if g.value(u, p) is not None else ""
        return text.reading(k, lab(NORMA.hasLegalAgent), lab(NORMA.hasCounterparty),
                            self.action_label(g.value(u, NORMA.hasLegalAction), g))

    def short_label(self, u) -> str:
        act = self.full_g.value(u, NORMA.hasLegalAction)
        if act is not None:
            return self.action_label(act)
        if (u, RDF.type, NORMA.LegalAction) in self.full_g:
            return self.action_label(u)
        return self.label(u)

    def brief(self, u) -> dict:
        g = self.full_g
        stmt = g.value(u, NORMA.normStatement) or g.value(u, NORMA.factStatement)
        return {"id": self.short(u), "kind": self.kind(u), "reading": self.reading(u), "statement": str(stmt or ""),
                "section": str(g.value(u, NORMA.fromArticle) or ""), "short": self.short_label(u)[:80],
                "agent": self.short(g.value(u, NORMA.hasLegalAgent)), "counterparty": self.short(g.value(u, NORMA.hasCounterparty)),
                "variant": next((v for v, vg in self.variant_g.items() if (u, RDF.type, None) in vg and (u, RDF.type, None) not in self.G), None)}

    def query(self, sparql: str, g: Graph | None = None, **bind):
        res = (g or self.G).query(self.prefixes + sparql, initBindings={k: self.full(v) if isinstance(v, str) else v for k, v in bind.items()})
        return [{str(v): r[v] for v in res.vars} for r in res]

    # ── overview ─────────────────────────────────────────────────────────────
    def ontology_info(self) -> dict:
        """Name, version, repository, licence and DOI, as the local ontology file declares them."""
        g = Graph().parse(self.tbox[0])
        o = next(g.subjects(RDF.type, OWL.Ontology))
        v = lambda p: str(g.value(o, p) or "")
        lic = v(DCTERMS.license)
        return {"title": v(DCTERMS.title), "version": v(OWL.versionInfo), "iri": str(o), "repo": v(DCTERMS.source),
                "license": lic, "licenseName": "CC BY 4.0" if "licenses/by/4.0" in lic else lic,
                "doi": v(URIRef("http://purl.org/ontology/bibo/doi"))}

    def overview(self) -> dict:
        g = self.full_g
        norms = sorted((self.brief(n) for k in NORM_KINDS for n in set(g.subjects(RDF.type, NORMA[k]))),
                       key=lambda n: (section_key(n["section"]), n["id"]))
        established = set(g.objects(None, NORMA.establishesTrigger))
        conditions = []
        for c in self.G.subjects(RDF.type, NORMA.LegalCondition):
            tes = list(self.G.objects(c, NORMA.hasTrigger))
            secs = sorted({str(self.G.value(self.G.value(te, NORMA.activatesNorm), NORMA.fromArticle) or "") for te in tes} - {""},
                          key=section_key)
            conditions.append({"id": self.short(c), "statement": self.label(c),
                               "activates": sorted({self.short(self.G.value(te, NORMA.activatesNorm)) for te in tes} - {""}),
                               "sections": secs, "institutional": any(te in established for te in tes),
                               "establishedBy": sorted({self.short(r) for te in tes for r in self.G.subjects(NORMA.establishesTrigger, te)})})
        conditions.sort(key=lambda c: (section_key(c["sections"][0] if c["sections"] else ""), c["id"]))
        cases = sorted(({"id": self.short(c), "label": self.label(c),
                         "facts": sorted({self.short(cond) for te in self.G.objects(c, NORMA.holdsTrigger)
                                          for cond in self.G.subjects(NORMA.hasTrigger, te)}),
                         "roleAssignments": sorted(self.short(ra) for ra in self.G.objects(c, NORMA.holdsRoleAssignment))}
                        for c in self.G.subjects(RDF.type, NORMA.FactPattern)), key=lambda c: natural(c["label"]))
        held = [set(c["roleAssignments"]) for c in cases]
        gaps = defaultdict(list)
        for gp in self.G.subjects(RDF.type, GAP.Gap):
            for n in self.G.objects(gp, GAP.representedAs):
                gaps[self.short(n)].append({"category": str(self.G.value(gp, GAP.category) or ""),
                                            "missing": str(self.G.value(gp, GAP.missing) or "")})
        roles = [{"id": self.short(r), "label": self.label(r),
                  "parties": sorted({self.label(self.G.value(ra, NORMA.hasAssignedParty)) for ra in self.G.subjects(NORMA.hasAssignedRole, r)})}
                 for r in sorted(self.G.subjects(RDF.type, NORMA.LegalRole), key=str)]
        labels = {self.short(s): self.label(s) for s in set(g.subjects(RDF.type, None))
                  if isinstance(s, URIRef) and s not in self.tbox_subjects and self.group(s) not in DERIVED_GROUPS}
        return {"title": self.title, "ontology": self.ontology_info(), "norms": norms, "conditions": conditions, "cases": cases, "roles": roles,
                "defaultRA": sorted(set.intersection(*held)) if held else [], "gaps": dict(gaps), "labels": labels,
                "variants": list(self.variant_g), "triples": len(self.G), "bundle": self.bundle.name,
                "annotationFile": self.annotation.name if self.annotation else None}

    # ── role ─────────────────────────────────────────────────────────────────
    Q_ROLE_NORMS = """
SELECT ?norm ?type ?action ?counterparty ?section WHERE {
  ?norm norma:hasLegalAgent ?role ; a ?t .
  VALUES ?t { norma:Obligation norma:Prohibition norma:Permission norma:Facultative
              norma:Recommendation norma:NegativeRecommendation }
  BIND(STRAFTER(STR(?t), "#") AS ?type)
  OPTIONAL { ?norm norma:hasLegalAction ?action }
  OPTIONAL { ?norm norma:hasCounterparty ?counterparty }
  OPTIONAL { ?norm norma:fromArticle ?section }
} ORDER BY ?section ?norm"""
    Q_ROLE_POSITIONS = """
SELECT ?position ?kind ?norm ?content ?other WHERE {
  ?position norma:hasPositionHolder ?role ; a ?k .
  VALUES ?k { norma:Duty norma:Claim norma:Privilege norma:NoRight }
  BIND(STRAFTER(STR(?k), "#") AS ?kind)
  ?norm norma:confersLegalPosition ?position .
  OPTIONAL { ?position norma:concernsLegalAction ?c1 }
  OPTIONAL { ?position norma:isCorrelativeOf ?corr .
             OPTIONAL { ?corr norma:concernsLegalAction ?c2 }
             ?corr norma:hasPositionHolder ?other }
  BIND(COALESCE(?c1, ?c2) AS ?content)
} ORDER BY ?kind ?norm"""

    def role(self, rid: str) -> dict:
        role = self.full(rid)
        norms = [self.brief(r["norm"]) for r in self.query(self.Q_ROLE_NORMS, role=role)]
        positions = [{"kind": str(r["kind"]), "norm": self.short(r["norm"]), "normKind": self.kind(r["norm"]),
                      "normShort": self.short_label(r["norm"]), "content": self.action_label(r["content"]),
                      "other": self.label(r["other"]) if r["other"] is not None else ""}
                     for r in self.query(self.Q_ROLE_POSITIONS, role=role)]
        return {"id": self.short(role), "label": self.label(role), "norms": norms, "positions": positions,
                "parties": sorted({self.label(self.G.value(ra, NORMA.hasAssignedParty)) for ra in self.G.subjects(NORMA.hasAssignedRole, role)}),
                "queries": {"norms": self.Q_ROLE_NORMS.strip(), "positions": self.Q_ROLE_POSITIONS.strip()}}

    # ── norm sheet ───────────────────────────────────────────────────────────
    Q_CLOSURE = """
SELECT ?operator ?action WHERE {
  ?norm ?p ?action .
  FILTER(STRSTARTS(STR(?p), "https://w3id.org/def/norma-o#entails"))
  BIND(STRAFTER(STR(?p), "#entails") AS ?operator)
}"""
    Q_POSITIONS = """
SELECT ?position ?kind ?holder ?content ?correlative ?corrKind ?corrHolder WHERE {
  ?norm norma:confersLegalPosition ?position .
  ?position a ?k ; norma:hasPositionHolder ?holder .
  VALUES ?k { norma:Duty norma:Privilege } BIND(STRAFTER(STR(?k), "#") AS ?kind)
  OPTIONAL { ?position norma:concernsLegalAction ?content }
  OPTIONAL { ?position norma:isCorrelativeOf ?correlative . ?correlative a ?ck ; norma:hasPositionHolder ?corrHolder .
             VALUES ?ck { norma:Claim norma:NoRight } BIND(STRAFTER(STR(?ck), "#") AS ?corrKind) }
}"""
    Q_DEFEAT = """
SELECT ?direction ?other ?gate WHERE {
  { ?other norma:isExceptionTo ?norm . BIND("overridden by" AS ?direction) }
  UNION { ?norm norma:isExceptionTo ?other . BIND("overrides" AS ?direction) }
  UNION { ?d norma:defeatingNorm ?other ; norma:defeatedNorm ?norm . BIND("overridden by" AS ?direction)
          OPTIONAL { ?d norma:appliesWhen ?g . ?gate norma:hasTrigger ?g } }
  UNION { ?d norma:defeatingNorm ?norm ; norma:defeatedNorm ?other . BIND("overrides" AS ?direction)
          OPTIONAL { ?d norma:appliesWhen ?g . ?gate norma:hasTrigger ?g } }
}"""
    Q_ACTIVATION = """
SELECT ?condition ?outcome WHERE {
  ?condition norma:hasTrigger ?te . ?te norma:activatesNorm ?norm ; norma:hasOutcome ?o .
  BIND(STRAFTER(STR(?o), "#") AS ?outcome)
}"""
    Q_RELATIONS = """
SELECT ?relation ?other WHERE {
  { ?norm norma:deonticallyContradicts ?other . BIND("contradicts" AS ?relation) }
  UNION { ?norm norma:deonticallyConflictsWith ?other . FILTER NOT EXISTS { ?norm norma:deonticallyContradicts ?other }
          BIND("is contrary to" AS ?relation) }
  UNION { ?norm norma:isDeonticallyEquivalentTo ?other . BIND("is equivalent to" AS ?relation) }
}"""
    Q_CASE_STATUS = """
SELECT ?norm ?status WHERE {
  ?ordering normad:forFactPattern ?case .
  ?e normad:inOrdering ?ordering ; normad:evaluatedNorm ?norm ; normad:hasApplicabilityStatus ?s .
  BIND(STRAFTER(STR(?s), "#") AS ?status)
} ORDER BY ?status ?norm"""

    def norm(self, nid: str, statuses: dict) -> dict:
        u, g = self.full(nid), self.full_g
        if (u, RDF.type, None) not in g:
            raise KeyError(nid)
        b = self.brief(u)
        own = {"Obligation": "Obligatory", "Prohibition": "Forbidden", "Permission": "Permitted", "Facultative": "Permitted",
               "Recommendation": "Recommended", "NegativeRecommendation": "Discouraged"}.get(b["kind"])
        act = g.value(u, NORMA.hasLegalAction)
        closure = []
        for r in self.query(self.Q_CLOSURE, g, norm=u):
            sym, meaning = text.CLOSURE.get(str(r["operator"]), (str(r["operator"]), str(r["operator"])))
            closure.append({"symbol": sym, "action": self.action_label(r["action"]), "meaning": meaning,
                            "annotated": str(r["operator"]) == own and r["action"] == act})
        closure.sort(key=lambda c: (not c["annotated"], c["symbol"]))
        positions = [{"kind": text.POSITION.get(str(r["kind"]), ""), "holder": self.label(r["holder"]),
                      "content": self.action_label(r["content"]),
                      "correlative": f"{text.POSITION.get(str(r['corrKind']), '')} of {self.label(r['corrHolder'])}"
                      if r["correlative"] is not None else ""} for r in self.query(self.Q_POSITIONS, g, norm=u)]
        defeat = [{"direction": str(r["direction"]), "other": self.brief(r["other"]),
                   "gate": self.label(r["gate"]) if r["gate"] is not None else "",
                   "onlyIn": next((v for v, vg in self.variant_g.items() if (r["other"], NORMA.isExceptionTo, u) in vg
                                   or (u, NORMA.isExceptionTo, r["other"]) in vg), None)} for r in self.query(self.Q_DEFEAT, g, norm=u)]
        established = set(g.objects(None, NORMA.establishesTrigger))
        when = [{"condition": self.short(r["condition"]), "text": self.label(r["condition"]),
                 "holds": str(r["outcome"]) == "TrueOutcome",
                 "institutional": any(te in established for te in g.objects(r["condition"], NORMA.hasTrigger))}
                for r in self.query(self.Q_ACTIVATION, g, norm=u)]
        src, activity = g.value(u, NORMA.hasLegalSource), g.value(u, NORMA.wasGeneratedByAnnotationActivity)
        local = lambda x: self.short(x).split(":")[-1] if x is not None else ""
        return {**b,
                "agent": self.label(g.value(u, NORMA.hasLegalAgent)) if g.value(u, NORMA.hasLegalAgent) else "",
                "counterparty": self.label(g.value(u, NORMA.hasCounterparty)) if g.value(u, NORMA.hasCounterparty) else "",
                "action": self.action_label(act) if act is not None else "",
                "deadline": str(g.value(u, NORMA.deadline) or ""), "comment": str(g.value(u, RDFS.comment) or ""),
                "bindingForce": local(g.value(u, NORMA.hasBindingForce)), "strength": local(g.value(u, NORMA.hasNormStrength)),
                "when": when, "defeat": defeat, "closure": closure, "positions": positions,
                "establishes": [self.label(c) for te in g.objects(u, NORMA.establishesTrigger) for c in g.subjects(NORMA.hasTrigger, te)],
                "relations": [{"relation": str(r["relation"]), "other": self.brief(r["other"])} for r in self.query(self.Q_RELATIONS, g, norm=u)],
                "gaps": [{"category": str(g.value(gp, GAP.category) or ""), "missing": str(g.value(gp, GAP.missing) or "")}
                         for gp in g.subjects(GAP.representedAs, u)],
                "provenance": {
                    "source": self.label(src) if src is not None else "",
                    "rank": local(g.value(src, NORMA.hasRank)) if src is not None else "",
                    "versions": sorted(self.label(e) for e in g.objects(src, NORMA.hasSourceExpression)) if src is not None else [],
                    "status": local(g.value(u, NORMA.hasNormStatus)), "review": local(g.value(u, NORMA.hasReviewStatus)),
                    "method": local(g.value(u, NORMA.hasExtractionMethod)),
                    "annotators": sorted(self.label(a) for a in g.objects(u, NORMA.wasAttributedToAnnotator)),
                    "activity": self.label(activity) if activity is not None else "",
                    "date": str(g.value(activity, NORMA.annotationDate) or "") if activity is not None else ""},
                "statuses": statuses, "sourceLine": self.source_line(b["id"]),
                "queries": {"closure": self.Q_CLOSURE.strip(), "positions": self.Q_POSITIONS.strip(), "defeat": self.Q_DEFEAT.strip(),
                            "activation": self.Q_ACTIVATION.strip(), "relations": self.Q_RELATIONS.strip(), "caseStatus": self.Q_CASE_STATUS.strip()}}

    def bundle_statuses(self) -> dict:
        """case -> norm -> status, as stored in the bundle (base reading)."""
        out = defaultdict(dict)
        for r in self.query("""SELECT ?c ?n ?s WHERE { ?o normad:forFactPattern ?c . ?e normad:inOrdering ?o ;
                                normad:evaluatedNorm ?n ; normad:hasApplicabilityStatus ?s }"""):
            out[self.short(r["c"])][self.short(r["n"])] = self.short(r["s"]).split(":")[-1]
        return out

    # ── exceptions: defeasibility, before any case ───────────────────────────
    def exceptions(self) -> dict:
        g = self.full_g
        edges = defaultdict(list)                  # overriding norm -> [(overridden, gate, onlyIn)]
        for a, b in g.subject_objects(NORMA.isExceptionTo):
            edges[a].append((b, "", next((v for v, vg in self.variant_g.items() if (a, NORMA.isExceptionTo, b) in vg), None)))
        for d in set(g.subjects(NORMA.defeatingNorm, None)):
            gate = g.value(d, NORMA.appliesWhen)
            gate_c = next(g.subjects(NORMA.hasTrigger, gate), None) if gate is not None else None
            for b in g.objects(d, NORMA.defeatedNorm):
                edges[g.value(d, NORMA.defeatingNorm)].append((b, self.label(gate_c) if gate_c is not None else "", None))
        groups = []
        for a, items in edges.items():
            when = [{"text": self.label(c), "holds": g.value(te, NORMA.hasOutcome) != NORMA.FalseOutcome}
                    for te in g.subjects(NORMA.activatesNorm, a) for c in g.subjects(NORMA.hasTrigger, te)]
            groups.append({"by": self.brief(a), "when": when, "byFacts": sorted({self.label(c) for te in g.subjects(NORMA.activatesNorm, a)
                                                                                for c in g.subjects(NORMA.hasTrigger, te)
                                                                                if te in set(g.objects(None, NORMA.establishesTrigger))}),
                           "overrides": [{"norm": self.brief(b), "gate": gate, "onlyIn": only}
                                         for b, gate, only in sorted(items, key=lambda x: self.short(x[0]))]})
        groups.sort(key=lambda x: (-len(x["overrides"]), x["by"]["id"]))
        # The static prevalence ladder: the level of every norm with no case in view.
        levels = defaultdict(list)
        for r in self.query("""SELECT ?n ?l WHERE { ?o a normad:PrevalenceOrdering . FILTER NOT EXISTS { ?o normad:forFactPattern ?x }
                                ?e normad:inOrdering ?o ; normad:evaluatedNorm ?n ; normad:prevalenceLevel ?l }"""):
            levels[int(r["l"])].append(self.short(r["n"]))
        involved = {x["by"]["id"] for x in groups} | {o["norm"]["id"] for x in groups for o in x["overrides"]}
        ladder = [{"level": lv, "norms": sorted(n for n in ns if n in involved), "others": len([n for n in ns if n not in involved])}
                  for lv, ns in sorted(levels.items(), reverse=True)]
        return {"groups": groups, "ladder": ladder}

    # ── Turtle source ────────────────────────────────────────────────────────
    def source(self) -> dict:
        files = []
        if self.annotation and self.annotation.exists():
            files.append({"name": self.annotation.name, "role": "annotation", "text": self.annotation.read_text(encoding="utf-8")})
        for name, p in self.variants_path.items():
            files.append({"name": p.name, "role": f"reading: {name}", "text": p.read_text(encoding="utf-8")})
        return {"files": files}

    def source_line(self, nid: str) -> int | None:
        if not (self.annotation and self.annotation.exists()):
            return None
        for i, line in enumerate(self.annotation.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(rf"^:{re.escape(nid)}\s+a\s", line):
                return i
        return None

    # ── graph neighbourhood ──────────────────────────────────────────────────
    def node_json(self, u) -> dict:
        return {"id": self.short(u), "group": self.group(u), "groupName": GROUP_NAME.get(self.group(u), self.group(u)),
                "label": self.short_label(u)}

    def neighbourhood(self, u: URIRef, collapse: bool, derived: bool, limit: int = 40) -> dict:
        G = self.G
        nodes, edges, more = {self.short(u): self.node_json(u)}, [], Counter()
        derived_p = DERIVED_PREDICATES | {NORMA.isNegationOf}
        hidden = lambda x: not derived and (self.group(x) in DERIVED_GROUPS or str(x).endswith("_neg"))

        def add(s, p, o, lab):
            if hidden(s) or hidden(o) or (not derived and p in derived_p):
                return
            nodes.setdefault(self.short(s), self.node_json(s)); nodes.setdefault(self.short(o), self.node_json(o))
            edges.append({"source": self.short(s), "target": self.short(o), "label": lab})

        def trig(te):
            return next(G.subjects(NORMA.hasTrigger, te), None), G.value(te, NORMA.activatesNorm), G.value(te, NORMA.hasOutcome) != NORMA.FalseOutcome

        count = Counter()
        for p, o in G.predicate_objects(u):
            if isinstance(o, (Literal, BNode)) or p == RDF.type or o in self.tbox_subjects:
                continue
            if collapse and p == NORMA.hasTrigger:
                _, n, yes = trig(o)
                if n is not None:
                    add(u, p, n, "activates" + ("" if yes else " (if it does not hold)"))
                continue
            if collapse and p in (NORMA.establishesTrigger, NORMA.holdsTrigger):
                c, _, yes = trig(o)
                if c is not None:
                    add(u, p, c, text.relation(str(p).split("#")[-1]) + ("" if yes else " (the opposite)"))
                continue
            count[p] += 1
            if count[p] > limit:
                more[text.relation(str(p).split("#")[-1])] += 1; continue
            add(u, p, o, text.relation(str(p).split("#")[-1]))
        count.clear()
        for s, p in G.subject_predicates(u):
            if p == RDF.type or s in self.tbox_subjects or (collapse and p == NORMA.hasTrigger):
                continue
            if collapse and p == NORMA.activatesNorm:
                c, _, yes = trig(s)
                if c is not None:
                    add(c, p, u, "activates" + ("" if yes else " (if it does not hold)"))
                continue
            count[p] += 1
            if count[p] > limit:
                more["← " + text.relation(str(p).split("#")[-1])] += 1; continue
            add(s, p, u, text.relation(str(p).split("#")[-1]))
        if collapse and self.group(u) == "Condition":
            for te in G.objects(u, NORMA.hasTrigger):
                yes = G.value(te, NORMA.hasOutcome) != NORMA.FalseOutcome
                for r in G.subjects(NORMA.establishesTrigger, te):
                    add(r, NORMA.establishesTrigger, u, "establishes" + ("" if yes else " (the opposite)"))
                for c in G.subjects(NORMA.holdsTrigger, te):
                    add(c, NORMA.holdsTrigger, u, "holds" + ("" if yes else " (the opposite)"))
        seen, uniq = set(), []
        for e in edges:
            k = (e["source"], e["target"], e["label"])
            if k not in seen:
                seen.add(k); uniq.append(e)
        return {"nodes": list(nodes.values()), "edges": uniq, "more": dict(more)}

    def properties(self, u: URIRef) -> dict:
        """Every statement about a node, in words: its data and its links, both ways."""
        G = self.full_g
        derived_p = DERIVED_PREDICATES | {NORMA.isNegationOf}
        is_derived = lambda p, x: p in derived_p or self.group(x) in DERIVED_GROUPS or str(x).endswith("_neg")
        out_lit, out_rel, in_rel = [], [], []
        for p, o in sorted(G.predicate_objects(u), key=lambda x: str(x[0])):
            name = text.relation(str(p).split("#")[-1]) if p != RDF.type else "type"
            if isinstance(o, Literal):
                out_lit.append({"property": name, "curie": self.short(p), "value": str(o)})
            elif p == RDF.type:
                out_rel.append({"property": "type", "curie": "rdf:type", "id": self.short(o), "label": self.short(o).split(":")[-1],
                                "vocabulary": True})
            elif not isinstance(o, BNode):
                vocab = o in self.tbox_subjects
                out_rel.append({"property": name, "curie": self.short(p), "id": self.short(o), "vocabulary": vocab,
                                "label": self.short(o).split(":")[-1] if vocab else self.short_label(o), "derived": is_derived(p, o)})
        for s, p in G.subject_predicates(u):
            if p == RDF.type or isinstance(s, BNode) or s in self.tbox_subjects or self.group(s) in ("Evaluation", "WeakPermission"):
                continue
            in_rel.append({"property": text.relation(str(p).split("#")[-1]), "curie": self.short(p), "id": self.short(s),
                           "label": self.short_label(s), "derived": is_derived(p, s)})
        out_rel.sort(key=lambda x: (x.get("derived", False), x["property"]))
        return {"literals": out_lit, "outgoing": out_rel,
                "incoming": sorted(in_rel, key=lambda x: (x["derived"], x["property"], x["label"]))[:60], "incomingTotal": len(in_rel)}

    def node(self, name: str, collapse: bool, derived: bool, statuses: dict) -> dict:
        u = self.full(name)
        if (u, None, None) not in self.full_g and (None, None, u) not in self.full_g:
            raise KeyError(name)
        d = self.node_json(u)
        d.update({"reading": self.reading(u) if self.kind(u) else self.label(u), "statuses": statuses,
                  "gaps": [{"category": str(self.G.value(gp, GAP.category) or ""), "missing": str(self.G.value(gp, GAP.missing) or "")}
                           for gp in self.G.subjects(GAP.representedAs, u)]})
        return {"details": d, "properties": self.properties(u), **self.neighbourhood(u, collapse, derived)}

    def search(self, term: str) -> list:
        term = term.lower().strip()
        hits = []
        for s in set(self.full_g.subjects(RDF.type, None)):
            if s in self.tbox_subjects or isinstance(s, BNode) or self.group(s) in DERIVED_GROUPS:
                continue
            if term in (self.short(s) + " " + self.label(s)).lower():
                hits.append({**self.node_json(s), "score": (0 if self.short(s).lower().startswith(term) else 1, len(self.label(s)))})
        return sorted(hits, key=lambda h: h["score"])[:25]
