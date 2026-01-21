# Progress: plan

Started: Tue Jan 20 22:41:07 EST 2026

## Status

IN_PROGRESS

## Analysis

### Current State
This is a greenfield project with minimal initialization:
- ✅ Git repository initialized
- ✅ Python 3.13 version configured
- ✅ FRED API key configured in .env
- ✅ Basic pyproject.toml structure exists
- ✅ Minimal main.py stub present
- ❌ No dependencies installed
- ❌ No source package structure exists
- ❌ No modules or code implemented

### What the Plan Requires
The plan describes a comprehensive CLI tool for Polymarket options-implied fair value analysis:

**Core Functionality:**
1. Pull Polymarket market data (Gamma + CLOB APIs)
2. Pull market data (yfinance: spot, options, IV)
3. Pull risk-free rates (FRED API)
4. Compute risk-neutral fair value using options pricing models (digital vs touch)
5. Generate A-G analysis report in Markdown format

**Architecture (from plan):**
- `polyarb/` package with submodules: cli, models, util, clients, vol, pricing, report
- `click`-based CLI with 3 commands: markets, analyze, rates
- Separated concerns: CLI → Data fetching → Vol interpolation → Pricing → Reporting
- Pure math functions isolated from I/O

**Technical Requirements:**
- Use `uv` exclusively (no pip/poetry/conda)
- Dependencies: click, yfinance, httpx, numpy, scipy, pytest, pytest-mock
- CLI entrypoint: `polyarb = polyarb.cli:main`
- Two pricing models: digital (terminal settle) and touch (barrier hit)
- IV selection from strike region + term structure interpolation
- Risk-neutral pricing with discounting

**Output Format:**
Markdown report with 7 sections:
- A: Input summary table
- B: Model choice explanation
- C: Full derivation with formulas
- D: Fair vs Polymarket comparison + verdict
- E: Professional conclusion
- F: Layman explanation
- G: One-liner takeaway

### Dependencies Between Tasks
Critical path identified:
1. Setup project structure FIRST (dependencies, directories)
2. Define data models (needed by all modules)
3. Implement clients (needed by CLI and pricing)
4. Implement pricing engines (needed by report generation)
5. Implement IV/vol logic (needed by pricing)
6. Implement reporting (needs all pricing outputs)
7. Wire up CLI (orchestrates everything)
8. Add tests (validates correctness)

### Contingencies & Edge Cases
From the plan analysis, must handle:
- Missing dividend yield (default to 0, warn)
- Missing IV data (drop, interpolate, or fallback with warning)
- Non-matching expiries (term structure interpolation)
- Multiple outcomes in markets (prompt for outcome label)
- FRED API failures (require --rate override)
- yfinance data quality issues
- Touch barrier direction (upper vs lower)
- Zero/negative inputs (validation)
- Prices outside [0,1] range (validation)
- Expiry in past (validation)
- Missing option chains (error gracefully)

## Task List

### Phase 1: Foundation & Setup
- [x] 1.1: Initialize uv project structure and add dependencies
  - Run `uv add click yfinance httpx numpy scipy`
  - Run `uv add --dev pytest pytest-mock`
  - Verify pyproject.toml has correct `project.scripts` entrypoint

- [x] 1.2: Create package directory structure
  - Create polyarb/ directory with __init__.py
  - Create polyarb/util/ with __init__.py, dates.py, math.py, fmt.py
  - Create polyarb/clients/ with __init__.py (client files added in later tasks)
  - Create polyarb/vol/ with __init__.py (vol files added in later tasks)
  - Create polyarb/pricing/ with __init__.py (pricing files added in later tasks)
  - Create polyarb/report/ with __init__.py (report files added in later tasks)
  - Create tests/ directory

### Phase 2: Data Models & Utilities
- [x] 2.1: Define core data models in polyarb/models.py
  - Market model (id, title, endDate, clobTokenIds, outcomes)
  - TokenPrice model (token_id, side, price)
  - AnalysisInputs model (ticker, event_type, level, expiry, etc.)
  - AnalysisResults model (probability, pv, verdict, etc.)
  - ReportContext model (all data for A-G sections)

