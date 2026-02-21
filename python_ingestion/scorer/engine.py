"""Weighted LLM-based scoring engine for grant opportunities.

Implements five-dimension scoring with evidence-based citations.
"""

from datetime import datetime, timezone
from typing import List, Tuple
from models.grant_opportunity import GrantOpportunity
from models.eligibility_result import EligibilityResult
from models.scoring_result import ScoringResult, DimensionScore
from .weights import DEFAULT_WEIGHTS, ScoringWeights
from .semantic_map import find_semantic_matches, get_vtkl_focus_areas


def score_opportunity(
    opportunity: GrantOpportunity,
    eligibility: EligibilityResult,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
    llm_model: str = "rule-based-v1.0"
) -> ScoringResult:
    """Score grant opportunity across five weighted dimensions.
    
    Dimensions:
    1. Mission Fit (default 25%): Alignment with VTKL's core capabilities
    2. Eligibility (default 25%): Based on eligibility assessment
    3. Technical Alignment (default 20%): Match to technical requirements
    4. Financial Viability (default 15%): Award size and financial fit
    5. Strategic Value (default 15%): Long-term relationship potential
    
    Args:
        opportunity: Grant opportunity to score
        eligibility: Eligibility assessment result
        weights: Scoring weights configuration
        llm_model: Model identifier (for tracking)
        
    Returns:
        ScoringResult with dimension scores and composite score
    """
    
    # Score each dimension
    mission_fit = _score_mission_fit(opportunity)
    eligibility_score = _score_eligibility(eligibility, opportunity)
    technical_alignment = _score_technical_alignment(opportunity)
    financial_viability = _score_financial_viability(opportunity)
    strategic_value = _score_strategic_value(opportunity)
    
    # Apply penalty for hard blocker cases
    # If eligibility is 0 due to hard blockers (8(a), HUBZone, entity type, security),
    # significantly reduce other dimensions since opportunity is fundamentally inaccessible
    if not eligibility.is_eligible:
        # Check for different types of critical blockers
        has_certification_blocker = any(
            "8(a)" in b or "HUBZone" in b or "HARD BLOCKER" in b
            for b in eligibility.blockers
        )
        
        has_naics_blocker = any(
            "NAICS" in b or "naics" in b.lower()
            for b in eligibility.blockers
        )
        
        has_entity_or_security_blocker = any(
            "entity type" in b.lower() or "Top Secret" in b or "IL5" in b or "IL6" in b
            for b in eligibility.blockers
        )
        
        if has_certification_blocker or has_entity_or_security_blocker:
            # Apply 80% penalty to mission fit and technical alignment
            # These opportunities are completely inaccessible
            mission_fit = DimensionScore(
                score=mission_fit.score * 0.2,
                evidence_citations=mission_fit.evidence_citations
            )
            technical_alignment = DimensionScore(
                score=technical_alignment.score * 0.2,
                evidence_citations=technical_alignment.evidence_citations
            )
            strategic_value = DimensionScore(
                score=strategic_value.score * 0.1,
                evidence_citations=strategic_value.evidence_citations
            )
        elif has_naics_blocker:
            # NAICS mismatch is serious - apply 50% penalty
            mission_fit = DimensionScore(
                score=mission_fit.score * 0.5,
                evidence_citations=mission_fit.evidence_citations
            )
            technical_alignment = DimensionScore(
                score=technical_alignment.score * 0.4,
                evidence_citations=technical_alignment.evidence_citations
            )
    
    # Calculate weighted composite score
    composite_score = (
        mission_fit.score * weights.mission_fit +
        eligibility_score.score * weights.eligibility +
        technical_alignment.score * weights.technical_alignment +
        financial_viability.score * weights.financial_viability +
        strategic_value.score * weights.strategic_value
    )
    
    # Determine verdict based on thresholds
    verdict = _get_verdict(composite_score)
    
    return ScoringResult(
        opportunity_id=opportunity.source_opportunity_id,
        mission_fit=mission_fit,
        eligibility=eligibility_score,
        technical_alignment=technical_alignment,
        financial_viability=financial_viability,
        strategic_value=strategic_value,
        composite_score=round(composite_score, 2),
        verdict=verdict,
        scored_at=datetime.now(timezone.utc),
        scoring_weights_version=weights.version,
        llm_model=llm_model
    )


