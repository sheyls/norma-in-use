# The test contract: a Spanish residential lease

The contract `norma-in-use` uses to try out NORMA-O 2.0: a real residential
lease signed in Spain on 10 June 2026 (14 clauses), anonymised (every name,
identity document, bank detail, address and amount replaced).

| Folder / file | What it is | Written by |
|---|---|---|
| [`contract/lease-es-original.txt`](contract/lease-es-original.txt) | The anonymised Spanish original. Authoritative. | — |
| [`contract/lease-en-translation.txt`](contract/lease-en-translation.txt) | The English translation the annotation is made on. | — |
| [`annotation/lease.ttl`](annotation/lease.ttl) | **The annotation**, in one file: 52 norms with their conditions, exceptions and counts-as rules; 14 described cases; 21 gaps; the source and the provenance. Imports `https://w3id.org/def/norma-o/2.0`. | hand (Claude Opus 5.5 and Sheyla Leyva) |
| [`annotation/variant-lau-2026.ttl`](annotation/variant-lau-2026.ttl) | Optional alternative reading: art. 11.3 LAU as worded by Royal Decree-Law 29/2026 applies to the contract. Its first line names it. | hand |
| `generated/` | Everything else: the derivation and the bundle of each reading, the review sheet, the per-case summary. Never edited; rebuilt by the engine. | the `norma` engine |

```bash
# from the project root
.venv/bin/norma residential-lease/annotation/lease.ttl --out residential-lease/generated
```

## What `lease.ttl` contains

Four sections, all NORMA-O 2.0:

1. **Norms**: obligations, prohibitions and permissions (addressee, counterparty,
   action, conditions, deadline) and constitutive rules (what they establish or
   which norms they withdraw). Conventions are in the file's header.
2. **Cases**: for each situation, only the brute facts that hold
   (`norma:holdsTrigger`) and who plays which role (`norma:RoleAssignment`).
   Institutional facts such as "the agreement has ended" are never written in a
   case: the derivation establishes them.
3. **Gaps**: what NORMA-O holds only as a fact, or holds as written although a
   mandatory provision of the LAU (outside the graph) corrects it.
4. **Source and provenance**: the agreement as `LegalSource`, with the Spanish
   original and the English translation as its `LegalSourceExpression`s;
   annotators, `AnnotationActivity`, extraction method, review status, norm
   status and binding force on every norm.

The two readings differ at one place: the compensation for withdrawing in the
eighth month (case L07) applies in the base reading and is defeated in reading B.
