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
- [ ] 2.1: Define core data models in polyarb/models.py
  - Market model (id, title, endDate, clobTokenIds, outcomes)
  - TokenPrice model (token_id, side, price)
  - AnalysisInputs model (ticker, event_type, level, expiry, etc.)
  - AnalysisResults model (probability, pv, verdict, etc.)
  - ReportContext model (all data for A-G sections)

- [ ] 2.2: Implement utility modules
  - polyarb/util/dates.py: date parsing, validation, time-to-expiry calculation
  - polyarb/util/math.py: basic math helpers (log, exp, clamp)
  - polyarb/util/fmt.py: number formatting for tables/reports

### Phase 3: API Clients
- [ ] 3.1: Implement Polymarket Gamma client (polyarb/clients/polymarket_gamma.py)
  - GammaClient class with httpx client
  - get_market(market_id) -> Market model
  - search_markets(query, limit) -> list[Market]
  - Handle API errors gracefully

- [ ] 3.2: Implement Polymarket CLOB client (polyarb/clients/polymarket_clob.py)
  - ClobClient class with httpx client
  - get_price(token_id, side) -> TokenPrice
  - get_book(token_id) -> order book data (for phase 2)
  - Map "Yes/No" to token IDs correctly

- [ ] 3.3: Implement FRED client (polyarb/clients/fred.py)
  - FredClient class with httpx client and API key from env
  - get_series_observations(series_id) -> latest rate value
  - search_series(query) -> list of series (for rates command)
  - Handle missing FRED_API_KEY gracefully

- [ ] 3.4: Implement yfinance wrapper (polyarb/clients/yfinance_md.py)
  - YFMarketData class wrapping yfinance
  - get_spot(ticker) -> float (S0)
  - get_option_expiries(ticker) -> list[date]
  - get_chain(ticker, expiry) -> calls/puts DataFrames with normalized IV
  - Handle missing tickers and missing IV fields with warnings

### Phase 4: Volatility & IV Logic
- [ ] 4.1: Implement IV extraction (polyarb/vol/iv_extract.py)
  - extract_strike_region_iv(chain, strike_level, window_pct) -> float
  - Find strikes around barrier/level (e.g., ±5% moneyness)
  - Interpolate IV at exact strike using log-moneyness
  - Handle missing IVs (drop or warn)

- [ ] 4.2: Implement term structure interpolation (polyarb/vol/term_structure.py)
  - find_bracketing_expiries(target_date, available_expiries) -> (before, after)
  - interpolate_variance(iv1, t1, iv2, t2, target_t) -> target_iv
  - Use total variance: w(T) = σ²T, linear interpolation
  - Handle edge cases (exact match, only one expiry available)

### Phase 5: Pricing Engines
- [ ] 5.1: Implement digital option pricing (polyarb/pricing/digital_bs.py)
  - digital_price(S0, K, T, r, q, sigma, direction) -> (probability, pv)
  - direction: 'above' or 'below'
  - Compute d2 = (ln(S0/K) + (r - q - 0.5σ²)T) / (σ√T)
  - P(above) = N(d2), P(below) = N(-d2)
  - PV = exp(-rT) * P
  - Add sensitivity analysis (vary sigma by ±0.02, ±0.03)

- [ ] 5.2: Implement touch barrier pricing (polyarb/pricing/touch_barrier.py)
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
- Task 1.2: Create package directory structure
  - Created polyarb/ main package directory with __init__.py (version 0.1.0)
  - Created polyarb/util/ with __init__.py and stub files: dates.py, math.py, fmt.py
  - Created polyarb/clients/ with __init__.py
  - Created polyarb/vol/ with __init__.py
  - Created polyarb/pricing/ with __init__.py
  - Created polyarb/report/ with __init__.py
  - Created tests/ directory
  - Verified package can be imported successfully
