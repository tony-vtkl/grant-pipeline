"""VerdictReportGenerator - Generates verdict reports and executive summaries."""

import logging
from typing import Optional

from database.client import SupabaseClient
from models.verdict_report import VerdictReport, RoadmapPhase
from models.scoring_result import ScoringResult
from models.eligibility_result import EligibilityResult
from models.teaming_partner import TeamingPartner

logger = logging.getLogger(__name__)


class VerdictReportGenerator:
    """Generates verdict reports combining scoring, eligibility, and teaming data."""

    def __init__(self, supabase_client: SupabaseClient):
        """Initialize generator with Supabase client.
        
        Args:
            supabase_client: Database client for querying pipeline results.
        """
        self.client = supabase_client

    def generate(self, opportunity_id: str) -> VerdictReport:
        """Generate verdict report for an opportunity.
        
        Queries scoring_results, eligibility_results, and teaming_partners
        to build a comprehensive VerdictReport.
        
        GO/SHAPE verdicts get full reports with all 5 sections.
        MONITOR/NO-GO get abbreviated reports (verdict card + risk assessment only).
        
        Args:
            opportunity_id: Opportunity source ID.
            
        Returns:
            Generated VerdictReport with status "awaiting_human_approval".
            
        Raises:
            Exception: If required data is missing from database.
        """
        logger.info(f"Generating verdict report for opportunity: {opportunity_id}")
        
        # Query scoring results
        scoring_response = (
            self.client._client
            .table("scoring_results")
            .select("*")
            .eq("opportunity_id", opportunity_id)
            .single()
            .execute()
        )
        if not scoring_response.data:
            raise ValueError(f"No scoring results found for {opportunity_id}")
        
        scoring = ScoringResult(**scoring_response.data)
        
        # Query eligibility results
        eligibility_response = (
            self.client._client
            .table("eligibility_results")
            .select("*")
            .eq("opportunity_id", opportunity_id)
            .single()
            .execute()
        )
        if not eligibility_response.data:
            raise ValueError(f"No eligibility results found for {opportunity_id}")
        
        eligibility = EligibilityResult(**eligibility_response.data)
        
        # Query teaming partners (may be empty list)
        teaming_response = (
            self.client._client
            .table("teaming_partners")
            .select("*")
            .eq("opportunity_id", opportunity_id)
            .execute()
        )
        teaming_partners = [TeamingPartner(**row) for row in teaming_response.data]
        
        # Query grant opportunity for raw_text
        grant_response = (
            self.client._client
            .table("grant_opportunities")
            .select("raw_text")
            .eq("source_opportunity_id", opportunity_id)
            .single()
            .execute()
        )
        raw_text = grant_response.data.get("raw_text", "") if grant_response.data else ""
        
        # Build report components
        verdict = scoring.verdict
        composite_score = scoring.composite_score
        
        # Component 1: Verdict rationale
        verdict_rationale = self._build_verdict_rationale(scoring, eligibility)
        
        # Component 2: Executive summary (3 sentences)
        executive_summary = self._build_executive_summary(
            scoring, eligibility, raw_text, verdict
        )
        
        # Component 3: Risk assessment
        risk_assessment = self._build_risk_assessment(eligibility)
        
        # Components 4 & 5: Strategic roadmap and one-pager (GO/SHAPE only)
        strategic_roadmap = None
        one_pager_pitch = None
        
        if verdict in ["GO", "SHAPE"]:
            strategic_roadmap = self._build_strategic_roadmap(verdict, eligibility, teaming_partners)
            one_pager_pitch = self._build_one_pager_pitch(scoring, eligibility, raw_text)
        
        # Create report
        report = VerdictReport(
            opportunity_id=opportunity_id,
            verdict=verdict,
            composite_score=composite_score,
            verdict_rationale=verdict_rationale,
            executive_summary=executive_summary,
            risk_assessment=risk_assessment,
            strategic_roadmap=strategic_roadmap,
            one_pager_pitch=one_pager_pitch,
            status="awaiting_human_approval"
        )
        
        # Save to database
        self.client._client.table("verdict_reports").insert(
            report.model_dump(mode="json")
        ).execute()
        
        logger.info(f"Verdict report generated and saved: {verdict} ({composite_score:.1f})")
        return report

    def _build_verdict_rationale(
        self, scoring: ScoringResult, eligibility: EligibilityResult
    ) -> str:
        """Build verdict rationale with evidence quotes."""
        rationale_parts = []
        
        # Include top scoring dimensions
        dimensions = [
            ("Mission Fit", scoring.mission_fit),
            ("Technical Alignment", scoring.technical_alignment),
            ("Financial Viability", scoring.financial_viability),
            ("Strategic Value", scoring.strategic_value),
        ]
        
        for name, dimension in dimensions:
            if dimension.score >= 70:
                evidence = dimension.evidence_citations[0] if dimension.evidence_citations else "N/A"
                rationale_parts.append(
                    f"{name}: {dimension.score:.0f}/100 - {evidence}"
                )
        
        # Include eligibility issues
        if eligibility.blockers:
            rationale_parts.append(f"Eligibility blockers: {'; '.join(eligibility.blockers)}")
        
        return ". ".join(rationale_parts) if rationale_parts else "No significant findings."

    def _build_executive_summary(
        self,
        scoring: ScoringResult,
        eligibility: EligibilityResult,
        raw_text: str,
        verdict: str
    ) -> str:
        """Build 3-sentence executive summary citing evidence.
        
        Full summary for GO/SHAPE, abbreviated for MONITOR/NO-GO.
        """
        sentences = []
        
        # Sentence 1: Opportunity description with mission fit evidence
        mission_evidence = (
            scoring.mission_fit.evidence_citations[0]
            if scoring.mission_fit.evidence_citations
            else "federal opportunity"
        )
        sentences.append(
            f"This opportunity focuses on {mission_evidence.lower()}."
        )
        
        # Sentence 2: VTKL's capabilities
        tech_evidence = (
            scoring.technical_alignment.evidence_citations[0]
            if scoring.technical_alignment.evidence_citations
            else "relevant technical capabilities"
        )
        sentences.append(
            f"VTKL has strong alignment with {tech_evidence.lower()}."
        )
        
        # Sentence 3: Verdict-specific conclusion
        if verdict in ["GO", "SHAPE"]:
            if eligibility.is_eligible:
                sentences.append(
                    f"Opportunity is eligible for pursuit with composite score of {scoring.composite_score:.0f}/100."
                )
            else:
                sentences.append(
                    f"Opportunity requires shaping due to: {eligibility.blockers[0] if eligibility.blockers else 'constraints'}."
                )
        else:  # MONITOR or NO-GO
            if eligibility.blockers:
                sentences.append(
                    f"Opportunity is not pursuable: {eligibility.blockers[0]}."
                )
            else:
                sentences.append(
                    f"Opportunity scores {scoring.composite_score:.0f}/100 and does not meet pursuit threshold."
                )
        
        return " ".join(sentences)

    def _build_risk_assessment(self, eligibility: EligibilityResult) -> str:
        """Build risk assessment from eligibility blockers and warnings."""
        sections = []
        
        if eligibility.blockers:
            sections.append(f"**Blockers:** {'; '.join(eligibility.blockers)}")
        
        if eligibility.warnings:
            sections.append(f"**Warnings:** {'; '.join(eligibility.warnings)}")
        else:
            sections.append("**Warnings:** None identified")
        
        # Timeline risk placeholder (would come from timeline analysis in full implementation)
        sections.append("**Timeline risk:** Standard federal procurement timeline applies")
        
        return ". ".join(sections) + "."

    def _build_strategic_roadmap(
        self,
        verdict: str,
        eligibility: EligibilityResult,
        teaming_partners: list[TeamingPartner]
    ) -> list[RoadmapPhase]:
        """Build phase-gated roadmap for GO/SHAPE opportunities."""
        phases = []
        
        # Phase 1: Initial assessment (always included)
        phases.append(RoadmapPhase(
            phase_number=1,
            description="Complete eligibility verification and teaming partner outreach",
            owner="human",
            estimated_duration="1-2 weeks"
        ))
        
        # Phase 2: Proposal development
        if verdict == "GO":
            phases.append(RoadmapPhase(
                phase_number=2,
                description="Develop proposal narrative and technical approach",
                owner="human",
                estimated_duration="2-4 weeks"
            ))
        else:  # SHAPE
            phases.append(RoadmapPhase(
                phase_number=2,
                description="Address eligibility gaps and refine approach",
                owner="human",
                estimated_duration="3-6 weeks"
            ))
        
        # Phase 3: Submission
        phases.append(RoadmapPhase(
            phase_number=3,
            description="Final review, pricing, and submission via SAM.gov/Grants.gov",
            owner="automated",
            estimated_duration="3-5 days"
        ))
        
        return phases

    def _build_one_pager_pitch(
        self,
        scoring: ScoringResult,
        eligibility: EligibilityResult,
        raw_text: str
    ) -> str:
        """Build one-pager pitch with VTKL brand messaging.
        
        Must include 'execution engine' and 'purpose-built solutions'.
        """
        pitch_sections = []
        
        # Opening: Opportunity overview
        mission_ev = scoring.mission_fit.evidence_citations[0] if scoring.mission_fit.evidence_citations else "mission"
        pitch_sections.append(
            f"**Opportunity:** {mission_ev.capitalize()}."
        )
        
        # VTKL value prop with brand messaging
        pitch_sections.append(
            f"**VTKL Solution:** VTKL brings purpose-built solutions combining proven execution engine "
            f"capabilities with deep technical expertise in federal AI/ML and data infrastructure."
        )
        
        # Technical fit
        tech_ev = scoring.technical_alignment.evidence_citations[0] if scoring.technical_alignment.evidence_citations else "technical requirements"
        pitch_sections.append(
            f"**Technical Alignment:** Our team has direct experience with {tech_ev.lower()}, "
            f"scoring {scoring.technical_alignment.score:.0f}/100 on technical fit."
        )
        
        # Differentiators
        differentiators = []
        if eligibility.assets:
            differentiators.extend(eligibility.assets)
        differentiators.append("Hawaii-based small business with active SAM registration")
        
        pitch_sections.append(
            f"**Differentiators:** {'; '.join(differentiators)}."
        )
        
        # Call to action
        pitch_sections.append(
            f"**Next Steps:** Immediate pursuit recommended with composite score of {scoring.composite_score:.0f}/100."
        )
        
        return " ".join(pitch_sections)
