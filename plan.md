# Project: Polymarket Options-Implied Fair Value CLI

## Goal
Turn the provided “quant analyst script” into a **working Python CLI** that:
1) pulls Polymarket prices/metadata + market data (spot/options/rates),
2) computes an **options-implied (risk-neutral) fair value** for the Polymarket “Yes” token (digital or touch),
3) outputs the required **A–G analysis sections** in **Markdown**.

---

## Requirements

### Hard requirements (must-haves)
- Use **`uv` only** for Python/project install + running (no pip/poetry/conda).
- CLI built with **`click`**.
- Market data via **`yfinance`** (spot + option chains + implied vol fields).
- Use the provided APIs:
  - Polymarket Gamma: `/markets`, `/markets/{id}`
  - Polymarket CLOB: `/price`, `/prices`, `/book`
  - FRED: `/fred/series/search`, `/fred/series`, `/fred/series/observations`
- Output must include sections **A–G** exactly (Input table, model choice, full derivation, fair vs poly table, pro conclusion, layman explanation, one-sentence takeaway).
- Must distinguish **touch** vs **settle at expiry** events.
- Must do **risk-neutral pricing** + **discounting** (risk-free rate).
- Must use **appropriate strike-region IV** (not “ATM only”), and do **term-structure interpolation** if Polymarket expiry doesn’t match listed option expiries.
- If inputs are missing, CLI should **prompt** for them.

### Nice-to-haves (phase 2)
- Slippage / size-aware entry price using CLOB `/book`.
- Bulk scanning multiple markets (Gamma list + CLOB bulk prices) to surface “most mispriced”.
- `--output json` in addition to markdown.

### Non-goals (explicitly out of scope for v1)
- Full multi-barrier / complex path-dependent structures beyond “single touch” and “terminal above/below”.
- Exotic vol surface modeling (SABR, local vol, etc.). Keep to pragmatic interpolation.

---

## Context / Assumptions
- Polymarket “Yes” token is treated as a $1 payout claim if the event happens at/over the defined condition.
- We compare **Polymarket tradable price** (best effective entry) vs **model fair PV**.
- Risk-free rate source:
  - Prefer user-provided `--rate` OR FRED `--fred-series-id` + `FRED_API_KEY`.
- Dividend yield:
  - Prefer user-provided `--div-yield` OR infer from yfinance if available; fallback 0 with a warning.

---

# Plan (Template-Driven)

## [Setup]: Initialize repo & tooling

## Goal
Create a clean `src/` layout Python package with a click CLI, managed and run exclusively with `uv`.

## Requirements
- `uv init` project with `pyproject.toml`
- Add runtime deps: `click`, `yfinance`, `httpx` (or `requests`), `numpy`, `scipy`
- Add dev deps: `pytest`, `pytest-mock` (and optionally `responses` or `respx` for HTTP mocking)
- Provide `project.scripts` entrypoint: `polyarb = polyarb.cli:main`
- All commands runnable via `uv run ...`

## Context
- Choose `httpx` for simple HTTP calls to Polymarket/FRED (sync client is fine).

### Concrete tasks
- `uv init --name polyarb`
- `uv add click yfinance httpx numpy scipy`
- `uv add --dev pytest pytest-mock`
- Add `README.md` with quickstart using only `uv run ...`

---

## [Architecture]: Define modules & data flow

## Goal
Separate concerns: CLI (I/O) → Data fetching → Vol selection/interpolation → Pricing → Reporting.

## Requirements
- Pure math/pricing functions are testable and do not perform I/O.
- All network calls isolated in `clients/`.
- Reporting produces Markdown with A–G sections.

## Suggested structure

polyarb/
init.py
cli.py
models.py
util/
dates.py
math.py
fmt.py
clients/
polymarket_gamma.py
polymarket_clob.py
fred.py
yfinance_md.py
vol/
iv_extract.py
term_structure.py
pricing/
digital_bs.py
touch_barrier.py
report/
markdown_report.py
tests/
test_pricing_digital.py
test_pricing_touch.py
test_iv_interpolation.py
test_report_sections.py


---

## [CLI UX]: Commands, options, prompting

## Goal
Provide a human-friendly CLI that can run fully from flags OR interactively prompt for missing inputs.

## Requirements
- `click`-based CLI with subcommands.
- Prompts for missing required inputs.
- Clear errors + warnings (e.g., missing dividend yield defaults to 0).

## Proposed commands
### 1) `polyarb markets`
List/search markets via Gamma.
- Options:
  - `--search TEXT` (keyword)
  - `--slug TEXT` (exact match if supported)
  - `--limit N`