- [x] 2.2: Implement utility modules
  - polyarb/util/dates.py: date parsing, validation, time-to-expiry calculation
  - polyarb/util/math.py: basic math helpers (log, exp, clamp)
  - polyarb/util/fmt.py: number formatting for tables/reports

### Phase 3: API Clients
- [x] 3.1: Implement Polymarket Gamma client (polyarb/clients/polymarket_gamma.py)
  - GammaClient class with httpx client
  - get_market(market_id) -> Market model
  - search_markets(query, limit) -> list[Market]
  - Handle API errors gracefully

- [x] 3.2: Implement Polymarket CLOB client (polyarb/clients/polymarket_clob.py)
  - ClobClient class with httpx client
  - get_price(token_id, side) -> TokenPrice
  - get_book(token_id) -> order book data (for phase 2)
  - Map "Yes/No" to token IDs correctly

- [x] 3.3: Implement FRED client (polyarb/clients/fred.py)
  - FredClient class with httpx client and API key from env
  - get_series_observations(series_id) -> latest rate value
  - search_series(query) -> list of series (for rates command)
  - Handle missing FRED_API_KEY gracefully

- [x] 3.4: Implement yfinance wrapper (polyarb/clients/yfinance_md.py)
  - YFMarketData class wrapping yfinance
  - get_spot(ticker) -> float (S0)
  - get_option_expiries(ticker) -> list[date]
  - get_chain(ticker, expiry) -> calls/puts DataFrames with normalized IV
  - Handle missing tickers and missing IV fields with warnings

### Phase 4: Volatility & IV Logic
- [x] 4.1: Implement IV extraction (polyarb/vol/iv_extract.py)
  - extract_strike_region_iv(chain, strike_level, window_pct) -> float
  - Find strikes around barrier/level (e.g., ±5% moneyness)
  - Interpolate IV at exact strike using log-moneyness
  - Handle missing IVs (drop or warn)

- [x] 4.2: Implement term structure interpolation (polyarb/vol/term_structure.py)
  - find_bracketing_expiries(target_date, available_expiries) -> (before, after)
  - interpolate_variance(iv1, t1, iv2, t2, target_t) -> target_iv
  - Use total variance: w(T) = σ²T, linear interpolation
  - Handle edge cases (exact match, only one expiry available)

### Phase 5: Pricing Engines
- [x] 5.1: Implement digital option pricing (polyarb/pricing/digital_bs.py)
  - digital_price(S0, K, T, r, q, sigma, direction) -> (probability, pv)
  - direction: 'above' or 'below'
  - Compute d2 = (ln(S0/K) + (r - q - 0.5σ²)T) / (σ√T)
  - P(above) = N(d2), P(below) = N(-d2)
  - PV = exp(-rT) * P
  - Add sensitivity analysis (vary sigma by ±0.02, ±0.03)

- [x] 5.2: Implement touch barrier pricing (polyarb/pricing/touch_barrier.py)
  - touch_price(S0, B, T, r, q, sigma) -> (probability, pv)
  - Determine barrier direction (upper if B > S0, lower if B < S0)
  - Use log-process first-passage probability with drift
  - Implement reflection principle formula carefully
  - Test against known limits (driftless, high vol, short T)
  - PV = exp(-rT) * P_hit

- [ ] 5.3: Add verdict logic
  - compute_verdict(poly_price, fair_pv, abs_tol, pct_tol) -> str
  - "Fair" if abs_diff <= abs_tol OR pct_diff <= pct_tol
  - "Cheap" if poly < fair beyond tolerance
  - "Expensive" if poly > fair beyond tolerance

### Phase 6: Reporting
- [ ] 6.1: Implement markdown report generator (polyarb/report/markdown_report.py)
  - render(ctx: ReportContext) -> str
  - Section A: Input summary table (ticker, spot, strike, expiry, rates, vol, etc.)
  - Section B: Model choice explanation (touch vs terminal, why)
  - Section C: Full derivation with formulas and intermediate values
  - Section D: Fair vs Polymarket comparison table with verdict
  - Section E: Professional one-paragraph conclusion
  - Section F: Layman explanation (no jargon)
  - Section G: One-liner takeaway with key numbers

### Phase 7: CLI Implementation
- [ ] 7.1: Implement CLI command structure (polyarb/cli.py)
  - Main click group with subcommands
  - Setup logging/error handling
  - Environment variable loading (FRED_API_KEY)

