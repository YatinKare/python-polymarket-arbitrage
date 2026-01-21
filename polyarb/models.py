"""Core data models for Polymarket arbitrage analysis."""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    """Type of event being modeled."""
    TOUCH = "touch"
    ABOVE = "above"
    BELOW = "below"


class Side(str, Enum):
    """Order book side for CLOB API."""
    BUY = "BUY"
    SELL = "SELL"


class IVMode(str, Enum):
    """Implied volatility selection mode."""
    AUTO = "auto"
    MANUAL = "manual"


class Verdict(str, Enum):
    """Verdict on Polymarket price vs fair value."""
    CHEAP = "Cheap"
    FAIR = "Fair"
    EXPENSIVE = "Expensive"


@dataclass
class Market:
    """Polymarket market data from Gamma API."""
    id: str
    title: str
    description: str
    end_date: datetime
    outcomes: list[str]
    clob_token_ids: dict[str, str]  # outcome label -> token_id

    # Additional fields that may be useful
    active: bool = True
    closed: bool = False
    archived: bool = False

    @property
    def has_binary_outcomes(self) -> bool:
        """Check if market has exactly two outcomes (Yes/No)."""
        return len(self.outcomes) == 2


@dataclass
class TokenPrice:
    """Price data for a Polymarket token from CLOB API."""
    token_id: str
    side: Side
    price: float  # Price in [0, 1] range

    def validate(self) -> None:
        """Validate that price is in valid range."""
        if not 0 <= self.price <= 1:
            raise ValueError(f"Price {self.price} must be in [0, 1] range")


@dataclass
class OrderBookLevel:
    """Single level in order book."""
    price: float
    size: float


@dataclass
class OrderBook:
    """Order book data from CLOB API."""
    token_id: str
    bids: list[OrderBookLevel]  # Buy orders (sorted descending by price)
    asks: list[OrderBookLevel]  # Sell orders (sorted ascending by price)
    timestamp: datetime

    @property
    def best_bid(self) -> Optional[float]:
        """Best bid price (highest buy price)."""
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        """Best ask price (lowest sell price)."""
        return self.asks[0].price if self.asks else None

    @property
    def mid_price(self) -> Optional[float]:
        """Mid-market price."""
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2
        return None


@dataclass
class AnalysisInputs:
    """All inputs required for pricing analysis."""

    # Market identification
    market_id: str
    ticker: str  # e.g., "SPY", "BTC-USD"

    # Event specification
    event_type: EventType
    level: float  # Strike for digital, barrier for touch
    expiry: date  # Polymarket expiration date

    # Polymarket prices
    yes_price: Optional[float] = None  # If not provided, fetch from CLOB
    no_price: Optional[float] = None

    # Market data parameters
    spot_price: Optional[float] = None  # S0, fetched if not provided

    # Risk-free rate (provide one or the other)
    rate: Optional[float] = None  # Annual risk-free rate (decimal, e.g., 0.05 for 5%)
    fred_series_id: Optional[str] = None  # FRED series ID to fetch rate

    # Dividend yield
    div_yield: float = 0.0  # Annual dividend yield (decimal)

    # Implied volatility settings
    iv_mode: IVMode = IVMode.AUTO
    iv: Optional[float] = None  # Manual IV (required if iv_mode=MANUAL)
    iv_strike_window: float = 0.05  # ±5% moneyness for strike region (used in AUTO mode)

    # Verdict thresholds
    abs_tol: float = 0.01  # Absolute price difference tolerance
    pct_tol: float = 0.05  # Percentage difference tolerance (5%)

    # Output options
    output_path: Optional[str] = None
    output_format: str = "markdown"  # v1: markdown only

    # Additional context
    outcome_label: Optional[str] = None  # For multi-outcome markets, which outcome to analyze

    def validate(self) -> list[str]:
        """Validate inputs and return list of warnings/errors."""
        errors = []

        # Validate level
        if self.level <= 0:
            errors.append(f"Level must be positive, got {self.level}")

        # Validate expiry is in future
        if self.expiry < date.today():
            errors.append(f"Expiry {self.expiry} is in the past")

        # Validate IV if manual mode
        if self.iv_mode == IVMode.MANUAL:
            if self.iv is None:
                errors.append("IV must be provided when iv_mode=MANUAL")
            elif self.iv <= 0:
                errors.append(f"IV must be positive, got {self.iv}")

        # Validate yes/no prices if provided
        if self.yes_price is not None and not 0 <= self.yes_price <= 1:
            errors.append(f"Yes price {self.yes_price} must be in [0, 1]")
        if self.no_price is not None and not 0 <= self.no_price <= 1:
            errors.append(f"No price {self.no_price} must be in [0, 1]")

        # Validate rate if provided
        if self.rate is not None and self.rate < 0:
            errors.append(f"Rate must be non-negative, got {self.rate}")

        # Validate div_yield
        if self.div_yield < 0:
            errors.append(f"Dividend yield must be non-negative, got {self.div_yield}")

        # Validate iv_strike_window
        if self.iv_strike_window <= 0:
            errors.append(f"IV strike window must be positive, got {self.iv_strike_window}")

        # Validate tolerances
        if self.abs_tol < 0:
            errors.append(f"Absolute tolerance must be non-negative, got {self.abs_tol}")
        if self.pct_tol < 0:
            errors.append(f"Percentage tolerance must be non-negative, got {self.pct_tol}")

        return errors


@dataclass
class PricingResult:
    """Results from pricing engine."""
    probability: float  # Risk-neutral probability of event
    pv: float  # Present value (discounted expected payout)

    # Intermediate values for reporting
    d2: Optional[float] = None  # For digital options
    drift: Optional[float] = None  # Risk-neutral drift μ

    # Sensitivity analysis (varying sigma)
    sensitivity: dict[str, tuple[float, float]] = field(default_factory=dict)
    # e.g., {"sigma-0.02": (prob, pv), "sigma+0.02": (prob, pv), ...}


@dataclass
class AnalysisResults:
    """Complete analysis results."""

    # Inputs (for reference)
    inputs: AnalysisInputs

    # Fetched market data
    market: Market
    spot_price: float  # S0
    risk_free_rate: float  # r
    implied_vol: float  # σ
    time_to_expiry: float  # T in years

    # Pricing results
    pricing: PricingResult

    # Polymarket comparison
    poly_yes_price: float
    poly_no_price: float

    # Verdict
    verdict: Verdict
    mispricing_abs: float  # poly_price - fair_pv
    mispricing_pct: float  # (poly_price - fair_pv) / fair_pv

    # Additional metadata
    iv_source: str = "auto"  # Description of how IV was obtained
    rate_source: str = "manual"  # Description of how rate was obtained
    warnings: list[str] = field(default_factory=list)


@dataclass
class ReportContext:
    """All data needed to generate A-G report sections."""

    # Core results
    results: AnalysisResults

    # Additional computed values for derivation section
    log_moneyness: float  # ln(S0/K) or ln(S0/B)
    variance_term: float  # σ√T

    # Model selection explanation
    model_name: str  # "Digital Option" or "Touch Barrier"
    model_rationale: str  # Why this model was chosen

    # Formulas used (for Section C)
    formulas: dict[str, str] = field(default_factory=dict)
    # e.g., {"d2": "...", "probability": "...", "pv": "..."}

    # Professional conclusion (for Section E)
    conclusion_text: Optional[str] = None

    # Layman explanation (for Section F)
    layman_text: Optional[str] = None

    # One-liner takeaway (for Section G)
    takeaway: Optional[str] = None
