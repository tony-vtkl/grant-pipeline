"""Hard eligibility filter for VTKL grant opportunities.

Implements six constraint checks as defined in VTK-66 contract.
"""

from datetime import datetime, timezone
from typing import Optional
from models.grant_opportunity import GrantOpportunity
from models.eligibility_result import EligibilityResult, ConstraintCheck
from .vtkl_profile import VTKL_PROFILE


def assess_eligibility(opportunity: GrantOpportunity) -> EligibilityResult:
    """Assess opportunity eligibility against VTKL profile.
    
    Performs six constraint checks:
    1. Entity type compatibility
    2. SAM registration validity
    3. NAICS code match
    4. Security posture compatibility
    5. Location eligibility
    6. Certification requirements (CRITICAL BLOCKER: 8(a)/HUBZone)
    
    Args:
        opportunity: Grant opportunity to assess
        
    Returns:
        EligibilityResult with detailed check results
    """
    
    # Run all six constraint checks
    entity_check = _check_entity_type(opportunity)
    location_check = _check_location(opportunity)
    sam_check = _check_sam_registration(opportunity)
    naics_check = _check_naics_match(opportunity)
    security_check = _check_security_posture(opportunity)
    certification_check = _check_certifications(opportunity)
    
    # Collect all checks
    all_checks = [
        entity_check,
        location_check,
        sam_check,
        naics_check,
        security_check,
        certification_check
    ]
    
    # Overall eligibility: all checks must pass
    is_eligible = all(check.is_met for check in all_checks)
    
    # Determine participation path
    participation_path = _determine_participation_path(
        is_eligible,
        opportunity,
        naics_check.is_met,
        certification_check.is_met
    )
    
    # Categorize findings
    blockers = []
    assets = []
    warnings = []
    
    for check in all_checks:
        if not check.is_met:
            blockers.append(f"{check.constraint_name}: {check.details}")
    
    # Check for favorable factors
    if location_check.is_met and VTKL_PROFILE["location"]["nho_eligible"]:
        if _is_nho_set_aside(opportunity):
            assets.append("NHO (Native Hawaiian Organization) set-aside eligible")
    
    if naics_check.is_met:
        assets.append("NAICS code alignment with VTKL capabilities")
    
    # Check for warnings (soft issues)
    if opportunity.award_amount_max:
        max_award = opportunity.award_amount_max
        vtkl_max = VTKL_PROFILE["financial_capacity"]["max_award"]
        if max_award > vtkl_max:
            warnings.append(
                f"Award amount (${max_award:,.0f}) exceeds VTKL capacity (${vtkl_max:,.0f})"
            )
    
    return EligibilityResult(
        opportunity_id=opportunity.source_opportunity_id,
        is_eligible=is_eligible,
        participation_path=participation_path,
        entity_type_check=entity_check,
        location_check=location_check,
        sam_active_check=sam_check,
        naics_match_check=naics_check,
        security_posture_check=security_check,
        certification_check=certification_check,
        blockers=blockers,
        assets=assets,
        warnings=warnings,
        evaluated_at=datetime.now(timezone.utc),
        vtkl_profile_version="1.0"
    )


def _check_entity_type(opportunity: GrantOpportunity) -> ConstraintCheck:
    """Check if VTKL's entity type matches opportunity requirements."""
    
    # VTKL is a for-profit corporation
    vtkl_type = VTKL_PROFILE["entity_type"]
    
    # Check opportunity requirements (look in description/raw_text)
    text = (opportunity.description or "") + " " + (opportunity.raw_text or "")
    text_lower = text.lower()
    
    # Blockers: requires non-profit, academic, or government entity
    requires_nonprofit = any(term in text_lower for term in [
        "non-profit only",
        "nonprofit only",
        "501(c)(3) required",
        "charitable organization"
    ])
    
    requires_academic = any(term in text_lower for term in [
        "university only",
        "academic institution required",
        "r1 institution"
    ])
    
    requires_government = any(term in text_lower for term in [
        "government entity only",
        "federal agency",
        "state agency only"
    ])
    
    if requires_nonprofit or requires_academic or requires_government:
        return ConstraintCheck(
            constraint_name="Entity Type",
            is_met=False,
            details="Opportunity requires non-profit/academic/government entity; VTKL is for-profit"
        )
    
    return ConstraintCheck(
        constraint_name="Entity Type",
        is_met=True,
        details="For-profit corporation (compatible)"
    )


