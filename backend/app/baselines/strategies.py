"""
Non-agentic baseline strategies for NexusTrader evaluation.

Each baseline generates a trading decision (BUY/SELL/HOLD) for a given
(ticker, simulated_date) using simple rules without LLM agents.
"""

from typing import Dict, Any, Optional, Literal
from datetime import datetime
from ..tools.technical_analysis_tools import get_historical_price_data, calculate_technical_indicators


class BaselineStrategy:
    """Base class for baseline strategies."""
    
    def __init__(self, name: str):
        self.name = name
    
    def generate_signal(
        self, 
        ticker: str, 
        simulated_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a trading signal.
        
        Returns a dict matching the NexusTrader output schema:
        {
            "baseline_name": str,
            "ticker": str,
            "simulated_date": str,
            "trading_strategy": {
                "action": "BUY"|"SELL"|"HOLD",
                "entry_price": float or None,
                "take_profit": float or None,
                "stop_loss": float or None,
                "position_size_pct": float,
                "rationale": str
            }
        }
        """
        raise NotImplementedError("Subclasses must implement generate_signal")


class BuyAndHoldBaseline(BaselineStrategy):
    """
    Baseline B1: Buy & Hold
    Always recommends BUY (passive long-only strategy).
    """
    
    def __init__(self):
        super().__init__(name="BuyAndHold")
    
    def generate_signal(
        self, 
        ticker: str, 
        simulated_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Always BUY."""
        
        # Fetch current price for entry
        try:
            price_data = get_historical_price_data(ticker, period="5d", as_of=simulated_date)
            if not price_data.empty:
                current_price = float(price_data['Close'].iloc[-1])
                entry_price = current_price
                # Simple targets: +5% TP, -2% SL
                take_profit = round(current_price * 1.05, 2)
                stop_loss = round(current_price * 0.98, 2)
            else:
                entry_price = None
                take_profit = None
                stop_loss = None
        except Exception:
            entry_price = None
            take_profit = None
            stop_loss = None
        
        return {
            "baseline_name": self.name,
            "ticker": ticker,
            "simulated_date": simulated_date or datetime.now().date().isoformat(),
            "trading_strategy": {
                "action": "BUY",
                "entry_price": entry_price,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "position_size_pct": 100,  # Full allocation for buy-and-hold
                "rationale": "Buy and hold baseline: always long."
            }
        }


class SMAcrossoverBaseline(BaselineStrategy):
    """
    Baseline B2: SMA Crossover
    BUY if SMA_fast > SMA_slow, SELL if SMA_fast < SMA_slow.
    Default: SMA_20 vs SMA_50.
    """
    
    def __init__(self, fast_period: int = 20, slow_period: int = 50):
        super().__init__(name=f"SMA_{fast_period}_{slow_period}")
        self.fast_period = fast_period
        self.slow_period = slow_period
    
    def generate_signal(
        self, 
        ticker: str, 
        simulated_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate signal based on SMA crossover."""
        
        try:
            # Fetch enough history for slow SMA calculation
            price_data = get_historical_price_data(ticker, period="6mo", as_of=simulated_date)
            
            if price_data.empty or len(price_data) < self.slow_period:
                # Not enough data
                return self._hold_signal(ticker, simulated_date, "Insufficient data for SMA calculation")
            
            indicators = calculate_technical_indicators(price_data)
            sma_fast = indicators.get(f'SMA_{self.fast_period}')
            sma_slow = indicators.get(f'SMA_{self.slow_period}')
            current_price = float(price_data['Close'].iloc[-1])
            
            if sma_fast is None or sma_slow is None:
                return self._hold_signal(ticker, simulated_date, "SMA indicators not available")
            
            # Decision logic
            if sma_fast > sma_slow:
                action = "BUY"
                rationale = f"SMA_{self.fast_period} ({sma_fast:.2f}) > SMA_{self.slow_period} ({sma_slow:.2f}): bullish crossover"
                entry_price = current_price
                take_profit = round(current_price * 1.05, 2)
                stop_loss = round(current_price * 0.98, 2)
                position_size = 20
            elif sma_fast < sma_slow:
                action = "SELL"
                rationale = f"SMA_{self.fast_period} ({sma_fast:.2f}) < SMA_{self.slow_period} ({sma_slow:.2f}): bearish crossover"
                entry_price = current_price
                take_profit = round(current_price * 0.95, 2)  # Profit on decline
                stop_loss = round(current_price * 1.02, 2)
                position_size = 20
            else:
                return self._hold_signal(ticker, simulated_date, f"SMA_{self.fast_period} ≈ SMA_{self.slow_period}: neutral")
            
            return {
                "baseline_name": self.name,
                "ticker": ticker,
                "simulated_date": simulated_date or datetime.now().date().isoformat(),
                "trading_strategy": {
                    "action": action,
                    "entry_price": entry_price,
                    "take_profit": take_profit,
                    "stop_loss": stop_loss,
                    "position_size_pct": position_size,
                    "rationale": rationale
                }
            }
        
        except Exception as e:
            return self._hold_signal(ticker, simulated_date, f"Error: {str(e)}")
    
    def _hold_signal(self, ticker: str, simulated_date: Optional[str], reason: str) -> Dict[str, Any]:
        """Helper to generate HOLD signal."""
        return {
            "baseline_name": self.name,
            "ticker": ticker,
            "simulated_date": simulated_date or datetime.now().date().isoformat(),
            "trading_strategy": {
                "action": "HOLD",
                "entry_price": None,
                "take_profit": None,
                "stop_loss": None,
                "position_size_pct": 0,
                "rationale": reason
            }
        }


class RSIthresholdBaseline(BaselineStrategy):
    """
    Baseline B3: RSI Threshold
    BUY if RSI < oversold_threshold (default 30)
    SELL if RSI > overbought_threshold (default 70)
    HOLD otherwise.
    """
    
    def __init__(self, oversold: int = 30, overbought: int = 70):
        super().__init__(name=f"RSI_{oversold}_{overbought}")
        self.oversold = oversold
        self.overbought = overbought
    
    def generate_signal(
        self, 
        ticker: str, 
        simulated_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate signal based on RSI thresholds."""
        
        try:
            price_data = get_historical_price_data(ticker, period="6mo", as_of=simulated_date)
            
            if price_data.empty or len(price_data) < 14:
                return self._hold_signal(ticker, simulated_date, "Insufficient data for RSI calculation")
            
            indicators = calculate_technical_indicators(price_data)
            rsi = indicators.get('RSI_14')
            current_price = float(price_data['Close'].iloc[-1])
            
            if rsi is None:
                return self._hold_signal(ticker, simulated_date, "RSI indicator not available")
            
            # Decision logic
            if rsi < self.oversold:
                action = "BUY"
                rationale = f"RSI_14 ({rsi:.2f}) < {self.oversold}: oversold, potential rebound"
                entry_price = current_price
                take_profit = round(current_price * 1.05, 2)
                stop_loss = round(current_price * 0.98, 2)
                position_size = 15
            elif rsi > self.overbought:
                action = "SELL"
                rationale = f"RSI_14 ({rsi:.2f}) > {self.overbought}: overbought, potential pullback"
                entry_price = current_price
                take_profit = round(current_price * 0.95, 2)
                stop_loss = round(current_price * 1.02, 2)
                position_size = 15
            else:
                return self._hold_signal(ticker, simulated_date, f"RSI_14 ({rsi:.2f}) in neutral range [{self.oversold}, {self.overbought}]")
            
            return {
                "baseline_name": self.name,
                "ticker": ticker,
                "simulated_date": simulated_date or datetime.now().date().isoformat(),
                "trading_strategy": {
                    "action": action,
                    "entry_price": entry_price,
                    "take_profit": take_profit,
                    "stop_loss": stop_loss,
                    "position_size_pct": position_size,
                    "rationale": rationale
                }
            }
        
        except Exception as e:
            return self._hold_signal(ticker, simulated_date, f"Error: {str(e)}")
    
    def _hold_signal(self, ticker: str, simulated_date: Optional[str], reason: str) -> Dict[str, Any]:
        """Helper to generate HOLD signal."""
        return {
            "baseline_name": self.name,
            "ticker": ticker,
            "simulated_date": simulated_date or datetime.now().date().isoformat(),
            "trading_strategy": {
                "action": "HOLD",
                "entry_price": None,
                "take_profit": None,
                "stop_loss": None,
                "position_size_pct": 0,
                "rationale": reason
            }
        }


class RandomBaseline(BaselineStrategy):
    """
    Baseline B4: Random (coinflip)
    Randomly choose BUY or SELL with 50/50 probability.
    Sanity check baseline (expected ~50% accuracy).
    
    Uses a deterministic per-call seed derived from hash(ticker + date)
    so that results are reproducible across runs but vary across
    different (ticker, date) combinations.
    """
    
    def __init__(self, seed: Optional[int] = None):
        super().__init__(name="Random")
        self.base_seed = seed  # optional base seed mixed into per-call hash
    
    def generate_signal(
        self, 
        ticker: str, 
        simulated_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Randomly choose BUY or SELL (deterministic per ticker+date)."""
        
        import random
        import hashlib
        # Build a deterministic seed from ticker + date (+ optional base_seed)
        seed_str = f"{ticker}|{simulated_date or ''}|{self.base_seed or ''}"
        seed_hash = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed_hash)
        action = rng.choice(["BUY", "SELL"])
        
        try:
            price_data = get_historical_price_data(ticker, period="5d", as_of=simulated_date)
            if not price_data.empty:
                current_price = float(price_data['Close'].iloc[-1])
                entry_price = current_price
                if action == "BUY":
                    take_profit = round(current_price * 1.05, 2)
                    stop_loss = round(current_price * 0.98, 2)
                else:
                    take_profit = round(current_price * 0.95, 2)
                    stop_loss = round(current_price * 1.02, 2)
            else:
                entry_price = None
                take_profit = None
                stop_loss = None
        except Exception:
            entry_price = None
            take_profit = None
            stop_loss = None
        
        return {
            "baseline_name": self.name,
            "ticker": ticker,
            "simulated_date": simulated_date or datetime.now().date().isoformat(),
            "trading_strategy": {
                "action": action,
                "entry_price": entry_price,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "position_size_pct": 20,
                "rationale": f"Random baseline: {action} (coinflip)"
            }
        }


# Factory function for easy instantiation
def get_baseline(name: str) -> BaselineStrategy:
    """
    Get a baseline strategy by name.
    
    Args:
        name: One of 'buy_hold', 'sma', 'rsi', 'random'
    
    Returns:
        BaselineStrategy instance
    """
    baselines = {
        'buy_hold': BuyAndHoldBaseline(),
        'sma': SMAcrossoverBaseline(),
        'rsi': RSIthresholdBaseline(),
        'random': RandomBaseline(seed=42),  # per-call seed from hash(ticker+date+42)
    }
    
    if name not in baselines:
        raise ValueError(f"Unknown baseline: {name}. Choose from: {list(baselines.keys())}")
    
    return baselines[name]
