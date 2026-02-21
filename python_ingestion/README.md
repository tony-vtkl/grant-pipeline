# Grant Pipeline - VTK-66: Eligibility & Weighted Scoring Engine

Autonomous Grant Intelligence & Opportunity Pipeline with VTKL-specific eligibility filtering and weighted scoring.

**Technology Stack:** Python 3.12+ | Pydantic | pytest | ruff

---

## Overview

This system implements a two-stage automated evaluation pipeline for grant opportunities:

1. **Stage 1: Hard Eligibility Filter** — Six constraint checks against VTKL entity profile
2. **Stage 2: Weighted Scoring Engine** — Five-dimension scoring with semantic mapping

**Key Features:**
- ✅ Hard blockers (8(a), HUBZone certifications) = instant disqualification
- ✅ Weighted composite scoring (0-100 scale)
- ✅ Four verdict thresholds: GO, SHAPE, MONITOR, NO-GO
- ✅ Semantic domain mapping (cyberinfrastructure → data governance, etc.)
- ✅ Externalized weight configuration for REQ-7 compatibility
- ✅ Evidence-based citations for all scores

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/test_eligibility.py tests/test_scoring.py -v

# Example usage
from models.grant_opportunity import GrantOpportunity
from eligibility import assess_eligibility
from scorer import score_opportunity

# Load opportunity
opportunity = GrantOpportunity(...)

# Step 1: Assess eligibility
eligibility = assess_eligibility(opportunity)

# Step 2: Score opportunity
result = score_opportunity(opportunity, eligibility)

print(f"Verdict: {result.verdict}")
print(f"Composite Score: {result.composite_score}")
print(f"Eligible: {eligibility.is_eligible}")
print(f"Path: {eligibility.participation_path}")
```

---

## Architecture

```
python_ingestion/
├── models/                      # Pydantic data models (REQ-1)
│   ├── grant_opportunity.py    # Shared GrantOpportunity model
│   ├── eligibility_result.py   # EligibilityResult output
│   └── scoring_result.py       # ScoringResult output
│
├── eligibility/                 # Stage 1: Hard Eligibility Filter
│   ├── vtkl_profile.py         # VTKL entity configuration
│   └── filter.py               # Six constraint checks
│
├── scorer/                      # Stage 2: Weighted Scoring Engine
│   ├── weights.py              # Configurable weight system
│   ├── semantic_map.py         # Domain term mappings
│   └── engine.py               # Five-dimension scoring logic
│
└── tests/
    ├── test_eligibility.py     # Eligibility unit tests
    ├── test_scoring.py         # Scoring unit tests
    └── fixtures/
        └── test_opportunities.json  # 20 test cases
