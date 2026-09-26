"""Output schemas.

Classification mirrors policy.md (v0) and is what triage.py and app.py consume.
CRSVAssessment mirrors policy/core.md; `finalize` applies its hard rules and
`to_classification` adapts it so the existing platform keeps working.
"""

from typing import Literal

from pydantic import BaseModel, Field

HarmType = Literal[
    "threat_incitement",
    "glorification",
    "mockery_dark_humor",
    "victim_identification",
    "stigmatization",
    "sexually_explicit",
    "denial_or_disinformation",
    "unverified_sv_claim",
]
Tone = Literal["serious", "humorous_ironic", "reporting", "testimony", "awareness", "other"]
ClaimStatus = Literal[
    "first_hand", "reported_by_media_or_org", "unverified_allegation", "appears_fabricated", "no_claim"
]
Victim = Literal["woman", "child", "man", "group", "unidentifiable", "none"]
Confidence = Literal["low", "medium", "high"]


class Classification(BaseModel):
    harm_types: list[HarmType]
    tone: Tone
    claim_status: ClaimStatus
    victims: list[Victim]
    harm_potential: int  # 0-3, clamped in triage
    confidence: Confidence
    summary: str
    rationale: str


# --- CRSV assessment (policy/core.md) ------------------------------------------

ElementValue = Literal["likely", "possible", "unlikely", "unclear"]
Relation = Literal["SV-REL-1", "SV-REL-2", "SV-REL-3", "SV-REL-4", "SV-REL-5"]
NamedAct = Literal[
    "SV-FORM-01", "SV-FORM-02", "SV-FORM-03", "SV-FORM-04", "SV-FORM-05",
    "SV-FORM-06", "SV-FORM-07", "SV-FORM-08", "SV-FORM-09", "SV-FORM-10",
]
HIType = Literal["HI-TYPE-01", "HI-TYPE-02", "HI-TYPE-03", "HI-TYPE-04", "HI-TYPE-05", "HI-TYPE-06"]
Pathway = Literal["HP-01", "HP-02", "HP-03", "HP-04", "HP-05", "HP-06", "HP-07"]
ConfId = Literal["CONF-1", "CONF-2", "CONF-3", "CONF-4"]
Exclusion = Literal["B2-1", "B2-2", "B2-3", "B2-4", "B2-5"]
Route = Literal["restricted_escalation", "priority_review", "standard_review", "not_flagged"]
Priority = Literal["urgent", "high", "standard", "none"]
Layer = Literal["TG-L1", "TG-L2", "TG-L3", "TG-L4", "TG-L5", "TG-L6", "TG-L7", "TG-L8"]
FLAG_ROUTES = ("priority_review", "standard_review")
PRIORITY_RANK = {"none": 0, "standard": 1, "high": 2, "urgent": 3}


class RiskFlags(BaseModel):
    possible_minor: bool
    identifiable_person: bool
    possible_manipulated_media: bool


class Features(BaseModel):
    source_attributed: bool  # core v1.1: "reports" requires a named source (media, NGO, UN, named authority)
    stance: Literal["endorses", "reports", "quotes_to_condemn", "mocks", "unclear"]
    target: Literal["individual", "group", "unspecified"]
    general: bool
    modal: Literal["past", "habitual", "future", "imperative", "conditional"]
    cta: Literal["explicit", "implied", "none"]
    frame: bool
    speaker: Literal["armed_actor_or_affiliate", "community_member", "journalist", "survivor_or_support_group", "unknown"]


class ForwardedOriginal(BaseModel):
    """TG-L2: the forwarded original is a separate speaker with its own stance."""
    stance: Literal["endorses", "reports", "quotes_to_condemn", "mocks", "unclear"]
    primary_relation: Relation | None


class Element(BaseModel):
    value: ElementValue
    confidence: float = Field(ge=0, le=1)
    reason: str


class Elements(BaseModel):
    A: Element
    B: Element
    C: Element


class Finding(BaseModel):
    """An HI-TYPE or HP with its certainty ("possible" when truth is unknown)."""
    id: str
    possible: bool


class HIFinding(Finding):
    id: HIType


class HPFinding(Finding):
    id: Pathway


