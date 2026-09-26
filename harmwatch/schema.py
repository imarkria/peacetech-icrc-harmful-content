"""Output schema shared by every classifier. Mirrors policy.md."""

from typing import Literal

from pydantic import BaseModel

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
