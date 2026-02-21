"""Scoring weight configuration system.

Supports externalized, configurable weights for REQ-7 compatibility.
"""

import json
import yaml
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, field_validator


class ScoringWeights(BaseModel):
    """Configurable scoring weights for five dimensions.
    
    All weights must sum to 1.0 for proper composite scoring.
    """
    
    mission_fit: float = 0.25
    eligibility: float = 0.25
    technical_alignment: float = 0.20
    financial_viability: float = 0.15
    strategic_value: float = 0.15
    version: str = "1.0"
    
    @field_validator('mission_fit', 'eligibility', 'technical_alignment', 
                     'financial_viability', 'strategic_value')
    @classmethod
    def weight_range(cls, v: float) -> float:
        """Ensure weights are between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError(f"Weight must be between 0 and 1, got {v}")
        return v
    
    def model_post_init(self, __context) -> None:
        """Validate that weights sum to 1.0."""
        total = (
            self.mission_fit +
            self.eligibility +
            self.technical_alignment +
            self.financial_viability +
            self.strategic_value
        )
        
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Weights must sum to 1.0, got {total:.3f}. "
                f"(MF:{self.mission_fit}, E:{self.eligibility}, "
                f"TA:{self.technical_alignment}, FV:{self.financial_viability}, "
                f"SV:{self.strategic_value})"
            )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "mission_fit": self.mission_fit,
            "eligibility": self.eligibility,
            "technical_alignment": self.technical_alignment,
            "financial_viability": self.financial_viability,
            "strategic_value": self.strategic_value,
            "version": self.version
        }


# Default weights as specified in contract
DEFAULT_WEIGHTS = ScoringWeights(
    mission_fit=0.25,
    eligibility=0.25,
    technical_alignment=0.20,
    financial_viability=0.15,
    strategic_value=0.15,
    version="1.0"
)


def load_weights(filepath: Optional[str] = None) -> ScoringWeights:
    """Load scoring weights from file or return defaults.
    
    Supports JSON and YAML formats.
    
    Args:
        filepath: Optional path to weights configuration file
        
    Returns:
        ScoringWeights instance
        
    Raises:
        FileNotFoundError: If filepath provided but doesn't exist
        ValueError: If weights are invalid
    """
    
    if not filepath:
        return DEFAULT_WEIGHTS
    
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Weights file not found: {filepath}")
    
    # Load based on extension
    if path.suffix == '.json':
        with open(path, 'r') as f:
            data = json.load(f)
    elif path.suffix in ['.yaml', '.yml']:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}. Use .json, .yaml, or .yml")
    
    return ScoringWeights(**data)


def save_weights(weights: ScoringWeights, filepath: str) -> None:
    """Save scoring weights to file.
    
    Args:
        weights: ScoringWeights instance to save
        filepath: Path to save to (extension determines format)
    """
    
    path = Path(filepath)
    data = weights.to_dict()
    
    if path.suffix == '.json':
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    elif path.suffix in ['.yaml', '.yml']:
        with open(path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")


# Alternative weight configurations for experimentation

EQUAL_WEIGHTS = ScoringWeights(
    mission_fit=0.20,
    eligibility=0.20,
    technical_alignment=0.20,
    financial_viability=0.20,
    strategic_value=0.20,
    version="equal_1.0"
)

ELIGIBILITY_FOCUSED = ScoringWeights(
    mission_fit=0.20,
    eligibility=0.40,  # Prioritize eligibility
    technical_alignment=0.15,
    financial_viability=0.15,
    strategic_value=0.10,
    version="eligibility_focused_1.0"
)

MISSION_FOCUSED = ScoringWeights(
    mission_fit=0.40,  # Prioritize mission alignment
    eligibility=0.20,
    technical_alignment=0.20,
    financial_viability=0.10,
    strategic_value=0.10,
    version="mission_focused_1.0"
)
