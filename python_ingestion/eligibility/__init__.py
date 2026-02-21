"""Eligibility assessment module for VTKL grant opportunities."""

from .filter import assess_eligibility
from .vtkl_profile import VTKL_PROFILE

__all__ = ["assess_eligibility", "VTKL_PROFILE"]
