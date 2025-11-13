# In nexustrader/backend/app/utils/shared_context.py

"""
Shared context manager to store fetched data and avoid redundant API calls.
This allows multiple agents to access the same data without re-fetching.
"""

from typing import Dict, Any, Optional


class SharedDataContext:
    """
    Stores commonly used data that multiple agents need.
    Prevents duplicate API calls within the same analysis run.
    """
    
    def __init__(self):
        self._data = {}
    
    def set(self, key: str, value: Any):
        """Store data in shared context."""
        self._data[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve data from shared context."""
        return self._data.get(key, default)
    
    def has(self, key: str) -> bool:
        """Check if data exists in context."""
        return key in self._data
    
    def clear(self):
        """Clear all shared data."""
        self._data.clear()
    
    # Convenience methods for common data
    
    def set_social_data(self, ticker: str, twitter: str, reddit: str, stocktwits: str):
        """Store social media data for reuse."""
        self.set(f"social_{ticker}_twitter", twitter)
        self.set(f"social_{ticker}_reddit", reddit)
        self.set(f"social_{ticker}_stocktwits", stocktwits)
    
    def get_social_data(self, ticker: str) -> Optional[Dict[str, str]]:
        """Retrieve cached social media data."""
        if self.has(f"social_{ticker}_twitter"):
            return {
                "twitter": self.get(f"social_{ticker}_twitter"),
                "reddit": self.get(f"social_{ticker}_reddit"),
                "stocktwits": self.get(f"social_{ticker}_stocktwits"),
            }
        return None
    
    def set_news_data(self, ticker: str, news: str):
        """Store news data for reuse."""
        self.set(f"news_{ticker}", news)
    
    def get_news_data(self, ticker: str) -> Optional[str]:
        """Retrieve cached news data."""
        return self.get(f"news_{ticker}")
    
    def set_financial_data(self, ticker: str, statements: Dict, ratios: Dict, ratings: Dict):
        """Store financial data for reuse."""
        self.set(f"financial_{ticker}_statements", statements)
        self.set(f"financial_{ticker}_ratios", ratios)
        self.set(f"financial_{ticker}_ratings", ratings)
    
    def get_financial_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached financial data."""
        if self.has(f"financial_{ticker}_statements"):
            return {
                "statements": self.get(f"financial_{ticker}_statements"),
                "ratios": self.get(f"financial_{ticker}_ratios"),
                "ratings": self.get(f"financial_{ticker}_ratings"),
            }
        return None


# Global shared context instance
shared_context = SharedDataContext()


def initialize_context():
    """Initialize a new shared context for an analysis run."""
    global shared_context
    shared_context = SharedDataContext()
    return shared_context


def get_shared_context() -> SharedDataContext:
    """Get the current shared context."""
    return shared_context
