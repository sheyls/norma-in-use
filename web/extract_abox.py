"""Rebuilds the annotation ABox from a derived bundle by removing everything
deriv/derive.py produces, so the derivation can be re-run (e.g. on new cases).

    python extract_abox.py "../NORMA Trademark License.ttl" -o data/abox.ttl
"""
import argparse
from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF

NORMA = Namespace("https://w3id.org/def/norma-o#")
NORMA_O = "https://w3id.org/def/norma-o/2.0"   # what an annotation imports (published version IRI)

DERIVED_PREDICATES = {NORMA[p] for p in (
    "entailsObligatory entailsNotObligatory entailsPermitted entailsNotPermitted entailsForbidden "
    "entailsNotForbidden entailsRecommended entailsDiscouraged confersLegalPosition isDeonticallyEquivalentTo "
    "deonticallyConflictsWith deonticallyContradicts isJuralOppositeOf").split()}
DERIVED_TYPES = {NORMA[t] for t in "Duty Claim Privilege NoRight WeakPermission".split()}


def extract(bundle: Path) -> Graph:
    g = Graph().parse(bundle)
    out = Graph()
    for p, ns in g.namespaces():
        out.bind(p, ns)
    derived_ns = [str(o).rstrip("#") + "#" for o in g.objects(None, URIRef("https://w3id.org/def/norma-o/deriv#derivedGraph"))]
    drop = {s for t in DERIVED_TYPES for s in g.subjects(RDF.type, t)}
    drop |= {s for s in g.subjects() if any(str(s).startswith(d) for d in derived_ns)}
    # negations minted by stage 1 of the rule set: <X>_neg, with isNegationOf to X
    minted = {s for s, o in g.subject_objects(NORMA.isNegationOf) if str(s) == str(o) + "_neg"}
    drop |= minted
    for s, p, o in g:
        if s in drop or o in drop or p in DERIVED_PREDICATES:
            continue
        if p == OWL.imports:      # the bundle also imports the derivation module; an annotation does not
            continue
        out.add((s, p, o))
    for onto in out.subjects(RDF.type, OWL.Ontology):
        out.add((onto, OWL.imports, URIRef(NORMA_O)))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args()
    g = extract(a.bundle)
    g.serialize(a.out, format="turtle")
    print(f"{a.out}: {len(g)} triples")
