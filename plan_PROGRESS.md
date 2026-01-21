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

- [x] 5.3: Add verdict logic
  - compute_verdict(poly_price, fair_pv, abs_tol, pct_tol) -> str
  - "Fair" if abs_diff <= abs_tol OR pct_diff <= pct_tol
  - "Cheap" if poly < fair beyond tolerance
  - "Expensive" if poly > fair beyond tolerance
  - NOTE: Already implemented in task 5.1 (polyarb/pricing/digital_bs.py)

### Phase 6: Reporting
- [x] 6.1: Implement markdown report generator (polyarb/report/markdown_report.py)
  - render(ctx: ReportContext) -> str
  - Section A: Input summary table (ticker, spot, strike, expiry, rates, vol, etc.)
  - Section B: Model choice explanation (touch vs terminal, why)
  - Section C: Full derivation with formulas and intermediate values
  - Section D: Fair vs Polymarket comparison table with verdict
  - Section E: Professional one-paragraph conclusion
  - Section F: Layman explanation (no jargon)
  - Section G: One-liner takeaway with key numbers

### Phase 7: CLI Implementation
- [x] 7.1: Implement CLI command structure (polyarb/cli.py)
  - Main click group with subcommands
  - Setup logging/error handling
  - Environment variable loading (FRED_API_KEY)

- [x] 7.2: Implement `markets` command
  - Options: --search, --slug, --limit
  - Call GammaClient.search_markets()
  - Output table: id, title, endDate

- [x] 7.3: Implement `analyze` command - input handling
  - Core inputs: MARKET_ID (required), --ticker, --event-type, --level, --expiry
  - Price inputs: --yes-price, --no-price (optional, fetch from CLOB if not provided)
  - Rate inputs: --rate OR --fred-series-id
  - Div yield: --div-yield
  - Vol inputs: --iv-mode [auto|manual], --iv, --iv-strike-window
  - Output: --output PATH, --format (v1: markdown only)
  - Verdict thresholds: --abs-tol, --pct-tol
  - Add click prompts for missing required inputs

- [x] 7.4: Implement `analyze` command - orchestration logic
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

- [x] 7.5: Implement `rates` command (optional)
  - Options: --series-id OR --search
  - Fetch and print latest rate value from FRED

- [x] 7.6: Add input validation
  - validate_inputs() function
  - Check: expiry in future, level > 0, IV > 0, yes/no prices in [0,1]
  - Warn if dividend yield not provided (default to 0)
  - Warn if Polymarket expiry differs from user override
  - NOTE: Completed in task 7.3 (validation integrated into analyze command)

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

- [x] 8.4: Write report tests
  - tests/test_report_sections.py
    - Assert all A-G section headers present
    - Check markdown structure validity
    - NOTE: Completed in task 6.1 (report tests written alongside report module)

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
- Task 7.5: Implement `rates` command (optional)
  - Implemented FRED rate fetching and search in polyarb/cli.py (lines 713-767)
    - Two operation modes:
      - `--search`: Search for rate series by keyword (e.g., "treasury bill", "federal funds")
        - Calls FredClient.search_series() with query and limit=10
        - Displays formatted results table with series ID, title, units, frequency
        - Shows 10 matching series with all metadata
      - `--series-id`: Fetch latest observation for specific series (e.g., DGS3MO, DFF)
        - Calls FredClient.get_series_info() for metadata
        - Calls FredClient.get_latest_observation() for latest value and date
        - Displays series title, units, latest value, and observation date
        - Automatically converts percentage to decimal form for convenience
    - Both options can be used together (search first, then specific series)
    - Error handling:
      - Checks for FRED_API_KEY environment variable (exits with helpful message if missing)
      - Validates at least one of --search or --series-id is provided
      - Catches and displays FRED API errors (invalid series, network errors, etc.)
      - Verbose mode shows full traceback for debugging
    - User-friendly output:
      - Clear formatting with series metadata
      - Percentage values shown both as-is and in decimal form
      - Observation dates included for currency
  - Testing:
    - Manually tested with real FRED API:
      - Search for "treasury bill": Returns 10 series (DTB3, DGS3MO, etc.)
      - Fetch DGS3MO (3-month T-bill): Returns 3.67% as of 2026-01-16
      - Fetch DFF (federal funds rate): Returns 3.64% as of 2026-01-19
      - Combined search + fetch: Both operations work together
      - Invalid series ID: Properly caught and reported
      - Missing API key: Clear error message with help URL
    - All 237 existing tests still passing (no regressions)
  - Command now fully functional and ready for use
  - Enables users to discover and fetch risk-free rate data for analysis