def _check_sam_registration(opportunity: GrantOpportunity) -> ConstraintCheck:
    """Check if VTKL's SAM registration is active through opportunity deadline."""
    
    sam_expiry = VTKL_PROFILE["sam_registration"]["expiry_date"]
    
    # If opportunity has a deadline, check if SAM is active through then
    if opportunity.response_deadline:
        deadline = opportunity.response_deadline
        if sam_expiry < deadline:
            return ConstraintCheck(
                constraint_name="SAM Registration",
                is_met=False,
                details=f"SAM expires {sam_expiry.date()} before deadline {deadline.date()}"
            )
        
        return ConstraintCheck(
            constraint_name="SAM Registration",
            is_met=True,
            details=f"Active through {sam_expiry.date()} (Entity ID: {VTKL_PROFILE['sam_registration']['entity_id']})"
        )
    
    # No deadline specified, check if currently active
    if sam_expiry > datetime.now(timezone.utc):
        return ConstraintCheck(
            constraint_name="SAM Registration",
            is_met=True,
            details=f"Active through {sam_expiry.date()}"
        )
    
    return ConstraintCheck(
        constraint_name="SAM Registration",
        is_met=False,
        details=f"SAM registration expired {sam_expiry.date()}"
    )


def _check_naics_match(opportunity: GrantOpportunity) -> ConstraintCheck:
    """Check if opportunity allows VTKL's NAICS codes."""
    
    vtkl_primary = VTKL_PROFILE["naics_primary"]
    vtkl_optional = VTKL_PROFILE["naics_optional"]
    all_vtkl_naics = vtkl_primary + vtkl_optional
    
    opp_naics = opportunity.naics_codes or []
    
    if not opp_naics:
        # No NAICS codes specified - assume compatible
        return ConstraintCheck(
            constraint_name="NAICS Match",
            is_met=True,
            details="No NAICS restrictions specified"
        )
    
    # Check for any matches
    matches = [code for code in opp_naics if code in all_vtkl_naics]
    
    if matches:
        primary_matches = [code for code in matches if code in vtkl_primary]
        if primary_matches:
            return ConstraintCheck(
                constraint_name="NAICS Match",
                is_met=True,
                details=f"Primary NAICS match: {', '.join(primary_matches)}"
            )
        else:
            return ConstraintCheck(
                constraint_name="NAICS Match",
                is_met=True,
                details=f"Optional NAICS match: {', '.join(matches)}"
            )
    
    return ConstraintCheck(
        constraint_name="NAICS Match",
        is_met=False,
        details=f"Required NAICS {', '.join(opp_naics[:3])} not in VTKL profile"
    )


def _check_security_posture(opportunity: GrantOpportunity) -> ConstraintCheck:
    """Check if VTKL can meet security clearance requirements."""
    
    vtkl_posture = VTKL_PROFILE["security_posture"]  # ["IL2", "IL3", "IL4"]
    
    # Check opportunity requirements
    text = (opportunity.description or "") + " " + (opportunity.raw_text or "")
    text_upper = text.upper()
    
    # Look for security requirements
    requires_il5 = "IL5" in text_upper or "IMPACT LEVEL 5" in text_upper
    requires_il6 = "IL6" in text_upper or "IMPACT LEVEL 6" in text_upper
    requires_ts = any(term in text_upper for term in [
        "TOP SECRET",
        "TS/SCI",
        "TS CLEARANCE"
    ])
    
    if requires_il5 or requires_il6 or requires_ts:
        return ConstraintCheck(
            constraint_name="Security Posture",
            is_met=False,
            details="Requires IL5/IL6/TS clearance; VTKL supports IL2-IL4"
        )
    
    # Check for IL2-IL4 mentions (which VTKL can handle)
    requires_security = any(f"IL{level}" in text_upper for level in [2, 3, 4])
    
    if requires_security:
        return ConstraintCheck(
            constraint_name="Security Posture",
            is_met=True,
            details="IL2-IL4 capable (meets requirement)"
        )
    
    return ConstraintCheck(
        constraint_name="Security Posture",
        is_met=True,
        details="No specific security posture required"
    )