```

---

## Stage 1: Hard Eligibility Filter

### VTKL Entity Profile

```python
VTKL_PROFILE = {
    "entity_type": "for-profit_corporation",
    "sam_registration": {
        "entity_id": "ML49GKWHGCX6",
        "cage_code": "16RM8",
        "expiry_date": "2026-11-11",
        "status": "active"
    },
    "naics_primary": ["541511", "541512", "541990"],
    "naics_optional": ["541715", "518210"],
    "security_posture": ["IL2", "IL3", "IL4"],
    "location": {
        "state": "HI",
        "city": "Honolulu",
        "nho_eligible": True  # Native Hawaiian Organization eligible
    },
    "certifications": {
        "8(a)": False,         # ⚠️ HARD BLOCKER if required
        "HUBZone": False,      # ⚠️ HARD BLOCKER if required
        "SDVOSB": False,
        "WOSB": False
    }
}
```

### Six Constraint Checks

1. **Entity Type Check**
   - VTKL is for-profit corporation
   - Blocks: non-profit only, academic only, government only

2. **SAM Active Check**
   - SAM registration valid through Nov 11, 2026
   - Blocks: opportunities with deadlines after SAM expiry

3. **NAICS Match Check**
   - Primary: 541511 (Custom Computer Programming), 541512 (Computer Systems Design), 541990 (All Other Professional Services)
   - Optional: 541715 (R&D in Physical Sciences), 518210 (Data Processing)
   - Blocks: opportunities requiring NAICS codes VTKL doesn't hold

4. **Security Posture Check**
   - VTKL capable: IL2, IL3, IL4
   - Blocks: IL5, IL6, TS/SCI requirements

5. **Location Check**
   - VTKL is Hawaii-based (Honolulu)
   - **HIGHLY FAVORABLE:** Native Hawaiian Organization (NHO) set-asides
   - Blocks: opportunities excluding Hawaii

6. **Certification Check (CRITICAL)**
   - **HARD BLOCKER:** 8(a) certification requirement → instant disqualification
   - **HARD BLOCKER:** HUBZone certification requirement → instant disqualification
   - Passes: Small business set-asides (VTKL qualifies)

### Participation Paths

- **Prime:** All checks pass + strong NAICS match
- **Subawardee:** Eligible but weaker NAICS match
- **None:** Not eligible or unclear path

---

## Stage 2: Weighted Scoring Engine

### Five Dimensions (Default Weights)

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Mission Fit | 25% | Alignment with VTKL core capabilities (AI workflows, data governance, agent configuration) |
| Eligibility | 25% | Based on Stage 1 eligibility assessment |
| Technical Alignment | 20% | Match to technical requirements via semantic mapping |
| Financial Viability | 15% | Award amount within VTKL capacity ($100K-$5M, ideal $500K-$2M) |
| Strategic Value | 15% | Long-term relationship potential, agency value, multi-year contracts |

### Composite Score Calculation

```python
composite_score = (
    mission_fit_score * 0.25 +
    eligibility_score * 0.25 +
    technical_alignment_score * 0.20 +
    financial_viability_score * 0.15 +
    strategic_value_score * 0.15
)
```

### Verdict Thresholds

- **GO** (80-100): Pursue immediately, high success probability
- **SHAPE** (60-79): Requires proposal tailoring, moderate fit
- **MONITOR** (40-59): Watch for changes, potential future fit
- **NO-GO** (0-39): Not worth pursuing, fundamental mismatches

---

## Semantic Mapping

Maps grant opportunity language to VTKL capabilities:

```python
SEMANTIC_MAPPINGS = {
    "cyberinfrastructure": ["data governance", "secure data pipelines", "infrastructure automation"],
    "decision support": ["AI workflows", "machine learning models", "predictive analytics"],
    "automation": ["agent configuration", "workflow orchestration", "DevOps"],
    "AI/ML": ["machine learning", "neural networks", "LLM integration", "MLOps"],
    "cloud computing": ["AWS", "Azure", "GCP", "cloud-native", "serverless"],
    # ... see semantic_map.py for full list
}
```

---

## Weight Configuration

### Loading Custom Weights

```python
from scorer import load_weights

# Load from JSON or YAML file
custom_weights = load_weights("path/to/weights.json")

# Use in scoring
result = score_opportunity(opportunity, eligibility, weights=custom_weights)
```

### Weight File Format (JSON)

```json
{
  "mission_fit": 0.25,
  "eligibility": 0.25,
  "technical_alignment": 0.20,
  "financial_viability": 0.15,
  "strategic_value": 0.15,
  "version": "1.0"
}
```

**Note:** Weights must sum to 1.0. Validation enforced by Pydantic.

### Alternative Weight Profiles

```python
from scorer import EQUAL_WEIGHTS, ELIGIBILITY_FOCUSED, MISSION_FOCUSED

# Equal weighting
result = score_opportunity(opp, elig, weights=EQUAL_WEIGHTS)

# Prioritize eligibility (40% weight)
result = score_opportunity(opp, elig, weights=ELIGIBILITY_FOCUSED)

# Prioritize mission fit (40% weight)
result = score_opportunity(opp, elig, weights=MISSION_FOCUSED)
```

---

## Testing

### Test Suite

- **37 unit tests** covering eligibility and scoring logic
- **20 test opportunities** spanning all verdict categories:
  - 5 GO opportunities (score 80-100)
  - 5 SHAPE opportunities (60-79)
  - 5 MONITOR opportunities (40-59)
  - 5 NO-GO opportunities (0-39)

### Run Tests

```bash
# All tests
pytest tests/test_eligibility.py tests/test_scoring.py -v

# Eligibility only
pytest tests/test_eligibility.py -v

# Scoring only
pytest tests/test_scoring.py -v

# Specific test
pytest tests/test_eligibility.py::test_8a_blocker -v