def _score_mission_fit(opportunity: GrantOpportunity) -> DimensionScore:
    """Score alignment with VTKL's mission and core capabilities.
    
    VTKL focus areas:
    - AI workflows
    - Data governance
    - Agent configuration
    - Decision support systems
    - Workflow automation
    - MLOps
    """
    
    text = (opportunity.description or "") + " " + (opportunity.raw_text or "")
    
    # Find semantic matches
    matches = find_semantic_matches(text)
    vtkl_areas = get_vtkl_focus_areas()
    
    # Count how many VTKL focus areas are mentioned
    matched_areas = set()
    evidence_citations = []
    
    for category, capability, context in matches:
        if capability in vtkl_areas:
            matched_areas.add(capability)
            if len(evidence_citations) < 3:  # Limit to 3 citations
                evidence_citations.append(context)
    
    # Also check for direct focus area mentions
    text_lower = text.lower()
    for area in vtkl_areas:
        if area.lower() in text_lower and area not in matched_areas:
            matched_areas.add(area)
            if len(evidence_citations) < 3:
                ctx = _extract_quote(text, area)
                if ctx:
                    evidence_citations.append(ctx)
    
    # Score based on number of matched areas
    num_areas = len(vtkl_areas)
    num_matched = len(matched_areas)
    
    if num_matched == 0:
        score = 20.0  # Minimal alignment
    elif num_matched <= 2:
        score = 50.0  # Some alignment
    elif num_matched <= 4:
        score = 75.0  # Good alignment
    else:
        score = 95.0  # Excellent alignment
    
    # Boost for explicit mission-critical terms
    if any(term in text_lower for term in ["ai", "artificial intelligence", "machine learning"]):
        score = min(100.0, score + 10.0)
    
    if not evidence_citations:
        evidence_citations = [opportunity.title or "No specific evidence found"]
    
    return DimensionScore(
        score=score,
        evidence_citations=evidence_citations[:3]
    )


def _score_eligibility(eligibility: EligibilityResult, opportunity: GrantOpportunity) -> DimensionScore:
    """Score based on eligibility assessment.
    
    Scoring:
    - Hard blockers (8(a), HUBZone, wrong entity type, etc.) = 0
    - Multiple blockers = 0-10
    - Single blocker = 10-20
    - Warnings only = 60-80
    - Clean eligibility = 80-100
    - Favorable assets (NHO) = 100
    """
    
    if not eligibility.is_eligible:
        # Check for different types of blockers
        has_certification_blocker = any(
            "8(a)" in blocker or "HUBZone" in blocker or "HARD BLOCKER" in blocker or
            "certification" in blocker.lower() or "SDVOSB" in blocker or "WOSB" in blocker
            for blocker in eligibility.blockers
        )
        
        has_entity_type_blocker = any(
            "entity type" in blocker.lower() or "non-profit" in blocker.lower() or
            "academic" in blocker.lower() or "university" in blocker.lower()
            for blocker in eligibility.blockers
        )
        
        has_naics_blocker = any(
            "NAICS" in blocker or "naics" in blocker.lower()
            for blocker in eligibility.blockers
        )
        
        has_security_blocker = any(
            "security" in blocker.lower() or "clearance" in blocker.lower() or
            "IL5" in blocker or "IL6" in blocker or "Top Secret" in blocker
            for blocker in eligibility.blockers
        )
        
        # Critical blockers = 0 score
        if has_certification_blocker or has_entity_type_blocker or has_security_blocker:
            score = 0.0
        elif has_naics_blocker:
            score = 5.0  # NAICS mismatch is serious but might work as subawardee
        elif len(eligibility.blockers) > 2:
            score = 5.0
        else:
            score = 15.0
        
        evidence_citations = eligibility.blockers[:3] if eligibility.blockers else [
            "Not eligible based on constraint checks"
        ]
    else:
        # Eligible - score based on quality
        if eligibility.assets:
            score = 100.0  # Favorable factors like NHO
            evidence_citations = eligibility.assets[:3]
        elif eligibility.warnings:
            score = 70.0  # Eligible but with warnings
            evidence_citations = [
                f"Eligible with warnings: {w}" for w in eligibility.warnings[:2]
            ]
        else:
            score = 90.0  # Clean eligibility
            evidence_citations = ["Clean eligibility - all constraints met"]
        
        # Add participation path context
        if eligibility.participation_path:
            evidence_citations.insert(0, f"Path: {eligibility.participation_path}")
    
    return DimensionScore(
        score=score,
        evidence_citations=evidence_citations[:3]
    )