- Output: small table (id, title/description snippet, endDate)

### 2) `polyarb analyze MARKET_ID`
Run full A–G analysis.
- Core inputs:
  - `--ticker TICKER` (yfinance ticker, e.g. `SPY`, `BTC-USD`)
  - `--event-type [touch|above|below]`
  - `--level FLOAT` (barrier/strike)
  - `--expiry YYYY-MM-DD` (Polymarket expiration if you want override; otherwise read from Gamma)
- Prices:
  - default: fetch “Yes/No” via CLOB using Gamma token IDs
  - `--yes-price` / `--no-price` override (optional)
- Rates/dividends:
  - `--rate FLOAT` OR `--fred-series-id TEXT` (+ `FRED_API_KEY`)
  - `--div-yield FLOAT`
- Vol selection:
  - `--iv-mode [auto|manual]`
  - `--iv FLOAT` (manual)
  - `--iv-strike-window FLOAT` (auto: strikes near level, e.g. ±5% moneyness)
- Slippage (phase 2):
  - `--size FLOAT` (estimate effective entry using order book)
- Output:
  - `--output PATH` (write markdown to file)
  - `--format [markdown|text|json]` (v1: markdown only)

### 3) `polyarb rates` (optional)
Fetch and print latest rate from FRED series.

---

## [Polymarket Integration]: Gamma + CLOB

## Goal
Resolve a market → outcome token IDs → tradable “Yes/No” prices (and optionally order book).

## Requirements
- Gamma `/markets/{id}` used to fetch:
  - description, outcomes, `endDate`, `clobTokenIds` (mapping outcome→token_id)
- CLOB `/price` used to fetch best quote(s) for token
- Optional: `/book` to compute effective entry for a given size

## Concrete tasks
- Implement `GammaClient.get_market(id)` returning a normalized `Market` model.
- Implement `ClobClient.get_price(token_id, side)`:
  - Add a “verify semantics” step in dev/testing (BUY vs SELL meaning).
- Map “Yes/No” labels:
  - If market has multiple outcomes, require `--outcome-label` or prompt.
- Provide “best entry price for buying Yes” definition:
  - v1: use best ask from `/book` if available; else use `/price` with the correct side once confirmed.

---

## [Market Data]: yfinance spot + option chain

## Goal
Pull spot price, option chain(s), and implied vols needed for digital/touch modeling.

## Requirements
- Spot:
  - Use yfinance recent close or live-ish price (document what you choose).
- Options:
  - Pull expiries around Polymarket expiry.
  - Pull calls/puts chain for those expiries.
  - Extract IV for strikes near the barrier/strike region.

## Concrete tasks
- `YFMarketData.get_spot(ticker)` → `S0`
- `YFMarketData.get_option_expiries(ticker)` → list of dates
- `YFMarketData.get_chain(ticker, expiry)` → calls/puts DataFrames
- Normalization:
  - Ensure IV is in decimals (0.25 not 25)
  - Handle missing IVs (drop, interpolate, or fallback with warning)

---

## [IV Selection + Interpolation]: “right strike region” + term structure

## Goal
Compute the implied vol σ to use at the target horizon and strike region.

## Requirements
- Strike-region vol:
  - Choose strikes closest to `level` (digital strike or touch barrier)
  - Prefer interpolation by **log-moneyness** around `K=level`
- Term structure:
  - If Polymarket expiry T doesn’t match an option expiry, interpolate in **total variance**:
    - `w(T) = σ(T)^2 * T` linearly between bracketing expiries

## Concrete tasks
1) **Find bracketing expiries** around `expiry`:
   - if exact match: use it
   - else pick nearest below/above; if only one side exists, use nearest with warning
2) For each expiry, compute strike-region σ:
   - pick N strikes around level (e.g., nearest 2 above + 2 below)
   - interpolate IV at level
3) Term interpolate to target T via total variance
4) Provide sensitivity set:
   - σ_base, σ_base ± 0.02, σ_base ± 0.03 (clip at >0)

---

## [Pricing Engine]: digital (terminal) + touch (barrier hit)

## Goal
Compute risk-neutral event probability and PV fair price for:
- settle above/below at expiry (digital)
- touch before expiry (barrier hit)

## Requirements
- Use risk-neutral drift:
  - `μ = r - q - 0.5 σ^2`
- Use correct probability formulas:
  - Terminal: Black–Scholes tail probability
  - Touch: first-passage probability for log-GBM (reflection principle form)
- Discount PV:
  - `PV = exp(-rT) * P(event)` (for $1 payout at expiry)