- Task 7.6: Add input validation
  - ALREADY COMPLETE (verified in this iteration)
  - All validation logic was implemented in task 7.3
  - Integrated into analyze command handler (polyarb/cli.py lines 323-391)
  - Comprehensive test coverage in tests/test_cli_validation.py (11 tests)
  - See task 7.3 completion notes for full details

Previous iteration:
- Task 7.4: Implement `analyze` command - orchestration logic
  - Implemented full end-to-end analysis pipeline in polyarb/cli.py
    - Outcome mapping: Maps Yes/No outcomes to token IDs
      - Binary markets (2 outcomes): Automatically detects Yes/No or uses first/second outcomes
      - Multi-outcome markets (>2 outcomes): Prompts user to select outcome (by name or number)
      - Validates outcome exists in market.clob_token_ids
    - Polymarket price fetching:
      - Fetches Yes price from CLOB using get_yes_price() if not provided
      - Optionally fetches No price for binary markets
      - Uses provided prices if --yes-price/--no-price flags given
    - Market data fetching (yfinance):
      - Fetches spot price for ticker using YFMarketData.get_spot()
      - Gets available option expiries
      - Fetches option chains (calls/puts) for each expiry
      - Chooses appropriate chain based on event type (calls for above/touch-up, puts for below/touch-down)
    - Risk-free rate:
      - Uses provided --rate if given
      - Otherwise fetches from FRED using --fred-series-id
      - Converts FRED percentage to decimal (divides by 100)
      - Logs rate source in report
    - IV selection and interpolation:
      - Manual mode: Uses provided --iv value directly
      - Auto mode:
        - Extracts strike-region IV from each expiry using extract_strike_region_iv()
        - Filters strikes within moneyness window (default ±5%)
        - Interpolates IV across term structure to target expiry using interpolate_iv_term_structure()
        - Logs IV for each expiry and final interpolated value
    - Pricing model selection:
      - Touch event: Uses touch_price_with_sensitivity() from touch_barrier module
      - Above/below events: Uses digital_price_with_sensitivity() from digital_bs module
      - Computes time to expiry in years using compute_time_to_expiry()
      - Runs sensitivity analysis (±2%, ±3% vol shifts)
    - Verdict computation:
      - Uses compute_verdict() to compare Polymarket price vs fair PV
      - Applies absolute and percentage tolerances (default: 0.01, 5%)
      - Returns "Fair", "Cheap", or "Expensive"
      - Computes absolute and percentage mispricing
    - Report generation:
      - Builds AnalysisInputs, AnalysisResults, and ReportContext models
      - Computes additional values: log_moneyness, variance_term
      - Generates complete A-G markdown report using render()
      - Writes to file if --output provided, else prints to stdout
    - Error handling:
      - Try-catch wraps entire orchestration
      - Detailed error messages for each step
      - Verbose mode shows full traceback
    - Logging:
      - Progress logged at each major step
      - Shows fetched prices, IV values, probabilities, verdict
      - Clear indication when analysis is complete
  - Fixed datetime/date comparison bug:
    - market.end_date is datetime but compared with date.today()
    - Added conversion: market.end_date.date() for comparisons
    - Fixed both expiry selection and warning logic
  - Updated CLI validation tests (tests/test_cli_validation.py):
    - Created mock_orchestration_dependencies() context manager
      - Mocks ClobClient, YFMarketData, FredClient
      - Mocks pricing functions (touch_price_with_sensitivity, digital_price_with_sensitivity)
      - Mocks IV extraction and interpolation functions
      - Returns realistic test data (spot=$95k, IV=0.45, prob=0.65, pv=0.63)
    - Updated 5 failing tests to use mock orchestration
      - test_analyze_validation_valid_inputs: Now expects analysis completion
      - test_analyze_warns_both_rate_and_fred: Checks stderr for warning
      - test_analyze_warns_unusual_rate: Checks combined output
      - test_analyze_uses_market_end_date: Checks date formatting
      - test_analyze_warns_expiry_override: Checks combined output
    - All 11 validation tests now passing with full orchestration
  - Full test suite status: 237 tests passing (all existing tests maintained)
  - Orchestration complete: analyze command now produces full A-G reports!