def _score_technical_alignment(opportunity: GrantOpportunity) -> DimensionScore:
    """Score technical capability match using semantic mapping."""
    
    text = (opportunity.description or "") + " " + (opportunity.raw_text or "")
    
    # Find all semantic matches
    matches = find_semantic_matches(text)
    
    if not matches:
        return DimensionScore(
            score=30.0,
            evidence_citations=["Limited technical detail in opportunity description"]
        )
    
    # Group by category
    categories_matched = set(cat for cat, _, _ in matches)
    
    # Score based on breadth and depth of matches
    num_categories = len(categories_matched)
    num_capabilities = len(matches)
    
    if num_categories >= 5 and num_capabilities >= 10:
        score = 95.0  # Excellent alignment
    elif num_categories >= 3 and num_capabilities >= 5:
        score = 80.0  # Strong alignment
    elif num_categories >= 2:
        score = 65.0  # Moderate alignment
    else:
        score = 40.0  # Weak alignment
    
    # Extract evidence
    evidence_citations = []
    for _, capability, context in matches[:3]:
        evidence_citations.append(f"{capability}: {context}")
    
    return DimensionScore(
        score=score,
        evidence_citations=evidence_citations if evidence_citations else [
            "General technical requirements"
        ]
    )


def _score_financial_viability(opportunity: GrantOpportunity) -> DimensionScore:
    """Score financial fit based on award amount and VTKL capacity.
    
    VTKL financial capacity:
    - Min: $100K
    - Max: $5M
    - Preferred: $500K - $2M
    """
    
    min_capacity = 100_000
    max_capacity = 5_000_000
    preferred_min = 500_000
    preferred_max = 2_000_000
    
    # Get award amount
    award_min = opportunity.award_amount_min or 0
    award_max = opportunity.award_amount_max or award_min
    
    if award_max == 0 and award_min == 0:
        # No financial info
        return DimensionScore(
            score=50.0,
            evidence_citations=["No award amount specified"]
        )
    
    avg_award = (award_min + award_max) / 2 if award_max > 0 else award_min
    
    # Score based on fit
    if avg_award < min_capacity:
        score = 20.0
        reason = f"Award too small (${avg_award:,.0f} < ${min_capacity:,.0f} capacity)"
    elif avg_award > max_capacity:
        score = 10.0
        reason = f"Award exceeds capacity (${avg_award:,.0f} > ${max_capacity:,.0f} max)"
    elif preferred_min <= avg_award <= preferred_max:
        score = 100.0
        reason = f"Ideal award range (${avg_award:,.0f})"
    elif min_capacity <= avg_award < preferred_min:
        # Scale based on proximity to preferred range
        proximity = (avg_award - min_capacity) / (preferred_min - min_capacity)
        score = 50.0 + (proximity * 30.0)  # 50-80 range
        reason = f"Below preferred range (${avg_award:,.0f})"
    else:  # preferred_max < avg_award <= max_capacity
        # Scale based on proximity to max
        proximity = (avg_award - preferred_max) / (max_capacity - preferred_max)
        score = 80.0 - (proximity * 30.0)  # 50-80 range
        reason = f"Large but manageable (${avg_award:,.0f})"
    
    evidence_citations = [reason]
    
    # Add total program funding context if available
    if opportunity.estimated_total_program_funding:
        total = opportunity.estimated_total_program_funding
        evidence_citations.append(f"Total program funding: ${total:,.0f}")
    
    return DimensionScore(
        score=score,
        evidence_citations=evidence_citations
    )