class CRSVModelOutput(BaseModel):
    """What the LLM fills, in decision-procedure order (core.md). Route and priority are proposals."""
    risk_flags: RiskFlags
    exclusion: Exclusion | None
    forwarded_original: ForwardedOriginal | None
    features: Features
    elements: Elements
    primary_relation: Relation | None
    secondary_relations: list[Relation]
    content_type: Literal[1, 2, 3, 4, 5, 6] | None
    named_acts: list[NamedAct]
    hi_types: list[HIFinding]
    harm_pathways: list[HPFinding]
    affiliation: Literal["AFF-1", "AFF-2", "AFF-3", "AFF-4", "none"]
    conf_ids: list[ConfId]
    age: list[Literal["adult", "minor", "unknown"]]
    triggered_layer: Layer
    lexicon_hits: list[str]
    cited_ids: list[str]
    route: Route
    priority: Priority
    lead: bool
    reviewer_summary: str
    media_needed_to_decide: bool
    notes: str


class CRSVAssessment(CRSVModelOutput):
    """Final record: model output after the hard rules of core.md / children.md."""
    item_id: str
    region: str
    profile_version: str
    in_scope: bool
    conflict_link: Literal["present", "absent", "unclear"]
    model_route: Route
    model_priority: Priority
    restricted_reason: Literal["model", "rule_age"] | None = None
    invalid_ids: list[str] = []
    rule_notes: list[str] = []


def _confident(e: Element) -> bool:
    return e.value in ("likely", "possible")


def flag_rule(o: CRSVModelOutput) -> bool:
    """Axis 1 AND Axis 2 AND AFF-1/2/3, no B2 exclusion, stance not reporting/condemning."""
    axis1 = o.primary_relation is not None
    axis2 = bool(o.hi_types) and bool(o.harm_pathways)
    aff = o.affiliation in ("AFF-1", "AFF-2", "AFF-3")
    stance_override = o.features.stance in ("reports", "quotes_to_condemn")
    return axis1 and axis2 and aff and o.exclusion is None and not stance_override


def rule_priority(o: CRSVModelOutput, high_reach: bool = False) -> Priority:
    hp = {h.id for h in o.harm_pathways}
    rel = o.primary_relation
    if rel == "SV-REL-2" and (o.features.cta == "explicit" or o.features.modal in ("future", "imperative")):
        return "urgent"
    if "HP-03" in hp and o.risk_flags.identifiable_person:
        return "urgent"
    if rel == "SV-REL-2" or high_reach:
        return "high"
    if rel == "SV-REL-5" and (o.risk_flags.identifiable_person or o.features.target == "individual"):
        return "high"
    if "minor" in o.age:  # CH-1b: children as targets of non-sexual text
        return "high"
    return "standard"


def finalize(o: CRSVModelOutput, *, item_id: str, region: str, profile_version: str,
             valid_ids: set[str] | None = None, age_indicator: bool = False,
             sv_signal: bool = False, high_reach: bool = False, quote_present: bool = False) -> CRSVAssessment:
    """Apply the hard rules. `age_indicator` / `sv_signal` come from the deterministic lexicon checks;
    `quote_present` = the item forwards or quotes other content (known from the item, not the model)."""
    notes: list[str] = []
    data = o.model_dump()
    data.update(item_id=item_id, region=region, profile_version=profile_version,
                model_route=o.route, model_priority=o.priority)

    invalid = sorted({i for i in o.cited_ids if valid_ids is not None and i not in valid_ids})
    data["invalid_ids"] = invalid

    # 1. possible_minor first (B1-1, CH-1a, CH-5). When unsure, raise it.
    sexual = _confident(o.elements.A) or bool(o.named_acts) or o.primary_relation is not None or sv_signal
    minor = o.risk_flags.possible_minor or (sexual and (age_indicator or "minor" in o.age))
    if minor:
        if not o.risk_flags.possible_minor:
            notes.append("possible_minor raised by rule (age indicator + sexual element)")
        blank = CRSVAssessment(
            item_id=item_id, region=region, profile_version=profile_version,
            risk_flags=RiskFlags(possible_minor=True, identifiable_person=False, possible_manipulated_media=False),
            exclusion=None, forwarded_original=None,
            features=Features(source_attributed=False, stance="unclear", target="unspecified", general=False, modal="past", cta="none",
                              frame=False, speaker="unknown"),
            elements=Elements(**{k: Element(value="unclear", confidence=0, reason="") for k in "ABC"}),
            primary_relation=None, secondary_relations=[], content_type=None, named_acts=[], hi_types=[],
            harm_pathways=[], affiliation="none", conf_ids=[], age=[], triggered_layer=o.triggered_layer,
            lexicon_hits=[], cited_ids=["B1-1", "CH-1a"], route="restricted_escalation", priority="urgent",
            lead=False, reviewer_summary="", media_needed_to_decide=False, notes="", in_scope=True,
            conflict_link="unclear", model_route=o.route, model_priority=o.priority, invalid_ids=[],
            rule_notes=notes, restricted_reason="model" if o.risk_flags.possible_minor else "rule_age",
        )
        return blank

    # core v1.1: "reports" without an attributed source is not reporting (unsourced rumour → unclear).
    if o.features.stance == "reports" and not o.features.source_attributed:
        o = o.model_copy(deep=True)
        o.features.stance = "unclear"
        data["features"]["stance"] = "unclear"
        notes.append("stance reports without attributed source -> unclear (core v1.1)")
    # Nothing is quoted or forwarded: there is nothing to "quote to condemn".
    if o.features.stance == "quotes_to_condemn" and not quote_present:
        o = o.model_copy(deep=True)
        o.features.stance = "unclear"
        data["features"]["stance"] = "unclear"
        notes.append("quotes_to_condemn without quoted or forwarded content -> unclear")

    # 2-8. Flag rule, lead, priority, route.
    flagged = flag_rule(o)
    # core v1.1: only reporting / quoting to condemn (B2-3) is a lead. Testimony (B2-1) never is (B6-3),
    # nor prevention or general discussion.
    lead = ((o.lead or o.features.stance in ("reports", "quotes_to_condemn") or o.exclusion == "B2-3")
            and o.exclusion not in ("B2-1", "B2-2", "B2-4", "B2-5"))
    priority: Priority = "none"
    route: Route = "not_flagged"
    if flagged:
        rule = rule_priority(o, high_reach)
        priority = max(rule, o.priority if o.priority != "none" else "standard", key=PRIORITY_RANK.get)
        ongoing = o.features.modal in ("future", "imperative") or o.features.cta != "none"
        a_b_likely = o.elements.A.value == "likely" and o.elements.B.value == "likely"
        targeted = o.primary_relation in ("SV-REL-2", "SV-REL-5") and (o.risk_flags.identifiable_person or ongoing)
        route = "priority_review" if priority == "urgent" or (a_b_likely and targeted) else "standard_review"
    if (route != o.route) or (priority != o.priority):
        notes.append(f"rules changed model route/priority {o.route}/{o.priority} -> {route}/{priority}")

    c = o.elements.C
    data.update(
        route=route, priority=priority, lead=lead and not flagged,
        in_scope=o.primary_relation is not None,
        conflict_link="present" if c.value == "likely" else "unclear" if c.value in ("possible", "unclear") else "absent",
        rule_notes=notes,
    )
    return CRSVAssessment(**data)