- [ ] 7.2: Implement `markets` command
  - Options: --search, --slug, --limit
  - Call GammaClient.search_markets()
  - Output table: id, title, endDate

- [ ] 7.3: Implement `analyze` command - input handling
  - Core inputs: MARKET_ID (required), --ticker, --event-type, --level, --expiry
  - Price inputs: --yes-price, --no-price (optional, fetch from CLOB if not provided)
  - Rate inputs: --rate OR --fred-series-id
  - Div yield: --div-yield
  - Vol inputs: --iv-mode [auto|manual], --iv, --iv-strike-window
  - Output: --output PATH, --format (v1: markdown only)
  - Verdict thresholds: --abs-tol, --pct-tol
  - Add click prompts for missing required inputs

- [ ] 7.4: Implement `analyze` command - orchestration logic
  - Fetch market from Gamma (get endDate, token IDs, outcomes)
  - Map Yes/No outcomes to token IDs (handle multi-outcome with prompt)
  - Fetch Polymarket prices from CLOB
  - Fetch yfinance spot + option chains
  - Fetch or use provided risk-free rate
  - Select IV using vol module (strike region + term structure)
  - Choose pricing model (touch vs digital based on event-type)
  - Run pricing engine with sensitivity analysis
  - Build ReportContext
  - Generate markdown report
  - Write to file if --output provided, else print to stdout

- [ ] 7.5: Implement `rates` command (optional)
  - Options: --series-id OR --search
  - Fetch and print latest rate value from FRED

- [ ] 7.6: Add input validation
  - validate_inputs() function
  - Check: expiry in future, level > 0, IV > 0, yes/no prices in [0,1]
  - Warn if dividend yield not provided (default to 0)
  - Warn if Polymarket expiry differs from user override

### Phase 8: Testing
- [ ] 8.1: Create test fixtures
  - tests/fixtures/ directory
  - Mock JSON responses for Gamma, CLOB, FRED APIs
  - Sample option chain DataFrames

- [ ] 8.2: Write pricing tests
  - tests/test_pricing_digital.py
    - Test edge cases: S0 >> K, S0 << K, σ → 0, T → 0
    - Test symmetry: P(above) + P(below) ≈ 1
  - tests/test_pricing_touch.py
    - Test driftless case against known formula
    - Test limits: very high vol, very short T
    - Test probability bounds [0,1]

- [ ] 8.3: Write IV interpolation tests
  - tests/test_iv_interpolation.py
    - Test strike region extraction
    - Test term structure interpolation
    - Test edge cases (exact match, single expiry)

- [ ] 8.4: Write report tests
  - tests/test_report_sections.py
    - Assert all A-G section headers present
    - Check markdown structure validity

- [ ] 8.5: Write client tests with mocks
  - Use pytest-mock to patch httpx.get
  - Test Gamma, CLOB, FRED clients with fixtures
  - Test error handling

### Phase 9: Documentation & Packaging
- [ ] 9.1: Write README.md
  - Project overview and goal
  - Installation: `uv sync` or `uv run polyarb ...`
  - Quickstart examples:
    - `uv run polyarb markets --search "BTC"`
    - `uv run polyarb analyze <ID> --ticker BTC-USD --event-type touch --level 80000`
  - Environment variables (FRED_API_KEY)
  - Command reference

- [ ] 9.2: Add troubleshooting section to README
  - yfinance missing IV fields
  - Polymarket token mapping issues
  - FRED key not set
  - Missing option chains

- [ ] 9.3: Verify project.scripts entrypoint
  - Ensure pyproject.toml has `polyarb = "polyarb.cli:main"`
  - Test that `uv run polyarb` works

### Phase 10: Integration & Validation
- [ ] 10.1: Run end-to-end test manually
  - Pick a real Polymarket market
  - Run full analyze command with all inputs
  - Verify A-G report generated correctly
  - Check that math/probabilities are sensible

- [ ] 10.2: Run pytest suite
  - `uv run pytest`
  - Ensure all tests pass

- [ ] 10.3: Test edge cases
  - Missing dividend yield (should warn, default to 0)
  - Non-matching expiries (should interpolate)
  - Multiple outcomes (should prompt)
  - Invalid inputs (should validate and error)

