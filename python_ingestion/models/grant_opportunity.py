"""GrantOpportunity - Shared model for normalized grant data from all sources."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class GrantOpportunity(BaseModel):
    """Normalized grant opportunity record from any source.
    
    Shared contract for all downstream REQs (REQ-2 through REQ-9).
    """
    
    # Core identifiers
    source: str = Field(..., description="Source system: grants_gov, sam_gov, sbir_gov")
    source_opportunity_id: str = Field(..., description="Unique ID from source system")
    dedup_hash: str = Field(..., description="SHA256(source + source_opportunity_id)")
    
    # Opportunity details
    title: str = Field(..., description="Opportunity title")
    agency: str = Field(..., description="Issuing agency")
    opportunity_number: Optional[str] = Field(None, description="Official opportunity/solicitation number")
    
    # Dates
    posted_date: Optional[datetime] = Field(None, description="Publication date")
    response_deadline: Optional[datetime] = Field(None, description="Submission deadline")
    archive_date: Optional[datetime] = Field(None, description="Archive/close date")
    
    # Financial
    award_amount_min: Optional[float] = Field(None, description="Minimum award amount")
    award_amount_max: Optional[float] = Field(None, description="Maximum award amount")
    estimated_total_program_funding: Optional[float] = Field(None, description="Total program funding")
    
    # Classification
    naics_codes: list[str] = Field(default_factory=list, description="NAICS codes")
    set_aside_type: Optional[str] = Field(None, description="Set-aside type: 8(a), HUBZone, Small Business, etc.")
    opportunity_type: Optional[str] = Field(None, description="Type: Grant, Cooperative Agreement, Procurement, etc.")
    
    # Content
    description: Optional[str] = Field(None, description="Opportunity description/abstract")
    raw_text: Optional[str] = Field(None, description="Full text for LLM scoring")
    
    # Links
    source_url: str = Field(..., description="Link to source listing")
    
    # Metadata
    first_detected_at: datetime = Field(default_factory=datetime.utcnow, description="First ingestion timestamp")
    last_updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    status: str = Field(default="new", description="Processing status: new, evaluated, scored, etc.")
    
    # SBIR-specific flag (per INTAKE BLOCK 1 acceptance criteria)
    sbir_program_active: bool = Field(default=False, description="SBIR program reauthorization status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "source": "sam_gov",
                "source_opportunity_id": "HHS-OS-24-001",
                "dedup_hash": "a3f5e8d9...",
                "title": "AI/ML Development for Healthcare",
                "agency": "Health and Human Services",
                "opportunity_number": "HHS-OS-24-001",
                "posted_date": "2024-01-15T00:00:00Z",
                "response_deadline": "2024-03-18T23:59:59Z",
                "award_amount_min": 1000000.0,
                "award_amount_max": 2500000.0,
                "naics_codes": ["541511", "541512"],
                "set_aside_type": "Small Business",
                "opportunity_type": "Grant",
                "description": "Seeking AI solutions for healthcare data analysis",
                "source_url": "https://sam.gov/opp/HHS-OS-24-001",
                "status": "new",
                "sbir_program_active": False,
            }
        }