Previous iteration:
- Task 7.3: Implement `analyze` command - input handling
  - Implemented comprehensive input validation and prompting in polyarb/cli.py
    - Fetches market metadata from Gamma API to get default expiry (end_date)
    - Prompts for missing required inputs: ticker, event-type, level
    - Uses market end_date as default expiry if not provided by user
    - Validates all inputs before proceeding to orchestration:
      - Expiry must be in the future (checked against today's date)
      - Level/strike must be positive
      - Yes/No prices must be in [0, 1] range if provided
      - IV must be positive if provided
      - Manual IV mode requires --iv parameter
      - Must have either --rate or --fred-series-id for risk-free rate
      - IV strike window must be positive
      - Tolerances (abs_tol, pct_tol) must be non-negative
    - Issues warnings for edge cases:
      - Both --rate and --fred-series-id provided (uses --rate, warns)
      - Unusual rate values outside [-10%, 30%]
      - Unusual dividend yield outside [0%, 20%]
      - User-provided expiry differs from market end date
      - Default dividend yield of 0% if not provided
    - Comprehensive error reporting: collects all validation errors and displays them together
    - Clear, user-friendly error messages with actual values shown
  - Created test suite for CLI validation (tests/test_cli_validation.py)
    - 11 test cases covering all validation scenarios
    - Tests negative level validation
    - Tests expiry in past validation
    - Tests yes/no price range validation
    - Tests manual IV mode validation
    - Tests missing rate validation
    - Tests negative IV validation
    - Tests valid inputs pass through
    - Tests warning for both rate sources
    - Tests warning for unusual rates
    - Tests market end date usage
    - Tests expiry override warning
    - All 11 tests passing
  - Full test suite status: 237 tests passing (226 existing + 11 new CLI validation tests)
  - Input handling complete, ready for task 7.4 (orchestration logic)

Previous iteration:
- Task 7.1: CLI command structure (already complete - marked as done)
- Task 7.2: Implement `markets` command
  - Implemented markets listing/search functionality in polyarb/cli.py
  - Calls GammaClient.search_markets() with query and limit parameters
  - Displays table with ID, End Date, and Title columns
  - Truncates long titles for better display
  - Handles empty results gracefully
  - Shows count of markets returned
  - Fixed GammaClient to allow markets without CLOB token IDs in search results
    - Changed requirement from mandatory to optional for search endpoints
    - Only get_market() endpoint requires full token mapping
  - Tested successfully with "BTC" search and without search filter

Previous iteration:
- Task 6.1: Implement markdown report generator (polyarb/report/markdown_report.py)
- Task 8.4: Write report tests (tests/test_report_sections.py) - completed alongside task 6.1
  - Created markdown report generator producing comprehensive A-G analysis sections
    - Implements render(ctx: ReportContext) -> str: Main function to generate complete report
      - Section A: Input summary table with all parameters
        - Displays ticker, spot price, event type, strike/barrier, expiry, T, r, q, σ
        - Shows Polymarket Yes/No prices
        - Documents data sources for IV and rate
        - Formatted markdown table with clear labels and units
      - Section B: Model selection explanation
        - Names the selected model (Digital Option or Touch Barrier)
        - Provides rationale for model choice based on event type
        - Default rationale generated for each event type (touch/above/below)
        - Explains path-dependence vs terminal-settle distinction
      - Section C: Mathematical derivation
        - Full step-by-step derivation with formulas
        - For digital options:
          - Risk-neutral drift μ = r - q - 0.5σ²
          - d₂ calculation with explicit values
          - Probability N(d₂) or N(-d₂) for above/below
          - Present value with discounting
        - For touch barriers:
          - Risk-neutral drift μ = r - q - 0.5σ²
          - Log-distance a = ln(B/S₀)
          - First-passage probability using reflection principle
          - Two-term formula with drift adjustment
          - Present value with discounting
        - Sensitivity analysis table showing IV shifts and resulting prob/PV
        - All intermediate values shown with actual numbers
      - Section D: Fair vs Polymarket comparison
        - Comparison table with model PV, Polymarket price, mispricing (abs and %)
        - Verdict with emoji indicators (📉 Cheap, ✅ Fair, 📈 Expensive)
        - Detailed interpretation explaining the verdict
        - References tolerance thresholds used
      - Section E: Professional conclusion
        - One-paragraph technical summary
        - Mentions model assumptions, IV source, rate
        - States event probability and fair value
        - Provides verdict and investment implication
        - Includes caveats about model limitations
      - Section F: Layman explanation
        - No-jargon explanation suitable for non-experts
        - Explains what the bet is about
        - States current Polymarket price as implied probability
        - Explains model fair value and its source
        - Translates verdict into plain language
        - Warns about model assumptions and real-world differences
      - Section G: One-liner takeaway
        - Single sentence summary with key numbers
        - States Polymarket price, model PV, implied probability, verdict
        - Includes emoji for quick visual cue
      - Helper functions for each section
        - _render_header: Market title and metadata
        - _render_section_a_inputs: Input table
        - _render_section_b_model_choice: Model explanation
        - _render_section_c_derivation: Full math (separate for digital vs touch)
        - _render_digital_derivation: Digital option derivation
        - _render_touch_derivation: Touch barrier derivation
        - _render_sensitivity_table: Volatility sensitivity table
        - _render_section_d_comparison: Comparison and verdict
        - _render_verdict_explanation: Verdict interpretation
        - _render_section_e_conclusion: Professional conclusion
        - _render_section_f_layman: Layman explanation
        - _render_section_g_takeaway: One-liner takeaway
      - Default text generation
        - _generate_default_rationale: Model selection rationale by event type
        - _generate_default_conclusion: Professional conclusion text
        - _generate_default_layman: Layman explanation text
        - _generate_default_takeaway: One-liner takeaway text
      - Custom text support
        - Allows overriding conclusion_text, layman_text, takeaway in ReportContext
        - Falls back to generated defaults if custom text not provided
      - Formatting
        - Consistent number formatting: prices with $, percentages with %
        - Large numbers with comma separators
        - Dates in YYYY-MM-DD format
        - Proper markdown structure with headers, tables, code blocks
  - Created comprehensive test suite (tests/test_report_sections.py)
    - 29 test cases covering all report functions and sections
    - Test render function: 1 test
      - Returns non-empty string
    - Test section presence: 1 test
      - All A-G section headers present in report
    - Test Section A: 2 tests
      - Contains all key input parameters
      - Data sources documented
    - Test Section B: 1 test
      - Model choice explained for digital and touch
    - Test Section C: 3 tests
      - Digital above derivation complete
      - Digital below derivation complete
      - Touch barrier derivation complete
    - Test Section D: 3 tests
      - Comparison table for fair verdict
      - Comparison table for cheap verdict
      - Comparison table for expensive verdict
    - Test Section E: 1 test
      - Professional conclusion present with technical language
    - Test Section F: 1 test
      - Layman explanation present with plain language
    - Test Section G: 1 test
      - One-sentence takeaway with key numbers
    - Test sensitivity table: 2 tests
      - Sensitivity table included when data available
      - Graceful handling when sensitivity data missing
    - Test custom text: 3 tests
      - Custom conclusion text used if provided
      - Custom layman text used if provided
      - Custom takeaway text used if provided
    - Test event descriptions: 3 tests
      - Touch event descriptions correct
      - Above event descriptions correct
      - Below event descriptions correct
    - Test markdown structure: 1 test
      - Valid markdown with proper headers and tables
    - Test formatting: 2 tests
      - Numeric formatting with commas
      - Percentage formatting with decimals
    - Test data sources: 1 test
      - Data sources section in Section A
    - Test all combinations: 2 tests
      - All event types render without errors
      - All verdicts render without errors
    - Test edge cases: 2 tests
      - Market title in header
      - Warnings section if present (documented for future)
    - All 29 tests passing
  - Full test suite status: 226 tests passing (197 existing + 29 new)
    - 10 Gamma client tests
    - 15 CLOB client tests
    - 19 FRED client tests
    - 26 yfinance client tests
    - 32 IV extraction tests
    - 39 term structure tests
    - 30 digital pricing tests
    - 26 touch barrier pricing tests
    - 29 report generation tests

Previous iterations:
- Task 5.2: Implement touch barrier pricing (polyarb/pricing/touch_barrier.py)
- Task 5.3: Verified verdict logic already implemented (discovered during task 5.2)
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