- [ ] 10.4: Final checklist verification
  - Touch events use barrier-hit math ✓
  - Terminal events use digital probability ✓
  - IV from strike region near barrier ✓
  - Term structure interpolation when needed ✓
  - Risk-free rate applied via discounting ✓
  - Missing inputs trigger prompts ✓
  - Unit tests pass ✓

## Notes

### Critical Dependencies
The task order is designed to respect dependencies:
- Models must exist before clients (clients return models)
- Clients must exist before CLI (CLI calls clients)
- Pricing engines must exist before CLI orchestration
- Vol logic must exist before pricing (pricing uses IV)
- Report must exist before CLI (CLI generates reports)

### API Endpoints Reference
**Polymarket Gamma:**
- Base: https://gamma-api.polymarket.com
- GET /markets (search)
- GET /markets/{id} (details)

**Polymarket CLOB:**
- Base: https://clob.polymarket.com
- GET /price?token_id={id}&side={BUY|SELL}
- GET /prices (bulk)
- GET /book?token_id={id}

**FRED:**
- Base: https://api.stlouisfed.org/fred
- GET /series/search?search_text={query}&api_key={key}
- GET /series?series_id={id}&api_key={key}
- GET /series/observations?series_id={id}&api_key={key}

### Mathematical Formulas Reference
**Digital (Terminal):**
- d2 = (ln(S0/K) + (r - q - 0.5σ²)T) / (σ√T)
- P(above) = N(d2)
- PV = exp(-rT) * P

**Touch (Barrier):**
- a = ln(B/S0)
- μ = r - q - 0.5σ²
- Use reflection principle: P(hit) with drift μ
- PV = exp(-rT) * P_hit

**Term Structure:**
- w(T) = σ²T (total variance)
- Linear interpolation: w_target = w1 + (w2 - w1) * (T_target - T1) / (T2 - T1)
- σ_target = sqrt(w_target / T_target)

### Risk Areas
1. **Touch barrier formula correctness** - needs careful implementation and unit tests
2. **IV interpolation edge cases** - missing strikes, single expiry only
3. **Polymarket outcome mapping** - multi-outcome markets need explicit selection
4. **yfinance data quality** - IV fields may be missing or stale
5. **FRED API availability** - must allow --rate override if API fails
6. **Date/timezone handling** - Polymarket uses UTC, ensure consistency

### Success Criteria (MVP - Milestone 1)
✓ `uv run polyarb markets --search "BTC"` lists markets
✓ `uv run polyarb analyze <ID> ...` produces complete A-G Markdown report
✓ Touch events use correct barrier-hit probability formula
✓ Terminal events use correct digital probability formula
✓ IV chosen from strike region and interpolated across term structure
✓ Risk-free rate applied via discounting
✓ Missing inputs trigger prompts
✓ Unit tests pass via `uv run pytest`

### Future Enhancements (Milestone 2 & 3)
- Size-aware entry pricing via CLOB /book
- Better outcome mapping + multi-outcome prompts
- JSON output format option
- Bulk market scanning and arbitrage ranking
- More sophisticated vol surface modeling

