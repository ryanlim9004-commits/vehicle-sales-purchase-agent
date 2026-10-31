"""Versioned safety/review evidence, separate from advertisements and prices.

Exact year/variant applicability is deliberately conservative. Review coding is
an inspectable course policy, never a measured breakdown or crash probability.
"""
from datetime import date
from calendar import monthrange
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ROOT = Path(__file__).resolve().parent
ASPECTS = ('seat_support', 'ride_comfort', 'highway_noise', 'rear_space')
CODE_POINTS = {'negative': 0.0, 'mixed': 0.5, 'positive': 1.0}
REVIEW_POLICY = 'review-coding-v2.0: negative=0, mixed=0.5, positive=1; family means first; fixed four-aspect comfort denominator; at least two independent source families and two comfort aspects; unknown widens the bound'
RELIABILITY_POLICY = 'ownership-coding-v2.0: negative=0, mixed=0.5, positive=1; family means first; at least two independent source families with explicit ownership periods; not a failure rate'


class EvidenceFrame(BaseModel):
    # This base rejects invented fields and nonfinite score values.
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class Source(EvidenceFrame):
    # Source family prevents counting an article and its companion video twice.
    source_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    url: str
    author: str = Field(min_length=1)
    published_on: date | None = None
    published_month: str | None = Field(default=None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    locator: str = Field(min_length=1)

    @field_validator('url')
    @classmethod
    def https_url(cls, value):
        # Only ordinary source links, never local paths or active URL schemes.
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or not parsed.netloc:
            raise ValueError('Evidence needs an HTTPS source URL.')
        return value


class SafetyEvidence(EvidenceFrame):
    # Stars/protocol are displayed as context, not averaged across test periods.
    source: Source
    protocol: str
    tested_variant: str
    kind: Literal['ncap_report', 'manufacturer_equipment'] = 'ncap_report'
    stars: int | None = Field(default=None, ge=0, le=5)
    report_points: float | None = Field(default=None, ge=0, le=100)
    esc: bool | None = None
    aeb: bool | None = None
    curtain_airbags: bool | None = None
    limits: list[str] = Field(min_length=1)

    @model_validator(mode='after')
    def report_kind(self):
        if self.kind == 'manufacturer_equipment' and (self.stars is not None or self.report_points is not None):
            raise ValueError('An equipment brochure is not an NCAP crash-test rating.')
        return self


class ReviewEvidence(EvidenceFrame):
    # Observations remain attributed opinions with explicit test context.
    source: Source
    context: Literal['short_drive', 'extended_test_drive', 'owner_report']
    seat_support: Literal['positive', 'mixed', 'negative', 'unknown'] = 'unknown'
    ride_comfort: Literal['positive', 'mixed', 'negative', 'unknown'] = 'unknown'
    highway_noise: Literal['positive', 'mixed', 'negative', 'unknown'] = 'unknown'
    rear_space: Literal['positive', 'mixed', 'negative', 'unknown'] = 'unknown'
    reliability: Literal['positive', 'mixed', 'negative', 'unknown'] = 'unknown'
    ownership_months: int | None = Field(default=None, gt=0)
    distance_km: float | None = Field(default=None, ge=0)
    summary: str = Field(min_length=1, max_length=650)
    limits: list[str] = Field(min_length=1)

    @model_validator(mode='after')
    def ownership_scope(self):
        # A new-car road test cannot establish a long-term reliability opinion.
        if self.reliability != 'unknown' and (self.context != 'owner_report' or not self.ownership_months):
            raise ValueError('Reliability coding requires an attributed ownership period.')
        return self


class ModelEvidence(EvidenceFrame):
    # An evidence profile is research, not stock, a price quote or a sale offer.
    profile_id: str
    brand: str
    model: str
    generation: str
    years: list[int] = Field(min_length=1)
    variants: list[str] = Field(min_length=1)
    transmissions: list[str] = Field(min_length=1)
    automatic_matching: bool = True
    safety: SafetyEvidence | None = None
    reviews: list[ReviewEvidence] = Field(default_factory=list)
    limits: list[str] = Field(min_length=1)

    @model_validator(mode='after')
    def unique_sources(self):
        # Duplicate publications cannot inflate evidence counts.
        ids = [item.source.source_id for item in self.reviews]
        if len(ids) != len(set(ids)) or any(y < 1900 or y > 2100 for y in self.years):
            raise ValueError('Evidence has duplicate review IDs or an invalid year.')
        return self


class EvidenceCatalogue(EvidenceFrame):
    # Price data and review data have different dates and evidence meanings.
    schema_version: Literal[1]
    reviewed_on: date
    notice: str
    profiles: list[ModelEvidence]

    @model_validator(mode='after')
    def unique_profiles(self):
        ids = [p.profile_id for p in self.profiles]
        if len(ids) != len(set(ids)):
            raise ValueError('Evidence profile IDs must be unique.')
        return self


def normalized(value):
    # Normalize case/spacing only; no cross-trim or cross-generation fuzzy joins.
    return ' '.join(str(value).casefold().split())


def source_date(source):
    # Preserve month precision instead of inventing a publication day. For an
    # as-of check, conservatively require that whole month to have elapsed.
    if source.published_on:
        return source.published_on
    if source.published_month:
        year, month = map(int, source.published_month.split('-'))
        return date(year, month, monthrange(year, month)[1])
    return None


def load_catalogue(path=None):
    # Read saved evidence without fetching websites or caching customer facts.
    catalogue = EvidenceCatalogue.model_validate_json(Path(path or ROOT/'data/model_evidence_v2.json').read_text(encoding='utf-8'))
    seen = set()
    for p in catalogue.profiles:
        for y in p.years:
            for variant in p.variants:
                for transmission in p.transmissions:
                    identity = (normalized(p.brand), normalized(p.model), y, normalized(variant), normalized(transmission))
                    if p.automatic_matching and identity in seen:
                        raise ValueError('Evidence applicability overlaps; resolve it before scoring.')
                    if p.automatic_matching:
                        seen.add(identity)
        sources = [r.source for r in p.reviews] + ([p.safety.source] if p.safety else [])
        if any(source_date(s) is not None and source_date(s) > catalogue.reviewed_on for s in sources):
            raise ValueError('An evidence source is dated after its review date.')
    return catalogue


def _review_reference(reviews, kind):
    # Average within a source family first, so syndication cannot dominate.
    fields = ASPECTS if kind == 'comfort' else ('reliability',)
    aspects, counts, disagreements = {}, {}, []
    relevant = []
    for review in reviews:
        if kind == 'reliability' and (review.context != 'owner_report' or not review.ownership_months):
            continue
        if any(getattr(review, name) != 'unknown' for name in fields):
            relevant.append(review)
    for name in fields:
        families = {}
        codes = set()
        for review in relevant:
            code = getattr(review, name)
            if code != 'unknown':
                families.setdefault(review.source.family, []).append(CODE_POINTS[code])
                codes.add(code)
        family_means = [sum(values) / len(values) for values in families.values()]
        aspects[name] = sum(family_means) / len(family_means) if family_means else None
        counts[name] = len(family_means)
        if 'positive' in codes and 'negative' in codes:
            disagreements.append(name)
    families = sorted({review.source.family for review in relevant})
    known = [value for value in aspects.values() if value is not None]
    enough = len(families) >= 2 and len(known) >= (2 if kind == 'comfort' else 1)
    # A single owner remains visible as a note, not a standalone car-wide score.
    coverage = len(known) / len(fields) if enough else 0.0
    lower = sum(known) / len(fields) if enough else None
    return {'normalized_value': lower, 'data_coverage': coverage,
            'upper_bound': lower + 1 - coverage if enough else 1.0,
            'label': 'Review-based comfort reference' if kind == 'comfort' else 'Ownership-opinion reference; not a failure rate',
            'independent_source_families': families, 'aspect_values': aspects, 'aspect_source_counts': counts,
            'disagreements': disagreements, 'policy': REVIEW_POLICY if kind == 'comfort' else RELIABILITY_POLICY,
            'unknown_reason': None if enough else 'Insufficient applicable independent review evidence.',
            'sources': [review.source.url for review in relevant]}


def evidence_for_vehicle(vehicle, *, as_of, catalogue=None, research_profile_id=None):
    # Look up only a documented exact identity, never an adjacent model year.
    catalogue = catalogue or load_catalogue()
    getter = vehicle.get if isinstance(vehicle, dict) else lambda name: getattr(vehicle, name, None)
    profile = next((p for p in catalogue.profiles
                    if not getter('simulation') and (p.profile_id == research_profile_id if research_profile_id else p.automatic_matching)
                    and normalized(p.brand) == normalized(getter('brand')) and normalized(p.model) == normalized(getter('model'))
                    and getter('year') in p.years and normalized(getter('variant')) in {normalized(v) for v in p.variants}
                    and normalized(getter('transmission')) in {normalized(v) for v in p.transmissions}), None)
    safety = profile.safety if profile and profile.safety and source_date(profile.safety.source) is not None and source_date(profile.safety.source) <= as_of else None
    reviews = [r for r in profile.reviews if source_date(r.source) is not None and source_date(r.source) <= as_of] if profile else []
    features = {name: getattr(safety, name) if safety else None for name in ('esc', 'aeb', 'curtain_airbags')}
    known = [value for value in features.values() if value is not None]
    # Score supported equipment only; missing equipment is not asserted absent.
    safety_value = sum(known) / 3 if known else None
    safety_coverage = len(known) / 3
    return {'profile_id': profile.profile_id if profile else None, 'evidence_reviewed_on': catalogue.reviewed_on.isoformat(),
            'scope': {'generation': profile.generation, 'years': profile.years, 'variants': profile.variants} if profile else None,
            'safety': {'normalized_value': safety_value, 'data_coverage': safety_coverage,
                       'upper_bound': (safety_value or 0) + 1 - safety_coverage, 'features': features,
                       'label': 'Equipment reference: ESC, AEB and curtain airbags; not crash probability',
                       'policy': 'Each equipment item has weight 1/3. Unknown widens the bound; it is not false. NCAP stars are context only.',
                       'report': safety.model_dump(mode='json') if safety else None,
                       'unknown_reason': None if len(known) == 3 else 'Exact-scope safety equipment is incomplete or unavailable.'},
            'comfort': _review_reference(reviews, 'comfort'), 'reliability': _review_reference(reviews, 'reliability'),
            'reviews': [r.model_dump(mode='json') for r in reviews],
            'limits': profile.limits if profile else ['No exact-year/variant evidence profile; nearby generations are not substituted.'],
            'catalogue_notice': catalogue.notice}
