---
title: NORMA-O in use · Residential lease
emoji: ⚖️
colorFrom: indigo
colorTo: green
sdk: gradio
sdk_version: 6.31.0
python_version: '3.12'
app_file: app.py
pinned: false
license: cc-by-4.0
short_description: NORMA-O 2.0 applied to a residential lease
---

# NORMA-O in use: a residential lease

A worked example of [NORMA-O 2.0](https://github.com/sheyls/NORMA-O), an
ontology for machine-readable legal norms. A real residential lease (Spain,
2026, anonymised) is annotated by hand in **one Turtle file**; the NORMA-O
engine derives everything else (deontic closure, Hohfeldian positions,
deontic relations, the prevalence ordering of exceptions, and which norms
apply in each described case); a web explorer shows the annotation and the
derivation side by side.

The point of the example is to show what a project needs in order to use
NORMA-O 2.0: **only the annotation**. The ontology and the engine are not copied
here; they are installed from the published release.

## Layout

```
norma-in-use/
├── residential-lease/
│   ├── contract/      the source text
│   │   ├── lease-es-original.txt       Spanish original (anonymised), authoritative
│   │   └── lease-en-translation.txt    English translation the annotation is made on
│   ├── annotation/    WRITTEN BY HAND, in NORMA-O 2.0
│   │   ├── lease.ttl                   norms, cases, gaps, source and provenance
│   │   └── variant-lau-2026.ttl        an alternative legal reading (optional)
│   └── generated/     PRODUCED BY THE ENGINE; never edited, can be deleted and rebuilt
├── queries/           SPARQL questions over the result, and query.py to run them
├── web/               the explorer
└── app.py · Dockerfile   to host the explorer (Hugging Face Space, or any container)
```

[`residential-lease/README.md`](residential-lease/README.md) describes the
contract and the annotation in detail.

## Using NORMA-O 2.0

NORMA-O is a dependency, pinned to its release tag
([`requirements.txt`](requirements.txt), next to Flask for the explorer):

```
norma-o @ git+https://github.com/sheyls/NORMA-O@v2.0.0
```

The annotation imports it by its published IRI:

```turtle
<https://example.org/lease-en> a owl:Ontology ;
    owl:imports <https://w3id.org/def/norma-o/2.0> .
```

The `norma-o` package resolves that IRI (and the derivation module's) to its
own files, so nothing is fetched from the network and the version is always the
pinned one. It provides the `norma` command and, from Python, `norma_o.load()`,
`norma_o.ONTOLOGY`, `norma_o.MODULE` and `norma_o.engine`.

## Running it

Python 3.10 or later:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt          # NORMA-O 2.0.0 (with rdflib) and Flask

# 1. annotation → derivation
.venv/bin/norma residential-lease/annotation/lease.ttl --out residential-lease/generated

# 2. explore it: http://127.0.0.1:5050
cd web && ../.venv/bin/python app.py

# or ask questions from the command line
.venv/bin/python queries/query.py --list
.venv/bin/python queries/query.py 10_status_matrix
```

Live demo: <https://huggingface.co/spaces/sheyls/norma-in-use-lease>. Or, with
Docker (the image installs NORMA-O from its tag and serves the explorer on port 7860):

```bash
docker build -t norma-in-use . && docker run --rm -p 7860:7860 norma-in-use
```

`norma` runs five steps on the annotation and on each `variant-*.ttl` next to it:

| Step | What it does | Output in `generated/` |
|---|---|---|
| check | what the derivation needs is present: addressee and action of every norm (errors); counterparty, source, provenance, review status, binding force, cases (warnings) | (console) |
| derive | the reference rule set (`norma-derivation/1.0`) | `lease.derived.ttl` |
| bundle | annotation + derivation, one file per reading, importing NORMA-O by its published IRIs | `lease.bundle.ttl`, `lease+variant-lau-2026.bundle.ttl` |
| reason | with `--reason`: OWL consistency with HermiT (`pip install "norma-o[reason]"`, Java) | (console) |
| report | a review sheet for a legal expert; the status of every norm in every case under every reading | `review-sheet.csv`, `summary.txt` |

The derivation is never merged back into the annotation: it is regenerated
(`normad:DerivationActivity` records the rule-set version and the assumptions).

## What is annotated and what is derived

| Derived | From | Rules |
|---|---|---|
| Deontic closure: O(x) ⇒ P(x), ¬F(x), F(¬x)…, with ¬x minted for every action | each norm's type and action | `01`, `02a`–`02f` |
| Hohfeldian positions: a duty and its correlative claim; a privilege and its no-right | the closure, the addressee and the counterparty | `04a`–`04d` |
| Deontic relations: equivalence, contradiction, contrariety | pairs of norms on the same addressee and action | `05a`–`05c` |
| Per case: which norms apply, are defeated or are not activated; institutional facts established by applicable constitutive rules, fed back until a fixpoint; who each norm reaches; weak permissions | the cases' brute facts, the exceptions and the prevalence graph (grounded semantics) | `03a`–`03c` and `deriv/prevalence.py` |

Result on this contract: 52 norms (28 regulative, 24 constitutive rules),
14 described cases, a three-level acyclic prevalence ordering, and two readings
that differ in one place: the compensation owed for withdrawing in the eighth
month (case L07) applies in the base reading and is defeated under art. 11.3
LAU as amended in 2026.

## The explorer

[`web/`](web/) shows, per role, the norms as annotated and the positions
derived from them; every norm with its conditions, exceptions, closure,
provenance and status in each case; each case as numbered reasoning steps
(facts → rules that fire → institutional facts → what starts and stops
applying), with custom cases re-derived on the fly by the real rule set; the
exceptions and the prevalence ordering; the annotation itself; a graph browser;
and the SPARQL behind every view. See [`web/README.md`](web/README.md).

## Licence and citation

- **NORMA-O 2.0** (the `norma-o` package: ontology, derivation module, rule set,
  engine): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), as declared
  in the ontology (`dcterms:license`). Source: <https://github.com/sheyls/NORMA-O>.
- **This example** (contract texts, annotation, queries, explorer):
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); see [`LICENSE`](LICENSE).
  The contract is a real lease, anonymised: names are placeholders (Alice Doe,
  Carol Roe, Erin Stiles) and identity documents, bank details and addresses are
  removed.
- Third-party libraries keep their own licences (rdflib BSD-3-Clause, Flask
  BSD-3-Clause, Cytoscape.js MIT, dagre MIT, owlready2 LGPL-3.0).

Cite NORMA-O as <https://doi.org/10.5281/zenodo.24116269>.
