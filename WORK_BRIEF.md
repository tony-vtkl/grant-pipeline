# VTK-66: VTKL Eligibility & Weighted Scoring Engine

## MISSION
Build a two-stage automated evaluation system for grant opportunities:
1. Hard eligibility filter (REQ-2)
2. Weighted scoring engine (REQ-3)

## TECH STACK
- Python 3.12+
- Pydantic models (already defined in models/)
- pytest for testing
- ruff for linting
- Existing models: GrantOpportunity, EligibilityResult, ScoringResult

## DIRECTORY STRUCTURE
```
python_ingestion/
├── models/               # ✅ Already exists (REQ-1)
│   ├── grant_opportunity.py
│   ├── eligibility_result.py
│   └── scoring_result.py
├── eligibility/          # 🔨 CREATE THIS
│   ├── __init__.py
│   ├── vtkl_profile.py   # VTKL entity configuration
│   └── filter.py         # Hard eligibility logic
├── scorer/               # 🔨 CREATE THIS
│   ├── __init__.py
│   ├── weights.py        # Configurable weight system
│   ├── semantic_map.py   # Domain term mappings
│   └── engine.py         # Five-dimension scoring logic
└── tests/                # 🔨 EXPAND THIS
    ├── test_eligibility.py
    ├── test_scoring.py
    └── fixtures/
        └── test_opportunities.json  # 20 test cases
```

## VTKL ENTITY PROFILE
```python
# eligibility/vtkl_profile.py
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
        "nho_eligible": True
    },
    "certifications": {
        "8a": False,
        "hubzone": False,
        "sdvosb": False,
        "wosb": False
    }
}
```

## STAGE 1: HARD ELIGIBILITY FILTER

**File:** `eligibility/filter.py`

**Function:** `def assess_eligibility(opportunity: GrantOpportunity) -> EligibilityResult`

### Six Constraint Checks (all must pass):

1. **Entity Type Check**
   - VTKL is for-profit corporation
   - Block if opportunity requires non-profit/academic/government entity

2. **SAM Active Check**
   - Check if opportunity requires active SAM registration
   - Verify VTKL SAM expiry (Nov 11 2026) is after opportunity deadline
   - Pass: VTKL has active SAM through 2026-11-11

3. **NAICS Match Check**
   - Opportunity must allow one of VTKL's primary NAICS: 541511, 541512, 541990
   - OR one of optional NAICS: 541715, 518210
   - Pass if any match found

4. **Security Posture Check**
   - If opportunity requires security clearance/posture
   - VTKL can meet IL2, IL3, or IL4
   - Pass if within capability

5. **Location Check**
   - VTKL is Hawaii-based (Honolulu)
   - Check for NHO (Native Hawaiian Organization) set-asides
   - Pass: geographically eligible

6. **Certification Check (CRITICAL BLOCKER)**
   - **If opportunity requires 8(a) OR HUBZone certification → HARD BLOCK**
   - This is an instant disqualifier
   - VTKL has neither certification
   - No workarounds

### Participation Path Logic:
```python
if all_checks_pass:
    if meets_prime_requirements:
        path = "prime"
    elif can_be_subawardee:
        path = "subawardee"
    else:
        path = None  # eligible but unclear path
else:
    path = None  # not eligible
```

### Output:
- Populate EligibilityResult model
- Set `is_eligible` based on all checks
- Set `participation_path` (prime/subawardee/None)
- Populate `blockers`, `assets`, `warnings` lists
- Fill all ConstraintCheck fields

## STAGE 2: WEIGHTED SCORING (0-100)

**File:** `scorer/engine.py`

**Function:** `def score_opportunity(opportunity: GrantOpportunity, eligibility: EligibilityResult) -> ScoringResult`

### Five Dimensions with Weights:

1. **Mission Fit (25%)**
   - Does opportunity align with VTKL's mission?
   - VTKL focus areas: AI workflows, data governance, agent configuration, decision support
   - Extract evidence quotes from `opportunity.raw_text`

2. **Eligibility (25%)**
   - Use `eligibility.is_eligible` as baseline
   - Hard blockers = 0 score
   - Warnings = reduced score
   - Perfect eligibility + assets (e.g., NHO) = 100

3. **Technical Alignment (20%)**
   - Match opportunity requirements to VTKL capabilities
   - Use semantic mapping (see below)
   - Extract evidence from description/raw_text

4. **Financial Viability (15%)**
   - Award amount within VTKL's capacity
   - Contract size, duration, overhead requirements
   - VTKL can handle $100K-$5M awards comfortably

5. **Strategic Value (15%)**
   - Long-term relationship potential
   - Repeat contract opportunities
   - Customer acquisition value
   - Portfolio diversification

