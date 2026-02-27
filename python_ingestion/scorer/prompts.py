"""LLM prompt templates for five-dimension scoring.

Each dimension prompt asks the LLM to:
1. Score 0-100 based on the grant opportunity text
2. Extract direct evidence citations from the text
3. Return structured JSON: {"score": int, "evidence_citations": ["quote1", "quote2"]}
"""

# Mission Fit (25%) - Alignment with VTKL's core capabilities
MISSION_FIT_PROMPT = """You are evaluating a government grant opportunity for VTKL, a small business specializing in:
- AI workflows and automation
- Data governance and management
- Agent configuration and orchestration
- Decision support systems
- MLOps and machine learning operations

Score the opportunity 0-100 on MISSION FIT based on how well it aligns with VTKL's core capabilities.

Scoring guidelines:
- 90-100: Excellent alignment - directly matches 4+ core capabilities
- 75-89: Strong alignment - clearly matches 2-3 core capabilities
- 50-74: Moderate alignment - some overlap with 1-2 capabilities
- 25-49: Weak alignment - tangential or vague connection
- 0-24: No alignment - unrelated to VTKL's focus

Extract 2-3 direct quotes from the text that justify your score.

Grant opportunity text:
{grant_text}

Return your response as valid JSON:
{{"score": <int 0-100>, "evidence_citations": ["quote1", "quote2"]}}"""


# Eligibility (25%) - Based on pre-assessed eligibility result
# Note: This dimension is handled differently - score is auto-calculated from EligibilityResult
# No LLM call is made for this dimension
ELIGIBILITY_PROMPT = """This prompt is not used - eligibility is auto-calculated from EligibilityResult."""


# Technical Alignment (20%) - Match to technical requirements
TECHNICAL_ALIGNMENT_PROMPT = """You are evaluating technical requirements for a government grant opportunity.

Score the opportunity 0-100 on TECHNICAL ALIGNMENT based on:
- Clarity and specificity of technical requirements
- Match with modern software engineering practices
- Feasibility of technical deliverables
- Technology stack alignment (cloud, AI/ML, APIs, automation)

Scoring guidelines:
- 90-100: Excellent - clear technical specs matching VTKL's stack (AI/ML, cloud, APIs, automation)
- 75-89: Strong - well-defined technical needs with good alignment
- 50-74: Moderate - some technical detail, partial alignment
- 25-49: Weak - vague technical requirements or poor fit
- 0-24: No alignment - incompatible or unclear technical needs

Extract 2-3 direct quotes about technical requirements from the text.

Grant opportunity text:
{grant_text}

Return your response as valid JSON:
{{"score": <int 0-100>, "evidence_citations": ["quote1", "quote2"]}}"""


# Financial Viability (15%) - Award size and financial fit
FINANCIAL_VIABILITY_PROMPT = """You are evaluating financial fit for a grant opportunity for VTKL, a small business with:
- Minimum capacity: $100,000
- Maximum capacity: $5,000,000
- Preferred range: $500,000 - $2,000,000

Score the opportunity 0-100 on FINANCIAL VIABILITY based on award amount and financial fit.

Scoring guidelines:
- 90-100: Ideal - award in preferred range ($500K-$2M)
- 75-89: Good - award within capacity but outside preferred range
- 50-74: Marginal - award at edges of capacity range
- 25-49: Poor - award significantly outside capacity (too large or too small)
- 0-24: Not viable - award well outside capacity range

Extract 1-2 direct quotes about award amounts, funding levels, or contract value from the text.

Grant opportunity text:
{grant_text}

Return your response as valid JSON:
{{"score": <int 0-100>, "evidence_citations": ["quote1", "quote2"]}}"""


# Strategic Value (15%) - Long-term relationship potential
STRATEGIC_VALUE_PROMPT = """You are evaluating strategic value of a government grant opportunity.

Score the opportunity 0-100 on STRATEGIC VALUE based on:
- Multi-year or IDIQ contract potential
- High-value agency relationships (DOD, Navy, Air Force, NASA, DOE, Intelligence)
- Innovation/R&D opportunities with follow-on potential
- Teaming and growth opportunities
- Prime contractor positioning

Scoring guidelines:
- 90-100: Exceptional - multi-year IDIQ with high-value agency and innovation focus
- 75-89: High value - 2+ strategic factors present
- 50-74: Moderate value - 1 strategic factor present
- 25-49: Low value - limited strategic benefit
- 0-24: Minimal value - no strategic factors

Extract 1-3 direct quotes about strategic aspects (contract type, agency, duration, innovation, teaming).

Grant opportunity text:
{grant_text}

Return your response as valid JSON:
{{"score": <int 0-100>, "evidence_citations": ["quote1", "quote2"]}}"""


def get_prompt_for_dimension(dimension: str, grant_text: str) -> str:
    """Get the prompt for a specific scoring dimension.
    
    Args:
        dimension: One of "mission_fit", "technical_alignment", "financial_viability", "strategic_value"
        grant_text: Full grant opportunity text to evaluate
        
    Returns:
        Formatted prompt string
        
    Raises:
        ValueError: If dimension is invalid or is "eligibility" (handled separately)
    """
    prompts = {
        "mission_fit": MISSION_FIT_PROMPT,
        "technical_alignment": TECHNICAL_ALIGNMENT_PROMPT,
        "financial_viability": FINANCIAL_VIABILITY_PROMPT,
        "strategic_value": STRATEGIC_VALUE_PROMPT,
    }
    
    if dimension == "eligibility":
        raise ValueError("Eligibility dimension does not use LLM - calculated from EligibilityResult")
    
    if dimension not in prompts:
        raise ValueError(f"Invalid dimension: {dimension}. Must be one of {list(prompts.keys())}")
    
    return prompts[dimension].format(grant_text=grant_text)