## Completed This Iteration
- Task 5.2: Implement touch barrier pricing (polyarb/pricing/touch_barrier.py)
  - Created touch barrier pricing module for barrier hit (touch) events
    - Implements touch_price(S0, B, T, r, q, sigma) -> PricingResult
      - Determines barrier direction automatically (up if B > S0, down if B < S0)
      - Uses geometric Brownian motion with risk-neutral drift μ = r - q - 0.5σ²
      - Implements reflection principle for first-passage probability
      - Handles special case: barrier equals spot (probability = 1)
      - Handles driftless case (μ ≈ 0) with simplified formula: P(hit) = 2 * N(-|a|/(σ√T))
      - General case with drift uses two-term formula:
        - Upper barrier: P = N(-(a - μT)/(σ√T)) + exp(2λa) * N(-(a + μT)/(σ√T))
        - Lower barrier: P = N((a - μT)/(σ√T)) + exp(2λa) * N((a + μT)/(σ√T))
        - where λ = μ / σ², a = ln(B/S0)
      - PV = exp(-rT) * P(hit) for proper discounting
      - Returns PricingResult with probability, pv, and drift (d2=None for touch)
      - Validates all inputs: S0, B, T, sigma > 0
      - Clamps probability to [0, 1] to handle numerical edge cases
    - Implements touch_price_with_sensitivity(...) -> PricingResult
      - Computes base price plus sensitivity to volatility shifts
      - Default shifts: [-0.03, -0.02, 0.02, 0.03] (customizable)
      - Clamps shifted sigma to minimum 0.01 (1%) to avoid negative values
      - Returns sensitivity dict: {"sigma-0.02": (prob, pv), "sigma+0.02": (prob, pv), ...}
      - Useful for understanding pricing sensitivity to IV uncertainty
    - Custom exception: TouchPricingError for clear error handling
    - Robust input validation and error messages
  - Created comprehensive test suite (tests/test_pricing_touch.py)
    - 26 test cases covering all functions and edge cases
    - Test touch_price: 21 tests
      - Barrier equals spot (probability = 1)
      - Driftless cases for upper/lower barriers (μ = 0)
      - Upper barrier with positive drift (r > q + 0.5σ²)
      - Lower barrier with negative drift (r < q + 0.5σ²)
      - High volatility increases hit probability
      - Short time reduces hit probability for OTM barrier
      - Very close barrier has high probability (>0.9)
      - Very far barrier has low probability (<0.1)
      - Discounting correctness verification
      - Probability bounds [0, 1] for various scenarios
      - Drift calculation verification
      - d2 field is None (not applicable for touch)
      - Input validation: negative/zero S0, B, T, sigma
    - Test touch_price_with_sensitivity: 5 tests
      - Default and custom sigma shifts
      - Low base sigma handling (clamping to min 0.01)
      - Monotonicity for OTM barrier (higher vol → higher prob)
      - Base result matches direct call
    - All 26 tests passing
  - Full test suite status: 197 tests passing (171 existing + 26 new)
    - 10 Gamma client tests
    - 15 CLOB client tests
    - 19 FRED client tests
    - 26 yfinance client tests
    - 32 IV extraction tests
    - 39 term structure tests
    - 30 digital pricing tests
    - 26 touch barrier pricing tests

Previous iterations:
- Task 5.1: Implement digital option pricing (polyarb/pricing/digital_bs.py)
  - Created digital option pricing module for terminal settle-at-expiry events
    - Implements digital_price(S0, K, T, r, q, sigma, direction) -> PricingResult
      - Supports both "above" and "below" directions
      - Uses Black-Scholes framework with risk-neutral drift μ = r - q - 0.5σ²
      - Computes d2 = (ln(S0/K) + (r - q - 0.5σ²)T) / (σ√T)
      - P(above) = N(d2), P(below) = N(-d2) using standard normal CDF
      - PV = exp(-rT) * P(event) for proper discounting
      - Returns PricingResult with probability, pv, d2, and drift
      - Validates all inputs: S0, K, T, sigma > 0; direction in {above, below}
      - Clamps probability to [0, 1] to handle numerical edge cases
    - Implements digital_price_with_sensitivity(...)  -> PricingResult
      - Computes base price plus sensitivity to volatility shifts
      - Default shifts: [-0.03, -0.02, 0.02, 0.03] (customizable)
      - Clamps shifted sigma to minimum 0.01 (1%) to avoid negative values
      - Returns sensitivity dict: {"sigma-0.02": (prob, pv), "sigma+0.02": (prob, pv), ...}
      - Useful for understanding pricing sensitivity to IV uncertainty
    - Implements compute_verdict(poly_price, fair_pv, abs_tol, pct_tol) -> str
      - Determines if Polymarket price is "Fair", "Cheap", or "Expensive"
      - Fair if |poly - fair| <= abs_tol OR |poly - fair| / fair <= pct_tol
      - Cheap if poly < fair beyond tolerance
      - Expensive if poly > fair beyond tolerance
      - Handles zero fair value gracefully (uses absolute tolerance only)
    - Custom exception: DigitalPricingError for clear error handling
    - Robust input validation and error messages
  - Created comprehensive test suite (tests/test_pricing_digital.py)
    - 30 test cases covering all functions and edge cases
    - Test digital_price: 17 tests
      - ATM options (above/below) with known probabilities
      - Deep ITM/OTM scenarios (S0 >> K, S0 << K)
      - Symmetry test: P(above) + P(below) = 1
      - Limit cases: zero volatility, zero time, high volatility
      - Discounting correctness
      - Probability bounds [0, 1] for various scenarios
      - Input validation: negative/zero S0, K, T, sigma; invalid direction
    - Test digital_price_with_sensitivity: 5 tests
      - Default and custom sigma shifts
      - Low base sigma handling (clamping to min 0.01)
      - Monotonicity for OTM options (higher vol → higher prob)
      - Base result matches direct call
    - Test compute_verdict: 8 tests
      - Fair within absolute tolerance
      - Fair within percentage tolerance
      - Cheap and expensive verdicts
      - Boundary conditions
      - Zero fair value handling
      - Custom tolerances
      - Symmetry
    - All 30 tests passing
  - Full test suite status: 171 tests passing (141 existing + 30 new)
    - 10 Gamma client tests
    - 15 CLOB client tests
    - 19 FRED client tests
    - 26 yfinance client tests
    - 32 IV extraction tests
    - 39 term structure tests
    - 30 digital pricing tests