def _score_strategic_value(opportunity: GrantOpportunity) -> DimensionScore:
    """Score long-term strategic value and relationship potential."""
    
    text = (opportunity.description or "") + " " + (opportunity.raw_text or "")
    text_lower = text.lower()
    
    score = 50.0  # Baseline
    evidence_citations = []
    
    # Check for repeat/multi-year opportunities
    if any(term in text_lower for term in [
        "multi-year",
        "multi year",
        "idiq",
        "indefinite delivery",
        "blanket purchase",
        "bpa",
        "multiple awards"
    ]):
        score += 20.0
        evidence_citations.append("Multi-year or IDIQ contract potential")
    
    # Check for high-value agencies
    high_value_agencies = [
        "defense",
        "dod",
        "navy",
        "air force",
        "army",
        "nasa",
        "doe",
        "energy",
        "intelligence",
        "homeland security"
    ]
    
    agency_lower = (opportunity.agency or "").lower()
    if any(agency in agency_lower for agency in high_value_agencies):
        score += 15.0
        evidence_citations.append(f"High-value agency: {opportunity.agency}")
    
    # Check for innovation/R&D opportunities
    if any(term in text_lower for term in [
        "research and development",
        "r&d",
        "innovation",
        "prototype",
        "proof of concept",
        "pilot program"
    ]):
        score += 10.0
        evidence_citations.append("Innovation/R&D opportunity with follow-on potential")
    
    # Check for small business growth potential
    if any(term in text_lower for term in [
        "small business growth",
        "mentor-protege",
        "teaming encouraged",
        "prime contractor opportunity"
    ]):
        score += 10.0
        evidence_citations.append("Growth and teaming opportunities")
    
    # Cap at 100
    score = min(100.0, score)
    
    if not evidence_citations:
        evidence_citations = ["Standard strategic value"]
    
    return DimensionScore(
        score=score,
        evidence_citations=evidence_citations
    )


def _get_verdict(composite_score: float) -> str:
    """Determine verdict based on composite score thresholds.
    
    Thresholds:
    - GO: 80-100
    - SHAPE: 60-79
    - MONITOR: 40-59
    - NO-GO: 0-39
    """
    
    if composite_score >= 80:
        return "GO"
    elif composite_score >= 60:
        return "SHAPE"
    elif composite_score >= 40:
        return "MONITOR"
    else:
        return "NO-GO"


def _extract_quote(text: str, keyword: str, max_length: int = 150) -> str:
    """Extract a relevant quote containing the keyword.
    
    Args:
        text: Full text to search
        keyword: Keyword to find
        max_length: Maximum quote length
        
    Returns:
        Extracted quote or empty string
    """
    
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    
    idx = text_lower.find(keyword_lower)
    if idx == -1:
        return ""
    
    # Find sentence boundaries
    start = max(0, idx - 75)
    end = min(len(text), idx + 75)
    
    # Try to find sentence start
    period_before = text.rfind('. ', 0, idx)
    if period_before != -1 and period_before > start:
        start = period_before + 2
    
    # Try to find sentence end
    period_after = text.find('. ', idx)
    if period_after != -1 and period_after < end:
        end = period_after + 1
    
    quote = text[start:end].strip()
    
    if len(quote) > max_length:
        quote = quote[:max_length].strip() + "..."
    
    if start > 0:
        quote = "..." + quote
    
    return quote