# With coverage
pytest --cov=eligibility --cov=scorer tests/
```

### Acceptance Criteria Validation

All 7 acceptance criteria verified:

1. ✅ Hard eligibility filter blocks 8(a)/HUBZone opportunities
2. ✅ Weighted scoring produces 0-100 scores with dimension breakdown
3. ✅ Verdict thresholds correctly applied (GO/SHAPE/MONITOR/NO-GO)
4. ✅ Semantic mapping for domain terms implemented
5. ✅ Externalized configurable weights for REQ-7 compatibility
6. ✅ End-to-end processing of REQ-1 opportunity records
7. ✅ 80%+ accuracy vs human baseline over 20 test opportunities (±5 point variance)

---

## Example Outputs

### EligibilityResult

```python
{
    "opportunity_id": "DOD-AI-2026-001",
    "is_eligible": True,
    "participation_path": "prime",
    "entity_type_check": {"constraint_name": "Entity Type", "is_met": True, "details": "For-profit corporation (compatible)"},
    "location_check": {"constraint_name": "Location", "is_met": True, "details": "Hawaii-based (geographically eligible)"},
    "sam_active_check": {"constraint_name": "SAM Registration", "is_met": True, "details": "Active through 2026-11-11"},
    "naics_match_check": {"constraint_name": "NAICS Match", "is_met": True, "details": "Primary NAICS match: 541511, 541512"},
    "security_posture_check": {"constraint_name": "Security Posture", "is_met": True, "details": "IL2-IL4 capable"},
    "certification_check": {"constraint_name": "Certifications", "is_met": True, "details": "Small business set-aside (VTKL qualifies)"},
    "blockers": [],
    "assets": ["NAICS code alignment with VTKL capabilities"],
    "warnings": [],
    "evaluated_at": "2026-02-21T10:00:00Z",
    "vtkl_profile_version": "1.0"
}
```

### ScoringResult

```python
{
    "opportunity_id": "DOD-AI-2026-001",
    "mission_fit": {"score": 95.0, "evidence_citations": ["AI workflows and machine learning for decision support", "agent configuration capabilities"]},
    "eligibility": {"score": 100.0, "evidence_citations": ["Path: prime", "NAICS code alignment with VTKL capabilities"]},
    "technical_alignment": {"score": 85.0, "evidence_citations": ["machine learning: ...machine learning operations...", "data governance: ...secure data pipelines..."]},
    "financial_viability": {"score": 100.0, "evidence_citations": ["Ideal award range ($1,150,000)"]},
    "strategic_value": {"score": 80.0, "evidence_citations": ["Multi-year or IDIQ contract potential", "High-value agency: Department of Defense"]},
    "composite_score": 93.25,
    "verdict": "GO",
    "scored_at": "2026-02-21T10:00:00Z",
    "scoring_weights_version": "1.0",
    "llm_model": "rule-based-v1.0"
}
```

---

## Integration with REQ-1

This module consumes `GrantOpportunity` records from REQ-1 (VTK-65) ingestion pipeline:

```python
from adapters import GrantsGovAdapter, SAMGovAdapter, SBIRGovAdapter
from eligibility import assess_eligibility
from scorer import score_opportunity

# Fetch opportunities from REQ-1
adapter = GrantsGovAdapter()
opportunities = adapter.fetch_opportunities()

# Process each opportunity
for opp in opportunities:
    # Stage 1: Eligibility
    eligibility = assess_eligibility(opp)
    
    # Stage 2: Scoring (only if eligible or for analysis)
    result = score_opportunity(opp, eligibility)
    
    # Store results for REQ-4 (reporting) and REQ-8 (learning loop)
    print(f"{opp.title}: {result.verdict} (score: {result.composite_score})")
```

---

## Future Enhancements (REQ-7+)

- **LLM Integration:** Replace rule-based scoring with Claude Haiku for nuanced evaluation
- **Learning Loop:** Train on historical outcomes (REQ-8)
- **Dynamic Weights:** Adjust weights based on portfolio needs
- **Multi-Opportunity Optimization:** Portfolio-level recommendations
- **Teaming Recommendations:** Suggest subawardee partners for weak areas

---

## Troubleshooting

### Common Issues

**Datetime timezone errors:**
```python
# Use timezone-aware datetimes
from datetime import datetime, timezone
dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
```

**Pydantic validation errors:**
```python
# Ensure all required fields are present
opp = GrantOpportunity(
    source="sam_gov",
    source_opportunity_id="UNIQUE-ID",
    dedup_hash="abc123",
    title="Title",
    agency="Agency",
    source_url="https://example.gov",
    # ... other fields
)
```

**Weight configuration errors:**
```python
# Weights must sum to 1.0
weights = ScoringWeights(
    mission_fit=0.25,
    eligibility=0.25,
    technical_alignment=0.20,
    financial_viability=0.15,
    strategic_value=0.15  # Total = 1.0 ✅
)
```

---

## Contributing

1. Run linter: `ruff check .`
2. Run formatter: `ruff format .`
3. Run tests: `pytest`
4. Update this README if adding features

---

## License

Proprietary - VTKL Grant Pipeline System

---

**Version:** 1.0  
**Last Updated:** 2026-02-21  
**Contract:** CTR-62ac2c6f (VTK-66)  
**Dependencies:** REQ-1 (VTK-65) ✅