# --- Adapter to the v0 Classification used by triage.py and app.py ---------------

_REL_TO_HARM = {
    "SV-REL-2": "threat_incitement",
    "SV-REL-3": "unverified_sv_claim",
    "SV-REL-4": "glorification",
    "SV-REL-5": "stigmatization",
    "SV-REL-1": "unverified_sv_claim",
}


def to_classification(a: CRSVAssessment) -> Classification:
    if a.route == "restricted_escalation":
        return Classification(harm_types=[], tone="other", claim_status="no_claim", victims=["child"],
                              harm_potential=3, confidence="high", summary="", rationale="Restricted (B1-1).")
    flagged = a.route in FLAG_ROUTES
    harms: list[str] = []
    if flagged:
        for rel in [a.primary_relation, *a.secondary_relations]:
            if rel and _REL_TO_HARM[rel] not in harms:
                harms.append(_REL_TO_HARM[rel])
        hi = {h.id for h in a.hi_types}
        hp = {h.id for h in a.harm_pathways}
        if a.features.stance == "mocks" and "mockery_dark_humor" not in harms:
            harms.append("mockery_dark_humor")
        if "HP-03" in hp and "victim_identification" not in harms:
            harms.append("victim_identification")
        if "HI-TYPE-02" in hi and "denial_or_disinformation" not in harms:
            harms.append("denial_or_disinformation")
    tone = ("reporting" if a.features.stance in ("reports", "quotes_to_condemn")
            else "testimony" if a.exclusion == "B2-1"
            else "awareness" if a.exclusion == "B2-2"
            else "humorous_ironic" if a.features.stance == "mocks" else "serious")
    conf = min(a.elements.A.confidence, a.elements.B.confidence) if flagged else a.elements.A.confidence
    return Classification(
        harm_types=harms,
        tone=tone,
        claim_status="unverified_allegation" if a.primary_relation == "SV-REL-1" else "no_claim",
        victims=["group"] if a.features.target == "group" else ["unidentifiable"],
        harm_potential={"urgent": 3, "high": 3, "standard": 2, "none": 0}[a.priority],
        confidence="low" if conf < 0.5 else "medium" if conf < 0.8 else "high",
        summary=a.reviewer_summary,
        rationale=f"Route {a.route}; cited: {', '.join(a.cited_ids) or 'none'}. {a.notes}".strip(),
    )
