"""LLM-based scoring engine for grant opportunities using Anthropic Claude.

Implements five-dimension scoring with evidence-based citations.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

import anthropic

from models.grant_opportunity import GrantOpportunity
from models.eligibility_result import EligibilityResult
from models.scoring_result import ScoringResult, DimensionScore
from .weights import DEFAULT_WEIGHTS, ScoringWeights
from .prompts import get_prompt_for_dimension


# Model configuration
DEFAULT_LLM_MODEL = "claude-haiku-4-5"


def score_opportunity(
    opportunity: GrantOpportunity,
    eligibility: EligibilityResult,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
    llm_model: str = DEFAULT_LLM_MODEL
) -> ScoringResult:
    """Score grant opportunity across five weighted dimensions using LLM.
    
    Dimensions:
    1. Mission Fit (default 25%): Alignment with VTKL's core capabilities
    2. Eligibility (default 25%): Based on eligibility assessment (auto-calculated)
    3. Technical Alignment (default 20%): Match to technical requirements
    4. Financial Viability (default 15%): Award size and financial fit
    5. Strategic Value (default 15%): Long-term relationship potential
    
    Args:
        opportunity: Grant opportunity to score
        eligibility: Eligibility assessment result
        weights: Scoring weights configuration
        llm_model: Anthropic model to use (default: claude-haiku-4-5)
        
    Returns:
        ScoringResult with dimension scores and composite score
    """
    
    # Prepare grant text for LLM
    grant_text = _prepare_grant_text(opportunity)
    
    # Initialize Anthropic client
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    # Score eligibility dimension (auto-calculated, no LLM call)
    eligibility_score = _score_eligibility(eligibility, opportunity)
    
    # Score other 4 dimensions via LLM (skip if ineligible to save API calls)
    if not eligibility.is_eligible:
        # For ineligible opportunities, set eligibility score to 0 and skip LLM for efficiency
        # Still call LLM for other dimensions but expect low scores
        mission_fit = _score_dimension_with_llm(client, "mission_fit", grant_text, llm_model)
        technical_alignment = _score_dimension_with_llm(client, "technical_alignment", grant_text, llm_model)
        financial_viability = _score_dimension_with_llm(client, "financial_viability", grant_text, llm_model)
        strategic_value = _score_dimension_with_llm(client, "strategic_value", grant_text, llm_model)
        
        # Apply penalty for ineligibility
        mission_fit = _apply_ineligibility_penalty(mission_fit)
        technical_alignment = _apply_ineligibility_penalty(technical_alignment)
        financial_viability = _apply_ineligibility_penalty(financial_viability)
        strategic_value = _apply_ineligibility_penalty(strategic_value)
    else:
        # Eligible - score all dimensions normally
        mission_fit = _score_dimension_with_llm(client, "mission_fit", grant_text, llm_model)
        technical_alignment = _score_dimension_with_llm(client, "technical_alignment", grant_text, llm_model)
        financial_viability = _score_dimension_with_llm(client, "financial_viability", grant_text, llm_model)
        strategic_value = _score_dimension_with_llm(client, "strategic_value", grant_text, llm_model)
    
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


def _prepare_grant_text(opportunity: GrantOpportunity) -> str:
    """Prepare comprehensive grant text for LLM evaluation.
    
    Args:
        opportunity: Grant opportunity
        
    Returns:
        Combined text with title, agency, description, and raw_text
    """
    parts = []
    
    if opportunity.title:
        parts.append(f"Title: {opportunity.title}")
    
    if opportunity.agency:
        parts.append(f"Agency: {opportunity.agency}")
    
    if opportunity.description:
        parts.append(f"Description: {opportunity.description}")
    
    if opportunity.award_amount_min or opportunity.award_amount_max:
        award_min = opportunity.award_amount_min or 0
        award_max = opportunity.award_amount_max or award_min
        if award_max > 0:
            parts.append(f"Award Amount: ${award_min:,.0f} - ${award_max:,.0f}")
        else:
            parts.append(f"Award Amount: ${award_min:,.0f}")
    
    if opportunity.raw_text:
        parts.append(f"Full Text: {opportunity.raw_text}")
    
    return "\n\n".join(parts)


def _score_dimension_with_llm(
    client: anthropic.Anthropic,
    dimension: str,
    grant_text: str,
    model: str
) -> DimensionScore:
    """Score a single dimension using Anthropic LLM.
    
    Args:
        client: Anthropic client instance
        dimension: Dimension name (mission_fit, technical_alignment, etc.)
        grant_text: Prepared grant text
        model: Model identifier
        
    Returns:
        DimensionScore with score and evidence citations
    """
    
    # Get prompt for this dimension
    prompt = get_prompt_for_dimension(dimension, grant_text)
    
    # Call Anthropic API
    try:
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Parse JSON response
        response_text = message.content[0].text
        result = json.loads(response_text)
        
        score = float(result["score"])
        citations = result["evidence_citations"]
        
        # Validate score range
        score = max(0.0, min(100.0, score))
        
        # Ensure we have at least one citation
        if not citations:
            citations = ["No specific evidence provided"]
        
        return DimensionScore(
            score=score,
            evidence_citations=citations[:3]  # Limit to 3 citations
        )
        
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        # Fallback if LLM response is malformed
        return DimensionScore(
            score=50.0,
            evidence_citations=[f"LLM response parsing error: {str(e)}"]
        )
    except Exception as e:
        # Fallback for API errors
        return DimensionScore(
            score=50.0,
            evidence_citations=[f"LLM API error: {str(e)}"]
        )


def _score_eligibility(eligibility: EligibilityResult, opportunity: GrantOpportunity) -> DimensionScore:
    """Score based on eligibility assessment (auto-calculated, no LLM).
    
    Per VTK-105 acceptance criteria #5:
    - EligibilityResult.is_eligible=False → automatic eligibility score=0 (skip LLM call)
    
    Scoring:
    - Hard blockers (8(a), HUBZone, wrong entity type, etc.) = 0
    - Multiple blockers = 0-10
    - Single blocker = 10-20
    - Warnings only = 60-80
    - Clean eligibility = 80-100
    - Favorable assets (NHO) = 100
    """
    
    if not eligibility.is_eligible:
        # Automatic score = 0 for ineligible opportunities
        score = 0.0
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


def _apply_ineligibility_penalty(dimension_score: DimensionScore, penalty_factor: float = 0.2) -> DimensionScore:
    """Apply penalty to dimension score for ineligible opportunities.
    
    Args:
        dimension_score: Original dimension score
        penalty_factor: Factor to multiply score by (default 0.2 = 80% penalty)
        
    Returns:
        New DimensionScore with penalized score
    """
    return DimensionScore(
        score=dimension_score.score * penalty_factor,
        evidence_citations=dimension_score.evidence_citations
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


# Optional: Function to save scoring result to database
def score_and_save(
    opportunity: GrantOpportunity,
    eligibility: EligibilityResult,
    db_client,  # Supabase client or similar
    weights: ScoringWeights = DEFAULT_WEIGHTS,
    llm_model: str = DEFAULT_LLM_MODEL
) -> ScoringResult:
    """Score opportunity and save result to database.
    
    Also updates grant status to "scored".
    
    Args:
        opportunity: Grant opportunity to score
        eligibility: Eligibility assessment result
        db_client: Database client for saving results
        weights: Scoring weights configuration
        llm_model: Anthropic model to use
        
    Returns:
        ScoringResult with dimension scores and composite score
    """
    
    # Score the opportunity
    result = score_opportunity(opportunity, eligibility, weights, llm_model)
    
    # Save to database
    scoring_data = {
        "opportunity_id": result.opportunity_id,
        "mission_fit_score": result.mission_fit.score,
        "mission_fit_citations": result.mission_fit.evidence_citations,
        "eligibility_score": result.eligibility.score,
        "eligibility_citations": result.eligibility.evidence_citations,
        "technical_alignment_score": result.technical_alignment.score,
        "technical_alignment_citations": result.technical_alignment.evidence_citations,
        "financial_viability_score": result.financial_viability.score,
        "financial_viability_citations": result.financial_viability.evidence_citations,
        "strategic_value_score": result.strategic_value.score,
        "strategic_value_citations": result.strategic_value.evidence_citations,
        "composite_score": result.composite_score,
        "verdict": result.verdict,
        "scoring_weights_version": result.scoring_weights_version,
        "llm_model": result.llm_model,
        "scored_at": result.scored_at.isoformat(),
    }
    
    db_client.table("scoring_results").insert(scoring_data).execute()
    
    # Update grant status to "scored"
    db_client.table("grant_opportunities").update(
        {"status": "scored"}
    ).eq("source_opportunity_id", opportunity.source_opportunity_id).execute()
    
    return result
