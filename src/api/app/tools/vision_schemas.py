"""Pydantic models for GPT-4o vision damage extraction."""

from enum import Enum
from pydantic import BaseModel, Field


class DamageType(str, Enum):
    DENT = "dent"
    SCRATCH = "scratch"
    BROKEN_GLASS = "broken_glass"
    CRACK = "crack"
    STRUCTURAL = "structural"
    WATER_DAMAGE = "water_damage"
    FIRE_DAMAGE = "fire_damage"
    OTHER = "other"


class DamageExtraction(BaseModel):
    """Structured output from GPT-4o vision analysis of a damage photo."""

    damage_type: DamageType = Field(description="Primary type of damage visible")
    severity: int = Field(ge=1, le=5, description="Severity 1 (cosmetic) to 5 (total loss)")
    affected_components: list[str] = Field(
        description="List of affected vehicle/property components"
    )
    visible_text: str = Field(
        default="", description="Any text visible in the photo (plates, VINs, signs)"
    )
    notes: str = Field(
        default="", max_length=200, description="Brief additional observations"
    )


VISION_SYSTEM_PROMPT = """You are analyzing a damage photo for an insurance claim.
Extract structured information about the visible damage.
Return ONLY valid JSON matching this schema:
{
  "damage_type": "dent|scratch|broken_glass|crack|structural|water_damage|fire_damage|other",
  "severity": 1-5 (1=cosmetic, 5=total loss/destruction),
  "affected_components": ["list", "of", "components"],
  "visible_text": "any readable text in photo",
  "notes": "brief observations, max 200 chars"
}
Do NOT attempt face recognition or biometric extraction."""