Previous iterations:
- Task 4.2: Implement term structure interpolation (polyarb/vol/term_structure.py)
  - Created term structure interpolation module for IV across time horizons
    - Implements find_bracketing_expiries(target_date, available_expiries) -> (before, after)
      - Finds expiries that bracket the target date
      - Returns exact match as (target_date, None)
      - Handles edge cases: before all, after all, empty list, single expiry
      - Works with unsorted input lists
    - Implements interpolate_variance(iv1, t1, iv2, t2, target_t) -> float
      - Linear interpolation of total variance: w(T) = σ²T
      - Formula: w_target = w1 + (w2 - w1) * (t_target - t1) / (t2 - t1)
      - Converts back to volatility: σ_target = sqrt(w_target / t_target)
      - Validates all times and IVs are positive
      - Ensures t1 < t2 and t1 <= target_t <= t2
      - Returns interpolated IV at target time
    - Implements interpolate_iv_term_structure(target_date, expiry_iv_pairs, reference_date) -> float
      - High-level function combining bracketing and variance interpolation
      - Handles exact matches (returns exact IV)
      - Handles target before/after all expiries (uses nearest with warning)
      - Handles single expiry (uses that expiry with warning)
      - Performs variance interpolation between two bracketing expiries
      - Computes time-to-expiry in years (365-day convention)
      - Validates target is after reference date
      - Gracefully handles edge cases with warnings
    - Implements compute_time_to_expiry(expiry_date, reference_date) -> float
      - Converts date difference to years (days / 365.0)
      - Uses today as default reference date
      - Validates expiry is after reference date
    - Custom exception: TermStructureError for clear error handling
    - Robust handling of edge cases:
      - Exact matches, bracketing, extrapolation
      - Single expiry, empty expiries
      - Reference date at or after expiries
      - Non-positive times or IVs
      - Reversed time ordering
  - Created comprehensive test suite (tests/test_term_structure.py)
    - 39 test cases covering all functions and edge cases
    - Test find_bracketing_expiries: 9 tests
      - Exact match, between two, before/after all
      - Empty list, single expiry (before/after/exact)
      - Unsorted input handling
    - Test interpolate_variance: 13 tests
      - Basic interpolation, at endpoints
      - Increasing and decreasing term structures
      - Error cases: negative/zero times, negative/zero IVs
      - Error cases: reversed times, target outside range
    - Test interpolate_iv_term_structure: 10 tests
      - Exact match, interpolation between two
      - Before/after all expiries (with warnings)
      - Single expiry (with warning)
      - Empty pairs, negative IV (errors)
      - Target before reference (with warning)
      - Default reference date, expiry at reference date
    - Test compute_time_to_expiry: 7 tests
      - Basic calculation, one year, one month
      - Default reference date, very short/long expiry
      - Error cases: expiry in past or same as reference
    - All 39 tests passing
  - Full test suite status: 141 tests passing (102 existing + 39 new)
    - 10 Gamma client tests
    - 15 CLOB client tests
    - 19 FRED client tests
    - 26 yfinance client tests
    - 32 IV extraction tests
    - 39 term structure tests