### Semantic Mapping:
```python
# scorer/semantic_map.py
SEMANTIC_MAPPINGS = {
    "cyberinfrastructure": ["data governance", "secure data pipelines", "infrastructure automation"],
    "decision support": ["AI workflows", "machine learning models", "predictive analytics"],
    "automation": ["agent configuration", "workflow orchestration", "DevOps"],
    "data management": ["data governance", "ETL pipelines", "data quality"],
    "AI/ML": ["machine learning", "neural networks", "LLM integration", "model training"],
    "cloud": ["AWS", "Azure", "GCP", "cloud-native", "serverless"],
    # Add more as needed
}
```

### Weight Configuration System:
```python
# scorer/weights.py
class ScoringWeights(BaseModel):
    mission_fit: float = 0.25
    eligibility: float = 0.25
    technical_alignment: float = 0.20
    financial_viability: float = 0.15
    strategic_value: float = 0.15
    version: str = "1.0"

    @validator('*', pre=True)
    def weights_sum_to_one(cls, v, values):
        total = sum([
            values.get('mission_fit', 0),
            values.get('eligibility', 0),
            values.get('technical_alignment', 0),
            values.get('financial_viability', 0),
            values.get('strategic_value', 0)
        ])
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        return v

DEFAULT_WEIGHTS = ScoringWeights()

# Allow loading custom weights from YAML/JSON
def load_weights(filepath: Optional[str] = None) -> ScoringWeights:
    if filepath:
        # Load from file
        pass
    return DEFAULT_WEIGHTS
```

### Verdict Thresholds:
```python
def get_verdict(composite_score: float) -> str:
    if composite_score >= 80:
        return "GO"
    elif composite_score >= 60:
        return "SHAPE"
    elif composite_score >= 40:
        return "MONITOR"
    else:
        return "NO-GO"
```

### Composite Score Calculation:
```python
composite_score = (
    mission_fit.score * weights.mission_fit +
    eligibility_score * weights.eligibility +
    technical_alignment.score * weights.technical_alignment +
    financial_viability.score * weights.financial_viability +
    strategic_value.score * weights.strategic_value
)
```

### Evidence Citations:
- Each DimensionScore must include `evidence_citations`
- Extract 1-3 direct quotes from `opportunity.raw_text` or `opportunity.description`
- Quote exact phrases that justify the score

## 20-OPPORTUNITY TEST HARNESS

**File:** `tests/fixtures/test_opportunities.json`

Create 20 diverse test cases covering:
- 5 GO opportunities (score 80-100)
- 5 SHAPE opportunities (60-79)
- 5 MONITOR opportunities (40-59)
- 5 NO-GO opportunities (0-39)

Include varied scenarios:
- 8(a) blockers
- HUBZone blockers
- Perfect matches (NHO set-aside + NAICS match)
- NAICS mismatches
- Expired SAM registration
- Out-of-scope work
- Financial mismatches (too small/large)
- Security posture mismatches

**Test Files:**
- `tests/test_eligibility.py`: Test each constraint check individually
- `tests/test_scoring.py`: Test scoring logic, weight configuration, semantic mapping

## ACCEPTANCE CRITERIA (MUST VALIDATE)

1. ✅ Hard eligibility filter blocks 8(a)/HUBZone opportunities
2. ✅ Weighted scoring produces 0-100 scores with dimension breakdown
3. ✅ Verdict thresholds: GO (80-100), SHAPE (60-79), MONITOR (40-59), NO-GO (0-39)
4. ✅ Semantic mapping for domain terms
5. ✅ Externalized configurable weights for REQ-7 compatibility
6. ✅ End-to-end processing of REQ-1 opportunity records
7. ✅ 90%+ accuracy vs human baseline over 20 test opportunities (±5 point variance)

## IMPLEMENTATION STEPS

1. Create directory structure: `eligibility/`, `scorer/`
2. Implement VTKL profile configuration
3. Implement hard eligibility filter with all 6 checks
4. Implement semantic mapping configuration
5. Implement weight configuration system
6. Implement five-dimension scoring engine
7. Create 20-opportunity test harness
8. Write comprehensive unit tests
9. Validate all 7 acceptance criteria
10. Update README.md with usage documentation

## EXECUTION NOTES

- All code must pass `ruff` linting (config in pyproject.toml)
- Use existing Pydantic models (don't modify them)
- Document all functions with docstrings
- Include type hints everywhere
- Write defensive code (handle None values gracefully)
- Log key decision points for debugging

## TESTING COMMAND

```bash
cd python_ingestion
pytest tests/test_eligibility.py tests/test_scoring.py -v
```

## SUCCESS METRICS

- All tests pass
- 90%+ accuracy on 20-test baseline (±5 points)
- 8(a) and HUBZone opportunities correctly blocked
- Composite scores match expected verdicts
- Weight configuration loads successfully
- Semantic mapping applied correctly

---

**TIME BUDGET:** 60 effective minutes
**MODEL:** claude-sonnet-4-5-20250929
**DEADLINE:** Sprint deadline per Linear dispatch
