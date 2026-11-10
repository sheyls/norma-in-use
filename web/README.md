# Web explorer

A local web app over the test contract: the annotation, what the NORMA-O
engine derives from it, and what applies case by case. It works with this
example only; there is no upload.

```bash
# from the project root, once the bundle is generated (see ../README.md)
cd web && ../.venv/bin/python app.py          # http://127.0.0.1:5050
lsof -ti:5050 | xargs kill                     # stop
```

By default it reads `../residential-lease/generated/lease.bundle.ttl`, shows
`../residential-lease/annotation/lease.ttl`, and offers every `variant-*.ttl`
next to it as an alternative reading (as the engine does).

At start-up (~50 s) it recovers the annotation from the bundle
(`extract_abox.py` removes everything `derive.py` produces), re-derives every
case and reports in the sidebar whether that reproduces the bundle. The
ontology, the derivation module and `derive.py` come from the installed `norma-o`
package (`norma_o.ONTOLOGY`, `norma_o.MODULE`, `norma_o.HOME/deriv`); nothing is fetched online.

## Code

| File | Role |
|---|---|
| `app.py` | HTTP routes only: wires the model and the simulator to `/api/*` and `/files/*`. |
| `model.py` | `Model`: the loaded bundle (+ TBox, + readings) and its read-only views: overview, role, norm sheet, exceptions, node neighbourhood and properties, search, source text. Every view's SPARQL is a class constant, shown in the UI. |
| `reasoner.py` | `Simulator`: runs a case with the release's `derive.py` (unchanged) and turns the result into numbered steps. Rule `05a` (deontic equivalence, ~95% of a run, case-independent) is memoised per reading. |
| `text.py` | All generated English wording: modal verbs, closure operators, positions, relation names, statuses, “The tenant must pay the rent, towards the landlord.” |
| `extract_abox.py` | Bundle → hand-written annotation (drops derived triples). |
| `static/` | `index.html`, `style.css`, `app.js` (vanilla JS, one function per view; Cytoscape + dagre for the graph). |

## Views

| View | Answers |
|---|---|
| **Home** | What the demo is, how to read it (annotated → derived → cases), where to start, glossary. |
| **Role** | Norms addressed to each role, in plain words, and the Hohfeldian positions derived from them: duties, claims, privileges, no-rights, each with the norm it comes from. |
| **All norms** | Clause by clause, filterable; click one for its sheet. |
| **Norm sheet** | Reading and contract text, who/towards whom, conditions, deadline, what overrides it and what it overrides, binding force, deontic closure (annotated vs derived), positions, relations, gaps, provenance, status in every case and reading (differences highlighted); links to the graph and to its line in the annotation. Direct link: `#norm/<id>`. |
| **Cases** | Numbered steps: what happened → rules that fire → facts they establish → what starts and stops applying (against L01), what differs under the other reading, conflicts with mandatory law, each party's positions. “Change the facts” builds a custom case. |
| **Exceptions** | Each overriding norm, the condition that triggers it and the norms it switches off; the prevalence ladder as tiers. |
| **The annotation** | `lease.ttl` and the reading file, highlighted, with sections, search, line links (`#annotation/<line>`) and downloads. |
| **Graph** | Click a node for all its properties (data, links out, links in; derived ones marked); double-click or “Bring in neighbours” to expand. Derived nodes behind a switch. |
| **SPARQL** | The query behind each view plus `queries/*.rq`; editable, with role/norm/case selectors and CSV export. Read-only. |
