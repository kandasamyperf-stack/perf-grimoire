"""Agent Loop Cost Guardian — monitor, budget, and kill runaway agent loops."""

from .guardian import CostGuardian, BudgetExceededError
from .tracker import LoopTracker
from .models import LoopStats, BudgetConfig

__all__ = ["CostGuardian", "BudgetExceededError", "LoopTracker", "LoopStats", "BudgetConfig"]
__version__ = "1.0.0"
