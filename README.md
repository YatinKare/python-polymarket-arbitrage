# Polymarket Options-Implied Fair Value CLI

A Python CLI tool that computes **risk-neutral fair values** for Polymarket binary markets using options pricing models (digital options and touch barriers). Compare tradable Polymarket prices against model-implied fair values to identify potential arbitrage opportunities.

## Features

- **Market Discovery**: Search and list Polymarket markets via the Gamma API
- **Fair Value Pricing**: Compute risk-neutral fair values using:
  - **Digital options** (Black-Scholes) for terminal settle events (above/below at expiry)
  - **Touch barrier options** for path-dependent events (barrier hit before expiry)
- **Market Data Integration**: Fetch spot prices, option chains, and implied volatility from yfinance
- **Risk-Free Rate**: Pull current rates from FRED (Federal Reserve Economic Data) API
- **IV Interpolation**: Smart strike-region selection and term-structure interpolation
- **Comprehensive Reports**: Generate detailed A-G analysis sections in Markdown
- **Sensitivity Analysis**: Compute fair value across volatility scenarios

## Installation

This project uses `uv` for Python package management. No other tools required.

### Prerequisites

- [uv](https://github.com/astral-sh/uv) installed
- Python 3.13+ (managed by uv)
- FRED API key (free from [FRED API](https://fred.stlouisfed.org/docs/api/api_key.html))

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/python-polymarket-arbitrage.git
cd python-polymarket-arbitrage
```

2. Install dependencies (uv handles everything):
```bash
uv sync
```

3. Set up your FRED API key:
```bash
# Create .env file
echo "FRED_API_KEY=your_api_key_here" > .env
```

That's it! You're ready to run the CLI.

## Usage

All commands use `uv run` to execute in the managed environment.

### 1. List Markets

Search for Polymarket markets by keyword:

```bash
# Search for Bitcoin-related markets
uv run polyarb markets --search "BTC"

# Search for election markets
uv run polyarb markets --search "Trump" --limit 5

# List recent markets
uv run polyarb markets --limit 20
```

### 2. Analyze a Market

Compute fair value for a specific market:

```bash
# Basic usage (will prompt for missing inputs)
uv run polyarb analyze MARKET_ID

# Full example: BTC touch event
uv run polyarb analyze 12345 \
  --ticker BTC-USD \
  --event-type touch \
  --level 80000 \
  --rate 0.035 \
  --div-yield 0.0

# Digital option: SPY above at expiry
uv run polyarb analyze 67890 \
  --ticker SPY \
  --event-type above \
  --level 500 \
  --expiry 2026-03-20 \
  --fred-series-id DGS3MO \
  --div-yield 0.013

# Save report to file
uv run polyarb analyze 12345 \
  --ticker BTC-USD \
  --event-type touch \
  --level 80000 \
  --rate 0.035 \
  --output report.md
```

#### Event Types

- `touch`: Barrier hit before expiry (path-dependent)
- `above`: Asset above strike at expiry (terminal)
- `below`: Asset below strike at expiry (terminal)

#### Required Inputs

- `MARKET_ID`: Polymarket market ID (from `markets` command or Polymarket URL)
- `--ticker`: yfinance ticker (e.g., SPY, BTC-USD, ^GSPC)
- `--event-type`: One of {touch, above, below}
- `--level`: Barrier/strike price

#### Risk-Free Rate (choose one)

- `--rate FLOAT`: Directly provide annual rate as decimal (e.g., 0.035 for 3.5%)
- `--fred-series-id TEXT`: FRED series ID to fetch rate (e.g., DGS3MO, DFF)

#### Optional Inputs

- `--expiry YYYY-MM-DD`: Override market end date
- `--yes-price FLOAT`: Override Polymarket Yes price (default: fetch from CLOB)
- `--no-price FLOAT`: Override Polymarket No price (default: fetch from CLOB)
- `--div-yield FLOAT`: Annual dividend yield as decimal (default: 0.0)
- `--iv FLOAT`: Manual implied volatility (default: auto-extract from options)
- `--iv-mode {auto|manual}`: IV selection mode (default: auto)
- `--iv-strike-window FLOAT`: Moneyness window for IV extraction (default: 0.05 = ±5%)
- `--abs-tol FLOAT`: Absolute tolerance for fair value verdict (default: 0.01)
- `--pct-tol FLOAT`: Percentage tolerance for fair value verdict (default: 0.05 = 5%)
- `--output PATH`: Write report to file (default: stdout)

### 3. Fetch Risk-Free Rates

Query FRED for current risk-free rate data:

```bash
# Fetch specific rate series
uv run polyarb rates --series-id DGS3MO  # 3-month T-bill

# Search for rate series
uv run polyarb rates --search "treasury bill"

# Both together
uv run polyarb rates --search "federal funds" --series-id DFF
```

Common FRED series IDs:
- `DGS3MO`: 3-Month Treasury Constant Maturity
- `DGS6MO`: 6-Month Treasury Constant Maturity
- `DGS1`: 1-Year Treasury Constant Maturity
- `DFF`: Federal Funds Effective Rate
- `DTB3`: 3-Month Treasury Bill Secondary Market Rate

### 4. Verbose Mode

Enable debug logging for any command:

```bash
uv run polyarb -v markets --search "BTC"
uv run polyarb --verbose analyze 12345 --ticker BTC-USD --event-type touch --level 80000
```

## Report Output

The `analyze` command generates a comprehensive Markdown report with 7 sections:

### Section A: Input Summary
Table of all input parameters (ticker, spot, strike, expiry, rates, volatility, etc.)

### Section B: Model Choice
Explanation of which pricing model was used and why (digital vs touch)

### Section C: Mathematical Derivation
Full step-by-step derivation with formulas, intermediate values, and sensitivity analysis

### Section D: Fair vs Polymarket Comparison
Comparison table showing model PV, Polymarket price, mispricing, and verdict (Fair/Cheap/Expensive)

### Section E: Professional Conclusion
Technical one-paragraph summary with assumptions, methodology, and investment implications

### Section F: Layman Explanation
Plain-language explanation suitable for non-experts (no jargon)

### Section G: One-Liner Takeaway
Single sentence summary with key numbers and verdict

## Environment Variables

- `FRED_API_KEY`: Your FRED API key (required for rate fetching)

Set in `.env` file or export directly:

```bash
export FRED_API_KEY=your_api_key_here
```

## Project Structure

```
polyarb/
├── cli.py                    # Click-based CLI commands
├── models.py                 # Data models (Market, AnalysisInputs, etc.)
├── util/                     # Utility functions
│   ├── dates.py             # Date parsing and time calculations
│   ├── math.py              # Math helpers
│   └── fmt.py               # Number formatting
├── clients/                  # API clients
│   ├── polymarket_gamma.py  # Polymarket Gamma API (markets)
│   ├── polymarket_clob.py   # Polymarket CLOB API (prices)
│   ├── fred.py              # FRED API (risk-free rates)
│   └── yfinance_md.py       # yfinance wrapper (market data)
├── vol/                      # Volatility logic
│   ├── iv_extract.py        # IV extraction from option chains
│   └── term_structure.py    # Term structure interpolation
├── pricing/                  # Pricing engines
│   ├── digital_bs.py        # Digital option pricing (Black-Scholes)
│   └── touch_barrier.py     # Touch barrier pricing (first-passage)
└── report/                   # Report generation
    └── markdown_report.py   # A-G section renderer
```

## Testing

Run the test suite with pytest:

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_pricing_digital.py

# Run with coverage
uv run pytest --cov=polyarb --cov-report=html
```

Current test coverage: **237 tests passing**
- 11 CLI validation tests
- 10 Gamma client tests
- 15 CLOB client tests
- 19 FRED client tests
- 26 yfinance client tests
- 32 IV extraction tests
- 39 term structure tests
- 30 digital pricing tests
- 26 touch barrier pricing tests
- 29 report generation tests

## Examples

### Example 1: BTC Touch $100K

```bash
uv run polyarb analyze MARKET_ID \
  --ticker BTC-USD \
  --event-type touch \
  --level 100000 \
  --fred-series-id DGS3MO \
  --div-yield 0.0 \
  --output btc_touch_100k.md
```

### Example 2: SPY Above $500 at Expiry

```bash
uv run polyarb analyze MARKET_ID \
  --ticker SPY \
  --event-type above \
  --level 500 \
  --expiry 2026-06-19 \
  --rate 0.035 \
  --div-yield 0.013 \
  --output spy_above_500.md
```

### Example 3: Manual IV Mode

```bash
uv run polyarb analyze MARKET_ID \
  --ticker BTC-USD \
  --event-type above \
  --level 90000 \
  --iv-mode manual \
  --iv 0.50 \
  --rate 0.035 \
  --output btc_manual_iv.md
```

## Methodology

### Digital Options (Terminal Events)

For "above" or "below" at expiry:

1. Use Black-Scholes risk-neutral framework
2. Compute d₂ = (ln(S₀/K) + (r - q - 0.5σ²)T) / (σ√T)
3. Probability: P(above) = N(d₂), P(below) = N(-d₂)
4. Present value: PV = exp(-rT) × P(event)

### Touch Barriers (Path-Dependent Events)

For "touch" events (barrier hit before expiry):

1. Use geometric Brownian motion with drift μ = r - q - 0.5σ²
2. Apply reflection principle for first-passage probability
3. Account for barrier direction (upper if B > S₀, lower if B < S₀)
4. Present value: PV = exp(-rT) × P(hit)

### Implied Volatility Selection

1. Extract option chains from yfinance for relevant expiries
2. Filter strikes within ±5% moneyness window around barrier/strike
3. Interpolate IV at exact strike using log-moneyness
4. If expiry doesn't match option expiries, interpolate across term structure using total variance
5. Run sensitivity analysis (±2%, ±3% vol shifts)

### Verdict Logic

Compare Polymarket price to model fair PV:

- **Fair**: |poly - fair| ≤ 0.01 OR |poly - fair| / fair ≤ 5%
- **Cheap**: poly < fair beyond tolerance (potential buy opportunity)
- **Expensive**: poly > fair beyond tolerance (potential sell opportunity)

Tolerances are configurable via `--abs-tol` and `--pct-tol`.

## Troubleshooting

### yfinance Missing IV Fields

**Problem**: Option chain has missing `impliedVolatility` fields.

**Solution**: yfinance data quality varies by ticker and expiry. The tool automatically:
- Drops strikes with missing IV
- Warns if too many strikes are missing
- Auto-expands strike window if needed (up to ±20%)
- Falls back to nearest strike if only one available

If all IVs are missing, use `--iv-mode manual` with `--iv` to provide your own volatility estimate.

### Polymarket Token Mapping Issues

**Problem**: Market has multiple outcomes and tool can't auto-select Yes/No.

**Solution**: The tool will prompt you to select the outcome interactively. For multi-outcome markets, you'll be asked to choose which outcome to analyze.

**Tip**: Use `polyarb markets --search "keyword"` to find market IDs and preview outcomes before analysis.

### FRED API Key Not Set

**Problem**: `Error: FRED_API_KEY environment variable not set`

**Solution**:
1. Get a free API key from https://fred.stlouisfed.org/docs/api/api_key.html
2. Add to `.env` file: `FRED_API_KEY=your_key_here`
3. Or export directly: `export FRED_API_KEY=your_key_here`

**Alternative**: Use `--rate` flag to provide risk-free rate directly instead of fetching from FRED.

### Missing Option Chains

**Problem**: No option chains available for ticker or expiry.

**Solution**: yfinance only provides options for tickers with listed options (primarily equities and major ETFs). For crypto (BTC-USD, ETH-USD):
- Use Deribit options if available via other data sources
- Or use `--iv-mode manual` with historical/implied vol estimate

**Workaround**: Analyze using a proxy ticker (e.g., BITO for BTC exposure) if correlation is high.

### Expiry Date Mismatches

**Problem**: Polymarket expiry doesn't match listed option expiries.

**Solution**: The tool automatically interpolates IV across term structure:
1. Finds bracketing expiries (before and after Polymarket expiry)
2. Interpolates using total variance: w(T) = σ²T
3. Extrapolates if Polymarket expiry is beyond all option expiries (with warning)

**Note**: Extrapolation is less reliable. Prefer markets where expiry aligns with standard option expiries (monthly/quarterly).

### Unusual Rate or Dividend Yield Values

**Problem**: Tool warns about unusual rate or dividend yield.

**Solution**: These are warnings, not errors. The tool checks:
- Risk-free rate should be in [-10%, 30%] range
- Dividend yield should be in [0%, 20%] range

If your inputs are intentional (e.g., negative rates in certain environments), you can ignore the warning. The analysis will proceed.

### High Implied Volatility

**Problem**: IV extraction warns about very high volatility (>500%).

**Solution**: This usually indicates:
- Stale or bad yfinance data (very OTM options)
- Actual high vol event (earnings, major news)

**Action**:
1. Verify the IV makes sense for the underlying
2. Check yfinance data freshness with `--verbose`
3. Use `--iv-mode manual` if data quality is poor

## Limitations

### Version 1 Scope

This is v1 with the following intentional limitations:

- **Output format**: Markdown only (JSON/CSV planned for v2)
- **Size-aware pricing**: Best quote only, no order book depth analysis (v2)
- **Bulk scanning**: Single market analysis only, no portfolio scanning (v3)
- **Exotic events**: Simple touch/digital only, no complex multi-barrier or path-dependent structures

### Model Assumptions

The pricing models make standard assumptions:

1. **Geometric Brownian motion**: Log-normal returns, constant drift/vol
2. **Risk-neutral pricing**: Market prices options efficiently
3. **No transaction costs**: Frictionless arbitrage
4. **Continuous trading**: No gaps or lockouts
5. **No counterparty risk**: Polymarket settles as promised

Real-world conditions may differ significantly. **Use model outputs as guidance, not gospel.**

### Data Quality Dependencies

Fair value accuracy depends on input data quality:

- **yfinance**: Option data can be stale, especially for OTM strikes
- **Polymarket**: Low liquidity markets have wide bid-ask spreads
- **FRED**: Rates are updated daily (lags real-time rates)
- **Dividends**: Often estimated, not announced

Always verify inputs and sanity-check outputs before trading.

## Contributing

Contributions welcome! Areas of interest:

- Additional pricing models (American options, exotic barriers)
- Better data sources (paid options data APIs)
- Portfolio scanning and ranking
- Risk management utilities
- UI/dashboard (Streamlit, Dash)

Please open an issue before major PRs to discuss approach.

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- [Polymarket](https://polymarket.com) for prediction market data
- [yfinance](https://github.com/ranaroussi/yfinance) for market data
- [FRED](https://fred.stlouisfed.org/) for economic data
- Black-Scholes and barrier option pricing literature

## Disclaimer

**This tool is for educational and research purposes only.**

Options and prediction market trading involves substantial risk of loss. The models and analysis provided are simplified approximations of complex financial instruments. Do not rely solely on this tool for investment decisions. Always conduct your own due diligence, understand the risks, and consult with qualified financial professionals.

The authors assume no liability for any financial losses incurred through use of this software.