Previous iterations:
- Task 4.1: Implement IV extraction (polyarb/vol/iv_extract.py)
  - Created IV extraction module for extracting implied volatility from option chains
    - Implements extract_strike_region_iv(chain_df, strike_level, window_pct) -> float
      - Filters strikes within moneyness window (default ±5%)
      - Drops strikes with missing IV values
      - Interpolates IV at exact strike using log-moneyness interpolation
      - Auto-expands window to ±20% if initial window too narrow
      - Falls back to nearest strike if only one available
      - Handles edge cases: target below/above all strikes (uses nearest)
      - Validates inputs: positive strike, valid window percentage
      - Warns on data quality issues: sparse strikes, high IV (>500%)
    - Implements compute_sensitivity_ivs(base_iv) -> dict
      - Generates sensitivity set: base, ±2%, ±3%
      - Clips minimum IV at 0.01 (1%) to avoid negative values
      - Returns dict with keys: 'base', 'minus_3', 'minus_2', 'plus_2', 'plus_3'
    - Implements get_average_iv_from_region(chain_df, strike_level, window_pct) -> Optional[float]
      - Fallback method: simple average IV in strike region
      - Returns None if insufficient data or invalid results
    - Custom exception: IVExtractionError for clear error handling
    - Robust handling of edge cases:
      - Empty chains, missing columns
      - No strikes in window (auto-expand)
      - Single strike available (use directly)
      - Missing IV data (drop and warn)
      - Target outside strike range (nearest neighbor)
      - Very high/low IVs (validate and warn)
  - Created comprehensive test suite (tests/test_iv_extract.py)
    - 32 test cases covering all functions and edge cases
    - Test extract_strike_region_iv: 18 tests
      - Exact match, interpolation between strikes
      - Various window sizes (narrow, default, wide)
      - Missing IVs, single strike, sparse data
      - Below/above all strikes (boundary cases)
      - Auto-expansion of window when too narrow
      - Error cases: empty chain, missing columns, invalid inputs
      - Warning cases: high IV, limited strikes
      - Log-moneyness interpolation correctness (U-shaped smile)
    - Test compute_sensitivity_ivs: 6 tests
      - Basic sensitivity computation
      - Low IV clipping (minimum 0.01)
      - High IV values
      - Error cases: zero/negative IV
      - All expected keys present
    - Test get_average_iv_from_region: 8 tests
      - Average calculation in region
      - Missing IVs excluded from average
      - Empty chain, no strikes in window
      - Single strike, all missing IVs
      - Negative/zero IV handling
    - All 32 tests passing
  - Full test suite status: 102 tests passing (70 existing + 32 new)
    - 10 Gamma client tests
    - 15 CLOB client tests
    - 19 FRED client tests
    - 26 yfinance client tests
    - 32 IV extraction tests

Previous iterations:
- Task 3.4: Implement yfinance wrapper (polyarb/clients/yfinance_md.py)
  - Created YFMarketData class for market data fetching via yfinance
    - Provides spot prices, option chains, and implied volatility data
    - Implements get_spot(ticker) -> float: Fetch current spot price (S0)
      - Tries multiple price fields in order: currentPrice, regularMarketPrice, previousClose
      - Falls back to history API if info fields unavailable
      - Properly handles zero/negative prices (explicit None checks to avoid falsy value issues)
      - Clear error messages for invalid tickers
    - Implements get_option_expiries(ticker) -> list[date]: Fetch available option expiries
      - Returns sorted list of expiration dates
      - Parses yfinance date strings to Python date objects
      - Handles invalid date formats with warnings
      - Clear error for tickers without listed options
    - Implements get_chain(ticker, expiry) -> (calls_df, puts_df): Fetch option chain
      - Returns tuple of calls and puts DataFrames with normalized columns
      - Normalizes impliedVolatility to decimal form (0.25 not 25)
      - Handles percentage-form IV (>1.0) by converting to decimal
      - Drops rows with missing IV and warns user
      - Verifies expiry is available before fetching
      - Clear error if all IV data is missing
    - Implements get_dividend_yield(ticker) -> Optional[float]: Fetch dividend yield
      - Returns annual yield in decimal form (0.02 for 2%)
      - Tries dividendYield field, then computes from dividendRate/price
      - Returns None for tickers without dividend data (e.g., crypto)
      - Non-critical: returns None on errors rather than raising
    - All methods handle missing data gracefully with clear warnings
    - Robust error handling with custom YFinanceClientError exception
  - Created comprehensive test suite (tests/test_yfinance_md.py)
    - 26 test cases covering all client methods
    - Mock yfinance.Ticker for isolated unit testing
    - Test get_spot: 8 tests (various price fields, fallbacks, zero/negative, errors)
    - Test get_option_expiries: 6 tests (parsing, sorting, invalid formats, no options)
    - Test get_chain: 7 tests (IV normalization, missing IV, percentage conversion, empty chains)
    - Test get_dividend_yield: 5 tests (field sources, computation, unavailable data, errors)
    - Test edge cases: zero prices, invalid tickers, missing IV, percentage conversions
    - All 26 tests passing
  - Full test suite status: 70 tests passing (10 Gamma + 15 CLOB + 19 FRED + 26 yfinance)