## Concrete tasks
### Digital settle-at-expiry
- `d2 = (ln(S0/K) + (r - q - 0.5σ^2)T) / (σ√T)`
- `P(above) = N(d2)`, `P(below) = N(-d2)`
- `PV = e^{-rT} * P`

### Touch event
Let `a = ln(B/S0)` (upper barrier if B>S0; lower barrier if B<S0).
Use log-process `X_t = μ t + σ W_t`.
Compute `P(hit by T)` using the standard drifted reflection form (implement carefully + unit test against known limits):
- Ensure:
  - driftless case matches `2 * (1 - N(a/(σ√T)))` for upper barrier
  - probabilities clamp to [0,1]
- `PV = e^{-rT} * P_hit`

### Verdict rule
- Default tolerance:
  - `abs_diff <= 0.01` OR `pct_diff <= 5%` → “Fair”
  - below fair by more than tolerance → “Cheap”
  - above fair by more than tolerance → “Expensive”
(Expose as flags: `--abs-tol`, `--pct-tol`)

---

## [Reporting]: Produce the A–G markdown sections

## Goal
Generate a single Markdown report that follows the script exactly, with both technical and layman explanations.

## Requirements
- Sections A–G present in order.
- A: Input summary table
- B: Model choice explanation (touch vs terminal)
- C: Full derivation with formulas + intermediate values
- D: Fair vs Polymarket comparison table + verdict
- E: One-paragraph professional conclusion
- F: Layman explanation (no jargon)
- G: Final one-liner takeaway with the key numbers

## Concrete tasks
- Create a `ReportContext` object containing:
  - inputs, derived values, probabilities, PV, poly prices, mispricing, sensitivity results
- Implement `markdown_report.render(ctx)` returning a markdown string
- Add `tests/test_report_sections.py` that asserts all headings A–G exist

---

## [Input Handling]: Prompting + validation

## Goal
Make the CLI resilient: if something is missing, prompt; if inconsistent, warn.

## Requirements
- If user didn’t provide:
  - event type, level, ticker → prompt
- Validate:
  - expiry is in the future
  - level is positive
  - IV is positive
  - yes/no prices in [0,1]
- If Polymarket expiry differs from Gamma `endDate` and user provided override, print both.

## Concrete tasks
- Central `validate_inputs()` called before analysis
- Use click prompts with defaults:
  - `click.option(..., prompt=True)` selectively when missing

---

## [Testing]: Unit + light integration

## Goal
Confidence that math + IV interpolation + report formatting is correct.

## Requirements
- Unit tests for:
  - digital probability edge cases
  - touch probability limits (μ=0, very short T, very high vol, etc.)
  - term-structure interpolation correctness
- Mock HTTP for Polymarket/FRED clients

## Concrete tasks
- Use `pytest`
- Use `pytest-mock` to patch `httpx.get`
- Include a small set of saved JSON fixtures for Gamma/CLOB responses

---

## [Packaging & Runbook]: Docs + commands

## Goal
Anyone can clone and run with `uv` only.

## Requirements
- README includes:
  - setup: `uv sync` (or just `uv run ...`)
  - examples for listing + analyzing
  - env var for FRED key
- Provide example commands:
  - `uv run polyarb markets --search "BTC"`
  - `uv run polyarb analyze 12345 --ticker BTC-USD --event-type touch --level 80000`

## Concrete tasks
- Add `README.md` “Quickstart”
- Add “Troubleshooting”:
  - yfinance missing IV fields
  - Polymarket token mapping oddities
  - FRED key not set

---

# Milestones

## Milestone 1 (MVP): Single-market analysis works end-to-end
- `markets` lists markets
- `analyze` pulls Gamma + CLOB + yfinance spot/options + (rate)
- Produces Markdown A–G output
- Unit tests for pricing + IV interpolation

## Milestone 2: Better realism
- Size-aware entry price via `/book`
- Better outcome mapping + multi-outcome prompt
- JSON output option + saving report to file

## Milestone 3: Scanner mode (arbitrage surfacing)
- Bulk fetch market prices with `/prices`
- Rank by absolute/pct mispricing
- Output top-N opportunities

---

# Acceptance Criteria Checklist (v1)
- [ ] Running `uv run polyarb analyze MARKET_ID ...` prints a complete Markdown report with A–G sections.
- [ ] Touch events use barrier-hit math; settle events use terminal digital probability.
- [ ] IV is chosen from strike region near the barrier/strike and interpolated across expiries when needed.
- [ ] Risk-free rate is applied via discounting; can be supplied directly or fetched from FRED.
- [ ] Missing inputs trigger click prompts (no silent assumptions).
- [ ] Unit tests pass via `uv run pytest`.