def _check_location(opportunity: GrantOpportunity) -> ConstraintCheck:
    """Check if VTKL's Hawaii location is eligible."""
    
    vtkl_state = VTKL_PROFILE["location"]["state"]
    vtkl_nho = VTKL_PROFILE["location"]["nho_eligible"]
    
    text = (opportunity.description or "") + " " + (opportunity.raw_text or "")
    text_lower = text.lower()
    
    # Check for geographic restrictions
    excludes_hi = any(term in text_lower for term in [
        "excluding hawaii",
        "hawaii not eligible",
        "continental us only",
        "conus only"
    ])
    
    if excludes_hi:
        return ConstraintCheck(
            constraint_name="Location",
            is_met=False,
            details="Opportunity excludes Hawaii"
        )
    
    # Check for NHO set-aside (highly favorable)
    is_nho = _is_nho_set_aside(opportunity)
    
    if is_nho and vtkl_nho:
        return ConstraintCheck(
            constraint_name="Location",
            is_met=True,
            details="Hawaii-based, NHO-eligible (HIGHLY FAVORABLE)"
        )
    
    return ConstraintCheck(
        constraint_name="Location",
        is_met=True,
        details="Hawaii-based (geographically eligible)"
    )


def _check_certifications(opportunity: GrantOpportunity) -> ConstraintCheck:
    """Check certification requirements. CRITICAL: 8(a) and HUBZone are HARD BLOCKERS."""
    
    vtkl_certs = VTKL_PROFILE["certifications"]
    
    # Check set_aside_type field
    set_aside = (opportunity.set_aside_type or "").lower()
    
    # Also check description/raw_text
    text = (opportunity.description or "") + " " + (opportunity.raw_text or "")
    text_lower = text.lower()
    
    # CRITICAL BLOCKERS
    requires_8a = any(term in set_aside for term in ["8(a)", "8a"]) or \
                  any(term in text_lower for term in [
                      "8(a) only",
                      "8a only",
                      "sba 8(a)",
                      "requires 8(a)",
                      "must be 8(a) certified"
                  ])
    
    requires_hubzone = "hubzone" in set_aside or \
                       any(term in text_lower for term in [
                           "hubzone only",
                           "hubzone required",
                           "must be hubzone certified"
                       ])
    
    if requires_8a and not vtkl_certs.get("8(a)", False):
        return ConstraintCheck(
            constraint_name="Certifications",
            is_met=False,
            details="HARD BLOCKER: Requires 8(a) certification (VTKL not certified)"
        )
    
    if requires_hubzone and not vtkl_certs.get("HUBZone", False):
        return ConstraintCheck(
            constraint_name="Certifications",
            is_met=False,
            details="HARD BLOCKER: Requires HUBZone certification (VTKL not certified)"
        )
    
    # Check for other certifications (less critical)
    requires_sdvosb = "sdvosb" in set_aside or "service-disabled veteran" in text_lower
    requires_wosb = "wosb" in set_aside or "women-owned small business" in text_lower
    
    if requires_sdvosb and not vtkl_certs.get("sdvosb", False):
        return ConstraintCheck(
            constraint_name="Certifications",
            is_met=False,
            details="Requires SDVOSB certification (VTKL not certified)"
        )
    
    if requires_wosb and not vtkl_certs.get("wosb", False):
        return ConstraintCheck(
            constraint_name="Certifications",
            is_met=False,
            details="Requires WOSB certification (VTKL not certified)"
        )
    
    # Check for small business set-aside (VTKL is small business)
    is_small_biz = "small business" in set_aside or "small business" in text_lower
    
    if is_small_biz:
        return ConstraintCheck(
            constraint_name="Certifications",
            is_met=True,
            details="Small business set-aside (VTKL qualifies)"
        )
    
    return ConstraintCheck(
        constraint_name="Certifications",
        is_met=True,
        details="No certification requirements"
    )


def _is_nho_set_aside(opportunity: GrantOpportunity) -> bool:
    """Check if opportunity is a Native Hawaiian Organization set-aside."""
    
    set_aside = (opportunity.set_aside_type or "").lower()
    text = (opportunity.description or "") + " " + (opportunity.raw_text or "")
    text_lower = text.lower()
    
    return "nho" in set_aside or \
           "native hawaiian" in set_aside or \
           any(term in text_lower for term in [
               "native hawaiian organization",
               "nho set-aside",
               "nho-owned"
           ])


def _determine_participation_path(
    is_eligible: bool,
    opportunity: GrantOpportunity,
    naics_match: bool,
    cert_check: bool
) -> Optional[str]:
    """Determine if VTKL can participate as prime or subawardee.
    
    Args:
        is_eligible: Overall eligibility result
        opportunity: Grant opportunity
        naics_match: Whether NAICS codes match
        cert_check: Whether certification check passed
        
    Returns:
        "prime", "subawardee", or None
    """
    
    if not is_eligible:
        return None
    
    # If all checks pass including NAICS, likely prime candidate
    if naics_match and cert_check:
        return "prime"
    
    # If eligible but NAICS is weak match, might be subawardee
    if not naics_match:
        return "subawardee"
    
    # Default: eligible but path unclear
    return None
