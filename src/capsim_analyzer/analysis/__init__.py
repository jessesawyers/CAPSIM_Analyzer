"""Pure analysis functions over structured Courier reports."""

from .market_share import analyze_market_share
from .finance import analyze_financials
from .segments import analyze_segments

__all__ = ["analyze_financials", "analyze_market_share", "analyze_segments"]
