# In nexustrader/backend/app/utils/cache.py

"""
Simple caching mechanism to avoid redundant API calls and LLM requests.
This significantly reduces execution time and API costs.
"""

from functools import wraps
from typing import Any, Callable
import hashlib
import json
import time
from pathlib import Path

class SimpleCache:
    """
    In-memory cache with optional disk persistence.
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize cache with time-to-live.
        
        Args:
            ttl_seconds: How long cached data remains valid (default: 1 hour)
        """
        self.cache = {}
        self.ttl_seconds = ttl_seconds
    
    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate a unique cache key from function name and arguments."""
        key_data = {
            'func': func_name,
            'args': str(args),
            'kwargs': str(sorted(kwargs.items()))
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Any:
        """Retrieve cached value if not expired."""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                return value
            else:
                # Expired, remove from cache
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any):
        """Store value in cache with current timestamp."""
        self.cache[key] = (value, time.time())
    
    def clear(self):
        """Clear all cached data."""
        self.cache.clear()


# Global cache instances
data_cache = SimpleCache(ttl_seconds=3600)  # 1 hour for market data
llm_cache = SimpleCache(ttl_seconds=86400)  # 24 hours for LLM responses


def cache_data(ttl_seconds: int = 3600):
    """
    Decorator to cache function results for market data.
    
    Usage:
        @cache_data(ttl_seconds=3600)
        def get_stock_price(ticker):
            # expensive API call
            return price
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = data_cache._generate_key(func.__name__, args, kwargs)
            
            # Try to get from cache
            cached_result = data_cache.get(cache_key)
            if cached_result is not None:
                print(f"[CACHE HIT] {func.__name__} - Using cached data")
                return cached_result
            
            # Cache miss - call function
            print(f"[CACHE MISS] {func.__name__} - Fetching fresh data")
            result = func(*args, **kwargs)
            
            # Store in cache
            data_cache.set(cache_key, result)
            
            return result
        return wrapper
    return decorator


def cache_llm(ttl_seconds: int = 86400):
    """
    Decorator to cache LLM responses.
    Useful for identical prompts that don't change.
    
    Usage:
        @cache_llm(ttl_seconds=86400)
        def call_llm(prompt):
            # expensive LLM call
            return response
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = llm_cache._generate_key(func.__name__, args, kwargs)
            
            # Try to get from cache
            cached_result = llm_cache.get(cache_key)
            if cached_result is not None:
                print(f"[LLM CACHE HIT] Using cached response")
                return cached_result
            
            # Cache miss - call LLM
            result = func(*args, **kwargs)
            
            # Store in cache
            llm_cache.set(cache_key, result)
            
            return result
        return wrapper
    return decorator


def clear_all_caches():
    """Clear all caches."""
    data_cache.clear()
    llm_cache.clear()
    print("All caches cleared")
