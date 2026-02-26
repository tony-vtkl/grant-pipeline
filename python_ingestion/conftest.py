"""Root conftest — ensures imports work for both test patterns."""
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
_parent = _here.parent

# Add repo root so `python_ingestion.X` works
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

# Add python_ingestion/ so `from models.X` (absolute) works
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))
