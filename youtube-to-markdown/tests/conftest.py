"""Shared test fixtures."""

import sys
from pathlib import Path

# Add parent so `lib.*` imports work
sys.path.insert(0, str(Path(__file__).parent.parent))