- Task 3.3: Implement FRED client (polyarb/clients/fred.py)
  - Created FredClient class for FRED (Federal Reserve Economic Data) API integration
    - Base URL: https://api.stlouisfed.org/fred
    - Implements get_latest_observation(series_id) -> (value, date): Fetch latest rate observation
      - Handles FRED's missing value indicator "." gracefully
      - Returns both the rate value and the observation date
      - Validates numeric values and date formats
    - Implements get_series_info(series_id) -> dict: Fetch series metadata
      - Returns title, units, frequency, and other metadata
      - Useful for displaying rate information to users
    - Implements search_series(query, limit) -> list[dict]: Search for series by keyword
      - Enables discovery of appropriate rate series
      - Supports the optional 'rates' command functionality
    - API key management:
      - Accepts explicit api_key parameter OR reads from FRED_API_KEY env var
      - Raises clear error if API key not provided
      - Key is included in all requests as query parameter
    - Robust error handling with custom FredClientError exception
      - Distinguishes between invalid series IDs (400) and other HTTP errors
      - Handles network errors, missing data, and invalid formats
    - Configurable timeout (default 30 seconds)
  - Created comprehensive test suite (tests/test_fred_client.py)
    - 19 test cases covering all client methods
    - Mock httpx.Client for isolated unit testing
    - Test edge cases: missing API key, invalid series IDs, missing values (".")
    - Test error handling: HTTP 400/404/500, network errors, malformed data
    - Test environment variable loading
    - All 19 tests passing
  - Full test suite status: 44 tests passing (10 Gamma + 15 CLOB + 19 FRED)

- Task 3.2: Implement Polymarket CLOB client (polyarb/clients/polymarket_clob.py)
  - Created ClobClient class for Polymarket CLOB API integration
    - Base URL: https://clob.polymarket.com
    - Implements get_price(token_id, side) -> TokenPrice: Fetch best price for a token
      - Supports BUY/SELL sides for Yes/No token pricing
      - Handles multiple response field formats (price, mid, best_price)
      - Validates prices are in [0, 1] range
    - Implements get_book(token_id) -> OrderBook: Fetch full order book
      - Parses both list [price, size] and dict {"price": x, "size": y} formats
      - Automatically sorts bids descending and asks ascending
      - Computes best_bid, best_ask, and mid_price properties
      - Handles timestamp parsing (Unix epoch and ISO formats)
    - Implements get_yes_price(token_id) -> float: Convenience method for Yes price
      - Tries order book best ask first (most accurate)
      - Falls back to /price endpoint if book unavailable
    - Robust error handling with custom ClobClientError exception
    - Timezone-aware datetime handling (fixed deprecation warnings)
  - Created comprehensive test suite (tests/test_clob_client.py)
    - 15 test cases covering all client methods
    - Mock httpx.Client for isolated unit testing
    - Test edge cases: 404 errors, missing fields, invalid ranges, empty books
    - Test both list and dict response formats
    - Test unsorted input data handling
    - Test fallback logic for get_yes_price
    - All 15 tests passing with no warnings
  - Full test suite status: 25 tests passing (10 Gamma + 15 CLOB)
