"""Everything the explorer says in words: plain readings of norms, relation
names, deontic operators and Hohfeldian positions. Generated from the graph,
never from the contract text."""
from __future__ import annotations

KIND = {"Obligation": "Obligation", "Prohibition": "Prohibition", "Permission": "Permission",
        "Facultative": "Faculty", "Recommendation": "Recommendation",
        "NegativeRecommendation": "Negative recommendation", "ConstitutiveRule": "Constitutive rule"}

MODAL = {"Obligation": "must", "Prohibition": "must not", "Permission": "may", "Facultative": "may, but need not,",
         "Recommendation": "should", "NegativeRecommendation": "should not"}

# The deontic closure: operator -> (symbol, plain meaning)
CLOSURE = {"Obligatory": ("O", "obligatory"), "NotObligatory": ("¬O", "not obligatory"),
           "Permitted": ("P", "permitted"), "NotPermitted": ("¬P", "not permitted"),
           "Forbidden": ("F", "forbidden"), "NotForbidden": ("¬F", "not forbidden"),
           "Recommended": ("Rec", "recommended"), "Discouraged": ("NegRec", "discouraged")}

POSITION = {"Duty": "duty", "Claim": "claim", "Privilege": "privilege", "NoRight": "no-right"}

# Graph relations as a reader would say them.
RELATION = {
    "hasLegalAgent": "addressed to", "hasCounterparty": "towards", "hasLegalAction": "action",
    "hasLegalObject": "object", "hasLegalSource": "source", "hasSourceExpression": "version",
    "usedLegalSource": "used the source", "wasAttributedToAnnotator": "annotated by",
    "wasGeneratedByAnnotationActivity": "annotated in", "wasAssociatedWithAnnotator": "annotator",
    "isExceptionTo": "overrides", "supersedes": "replaces", "defeatingNorm": "overriding norm",
    "defeatedNorm": "overridden norm", "appliesWhen": "only when", "confersRole": "confers the role",
    "hasAssignedParty": "party", "hasAssignedRole": "role", "holdsRoleAssignment": "assigns",
    "assignedUnderRule": "under the rule", "representedAs": "gap in", "activatesNorm": "activates",
    "hasTrigger": "trigger", "establishesTrigger": "establishes", "holdsTrigger": "holds",
    "isNegationOf": "negation of", "confersLegalPosition": "confers", "hasPositionHolder": "held by",
    "isCorrelativeOf": "correlative of", "isJuralOppositeOf": "opposite of", "concernsLegalAction": "about",
    "inFactPattern": "in case", "forAgent": "for", "aboutAction": "about", "evaluatedNorm": "evaluates",
    "isDeonticallyEquivalentTo": "equivalent to", "deonticallyContradicts": "contradicts",
    "deonticallyConflictsWith": "conflicts with", "reachesParty": "reaches",
    "hasNormStatus": "status", "hasReviewStatus": "review", "hasExtractionMethod": "method",
    "hasBindingForce": "binding force", "fromRank": "rank", "hasRank": "rank",
    "hasOutcome": "outcome", "normStatement": "text in the contract", "conditionStatement": "statement",
    "factStatement": "statement", "deonticId": "identifier", "fromArticle": "clause",
    "fromRegulation": "regulation", "regulationName": "name", "hasDeadline": "deadline", "label": "label",
    "comment": "comment", "annotationDate": "annotated on", "hasStrength": "defeasibility",
}

STATUS = {"Applicable": "applies", "Defeated": "overridden", "NotActivated": "not triggered",
          "Undecided": "undecided", "Invalid": "not in force"}


def relation(local: str) -> str:
    return RELATION.get(local, local)


def the(label: str) -> str:
    return "the " + label.lower() if label else "the addressee"


def reading(kind: str | None, agent: str, counterparty: str, action: str, fact: str = "") -> str:
    """'The tenant must pay the rent, towards the landlord.'"""
    if kind == "ConstitutiveRule" or kind is None:
        return fact
    a = the(agent)
    towards = f", towards {the(counterparty)}" if counterparty else ""
    return f"{a[0].upper()}{a[1:]} {MODAL.get(kind, '')} {action}{towards}."
