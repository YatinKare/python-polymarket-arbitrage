# Investigation Report: Polymarket Arbitrage CLI Issues

## Executive Summary

This investigation identified **critical bugs** in the API client implementations that render the CLI non-functional for its intended purpose. The most severe issues are in the Gamma API client where JSON strings are not being parsed correctly.

---

## Critical Issues (Must Fix)

### 1. **Gamma API: JSON String Parsing Bug**
**Severity: CRITICAL**
**File:** `polyarb/clients/polymarket_gamma.py:168-193`

**Problem:** The Polymarket Gamma API returns `outcomes` and `clobTokenIds` as JSON **strings** (e.g., `'["Yes", "No"]'`), but the code treats them as Python lists, iterating over them character-by-character.

**Evidence:**
```python
# API returns:
outcomes = '["Yes", "No"]'  # STRING, not list
clobTokenIds = '["token1", "token2"]'  # STRING, not list

# Current code does:
outcomes = [str(outcome) for outcome in outcomes_data]  # Iterates over characters!
# Result: ['[', '"', 'Y', 'e', 's', '"', ...]  # WRONG!
```

**Impact:**
- Market outcomes are completely broken (parsed as individual characters)
- CLOB token ID mapping is empty (can't fetch prices)
- The entire `analyze` command fails because token IDs cannot be resolved

**Fix:** Add JSON parsing when the field is a string:
```python
import json

outcomes_data = data.get("outcomes") or []
if isinstance(outcomes_data, str):
    outcomes_data = json.loads(outcomes_data)

clob_token_ids_raw = data.get("clobTokenIds") or []
if isinstance(clob_token_ids_raw, str):
    clob_token_ids_raw = json.loads(clob_token_ids_raw)
```

---

### 2. **Gamma API: Wrong Search Endpoint**
**Severity: HIGH**
**File:** `polyarb/clients/polymarket_gamma.py:64-132`

**Problem:** The `search_markets()` method uses `/markets?query=BTC` but the Gamma API does NOT support a `query` parameter on the `/markets` endpoint. The correct endpoint is `/public-search?q=BTC`.

**Evidence:**
```bash
# Current implementation (WRONG):
GET https://gamma-api.polymarket.com/markets?query=BTC
# Returns: Old markets sorted by ID (ignores query parameter)

# Correct endpoint:
GET https://gamma-api.polymarket.com/public-search?q=BTC
# Returns: Relevant BTC markets
```

**Impact:**
- `polyarb markets --search "BTC"` returns completely unrelated markets (Biden, Airbnb, etc.)
- Search functionality is completely broken

**Fix:**
- Use `/public-search` endpoint with `q` parameter for keyword searches
- The `/public-search` endpoint returns `{events: [...]}` structure with nested markets
- May need to restructure the return type to handle events vs markets

---

### 3. **Gamma API: Markets Endpoint Returns Expired Markets**
**Severity: MEDIUM**
**File:** `polyarb/clients/polymarket_gamma.py:64-132`

**Problem:** The `/markets?active=true&closed=false` filter parameters don't work as expected - the API still returns markets from 2020-2021 that are clearly expired.

**Evidence:**
```bash
# Request with active=true filter:
GET https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=5

# Returns markets from 2020:
- "Will Joe Biden get Coronavirus before the election?" (2020-11-04)
- "Will Airbnb begin publicly trading before Jan 1, 2021?"
```

**Impact:**
- Users see irrelevant expired markets
- No way to list only truly active markets via the current implementation

**Fix:**
- Use the `/events` endpoint instead which has better filtering
- Or filter client-side by `endDate > today()`
- Document the correct API behavior

---

## Medium Issues (Should Fix)

### 4. **CLOB API: 404 for Markets Without Active Orderbooks**
**Severity: MEDIUM**
**File:** `polyarb/clients/polymarket_clob.py:101-128`

**Problem:** The CLOB `/book` and `/price` endpoints return 404 with "No orderbook exists for the requested token id" for markets without active trading, but the error handling doesn't distinguish this from actual missing tokens.

**Evidence:**
```python
# For inactive markets:
Status: 404
Response: {"error":"No orderbook exists for the requested token id"}
```

**Impact:**
- Users get confusing "Token not found" errors for valid but inactive markets
- No graceful fallback or clear messaging

**Fix:**
- Parse the 404 response body to detect "No orderbook" vs "Invalid token"
- Provide clearer error messages: "Market has no active trading" vs "Invalid token ID"
- Consider returning None or a sentinel value instead of raising for inactive markets

---

### 5. **FRED API: Works Correctly**
**Severity: NONE**

The FRED API implementation appears correct and matches the official FRED API documentation:
- `/fred/series/observations` endpoint ✓
- Required parameters: `api_key`, `series_id` ✓
- Optional parameters: `file_type`, `sort_order`, `limit` ✓
- Response parsing handles `observations` array ✓
- Missing value handling for "." ✓

**Verified Working:**
```bash
uv run polyarb rates --series-id DGS3MO
# Returns: 3.67% (as of 2026-01-29) ✓

uv run polyarb rates --search "treasury"
# Returns: 10 relevant series ✓
```

---

## Low Issues (Nice to Fix)

### 6. **CLI: Outcome Selection Crash**
**Severity: LOW** (consequence of Issue #1)
**File:** `polyarb/cli.py:446-470`

**Problem:** The multi-outcome selection crashes because `market.clob_token_ids` is empty (due to JSON parsing bug).

**Fix:** This will be resolved by fixing Issue #1.

---

### 7. **CLI: Missing `--outcome` Flag**
**Severity: LOW**
**File:** `polyarb/cli.py`

**Problem:** For multi-outcome markets, users must interactively select an outcome. There's no CLI flag to specify the outcome non-interactively.

**Fix:** Add `--outcome TEXT` option to the analyze command.

---

## Test Results Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Unit Tests | ✅ 237 PASS | Tests pass but mock API responses |
| `polyarb markets --search` | ❌ BROKEN | Wrong endpoint, wrong results |
| `polyarb analyze` | ❌ BROKEN | JSON parsing bug, no token IDs |
| `polyarb rates` | ✅ WORKS | FRED API implemented correctly |
| Gamma API `/markets` | ⚠️ PARTIAL | Filtering doesn't work |
| Gamma API `/public-search` | ✅ WORKS | Correct endpoint exists but not used |
| CLOB API `/price` | ⚠️ PARTIAL | Works but poor error handling |
| CLOB API `/book` | ⚠️ PARTIAL | Works but poor error handling |
| FRED API | ✅ WORKS | All endpoints working |

---

## Root Cause Analysis

The implementation was built against **assumed** API contracts rather than the **actual** API behavior:

1. **Gamma API assumed** `outcomes` and `clobTokenIds` were JSON arrays → Actually JSON strings
2. **Gamma API assumed** `/markets?query=` supported keyword search → Actually needs `/public-search?q=`
3. **Gamma API assumed** `active=true` filter worked → Doesn't filter as expected

The test suite passes because it mocks HTTP responses with **assumed** formats, not actual API responses. This masked the bugs during development.

---

## Recommended Fix Priority

1. **IMMEDIATE:** Fix JSON string parsing in `polymarket_gamma.py` (Critical - nothing works without this)
2. **HIGH:** Change search to use `/public-search` endpoint (Search is core functionality)
3. **MEDIUM:** Improve CLOB error handling (Better UX)
4. **LOW:** Add `--outcome` CLI flag (Convenience)

---

## Files Requiring Modification

| File | Changes Required |
|------|------------------|
| `polyarb/clients/polymarket_gamma.py` | Fix JSON parsing, fix search endpoint |
| `polyarb/clients/polymarket_clob.py` | Improve 404 error handling |
| `polyarb/cli.py` | Add `--outcome` flag |
| `tests/test_gamma_client.py` | Update mocks to use actual API format |
| `tests/test_clob_client.py` | Add tests for "no orderbook" scenario |

---

## Verification Steps After Fixes

1. **Test JSON parsing:**
   ```bash
   uv run python -c "
   from polyarb.clients.polymarket_gamma import GammaClient
   client = GammaClient()
   market = client.get_market('678876')
   print(f'outcomes: {market.outcomes}')  # Should be ['Yes', 'No']
   print(f'token_ids: {market.clob_token_ids}')  # Should have Yes/No keys
   "
   ```

2. **Test search:**
   ```bash
   uv run polyarb markets --search "BTC" --limit 5
   # Should return BTC-related markets
   ```

3. **Test full analyze:**
   ```bash
   uv run polyarb analyze MARKET_ID --ticker SPY --event-type above --level 600 --rate 0.04
   # Should produce A-G report
   ```

---

## Task List

### Phase 1: Critical Fixes (Gamma API)

- [ ] 1.1: Fix JSON string parsing for outcomes field
  - File: `polyarb/clients/polymarket_gamma.py`
  - Add `import json` at top of file
  - In `_parse_market()` method, check if `outcomes_data` is a string
  - If string, parse with `json.loads(outcomes_data)`
  - Ensure outcomes is always a Python list of strings

- [ ] 1.2: Fix JSON string parsing for clobTokenIds field
  - File: `polyarb/clients/polymarket_gamma.py`
  - In `_parse_market()` method, check if `clob_token_ids_raw` is a string
  - If string, parse with `json.loads(clob_token_ids_raw)`
  - Ensure token IDs are properly mapped to outcomes

- [ ] 1.3: Update unit tests for JSON string format
  - File: `tests/test_gamma_client.py`
  - Update mock responses to use JSON strings (matching real API)
  - Add test case for string vs list format handling
  - Verify all 10 existing tests still pass

### Phase 2: Search Endpoint Fix

- [ ] 2.1: Implement `/public-search` endpoint method
  - File: `polyarb/clients/polymarket_gamma.py`
  - Add new method `public_search(query, limit)`
  - Use endpoint: `GET /public-search?q={query}&limit={limit}`
  - Parse response structure: `{events: [{markets: [...]}]}`
  - Return flattened list of Market objects

- [ ] 2.2: Update `search_markets()` to use public-search
  - File: `polyarb/clients/polymarket_gamma.py`
  - Modify existing `search_markets()` method
  - When `query` parameter is provided, use `/public-search` endpoint
  - When no query, use `/events` endpoint for listing
  - Handle the nested events/markets response structure

- [ ] 2.3: Update CLI markets command
  - File: `polyarb/cli.py`
  - Update `markets` command to use new search method
  - Ensure `--search` flag works correctly
  - Add client-side filtering for `endDate > today()` if needed

- [ ] 2.4: Update search tests
  - File: `tests/test_gamma_client.py`
  - Add tests for `/public-search` endpoint
  - Mock the correct response structure
  - Test query parameter handling

### Phase 3: CLOB Error Handling

- [ ] 3.1: Improve 404 error handling in CLOB client
  - File: `polyarb/clients/polymarket_clob.py`
  - Parse 404 response body for "No orderbook exists" message
  - Create distinct error types: `NoOrderbookError` vs `TokenNotFoundError`
  - Return None or raise appropriate error based on response

- [ ] 3.2: Handle inactive markets gracefully in CLI
  - File: `polyarb/cli.py`
  - Catch `NoOrderbookError` in analyze command
  - Display user-friendly message: "Market has no active trading"
  - Suggest using `--yes-price` flag to provide price manually

- [ ] 3.3: Add CLOB error handling tests
  - File: `tests/test_clob_client.py`
  - Add test for "No orderbook exists" 404 response
  - Add test for actual token not found 404 response
  - Verify correct exception types are raised

### Phase 4: CLI Enhancements

- [ ] 4.1: Add `--outcome` flag to analyze command
  - File: `polyarb/cli.py`
  - Add `@click.option('--outcome', type=str, help='Outcome label for multi-outcome markets')`
  - Use provided outcome instead of prompting
  - Validate outcome exists in market

- [ ] 4.2: Filter expired markets from listing
  - File: `polyarb/cli.py` or `polyarb/clients/polymarket_gamma.py`
  - Add client-side filtering: `market.end_date > datetime.now()`
  - Add `--include-expired` flag to show all markets if needed
  - Update markets command output

- [ ] 4.3: Add CLI enhancement tests
  - File: `tests/test_cli_validation.py`
  - Add test for `--outcome` flag
  - Add test for expired market filtering
  - Verify backward compatibility

### Phase 5: Integration Testing

- [ ] 5.1: Create integration test with real API
  - File: `tests/test_integration.py` (new file)
  - Test `GammaClient.get_market()` with real market ID
  - Verify outcomes and token IDs are parsed correctly
  - Skip in CI if no network (use `@pytest.mark.integration`)

- [ ] 5.2: End-to-end CLI test
  - Test full `polyarb markets --search "BTC"` command
  - Verify BTC-related markets are returned
  - Test `polyarb analyze` with a valid active market

- [ ] 5.3: Run full test suite
  - Run `uv run pytest -v`
  - Ensure all 237+ tests pass
  - Fix any regressions from changes

---

## Notes

### API Reference (Verified)

**Gamma API:**
- Base: `https://gamma-api.polymarket.com`
- `GET /markets/{id}` - Get single market (returns JSON strings for outcomes/tokens)
- `GET /public-search?q={query}` - Search markets by keyword
- `GET /events?active=true&closed=false` - List events with markets

**CLOB API:**
- Base: `https://clob.polymarket.com`
- `GET /price?token_id={id}&side={BUY|SELL}` - Get price
- `GET /book?token_id={id}` - Get order book

**FRED API:** (Working correctly)
- Base: `https://api.stlouisfed.org/fred`
- `GET /series/observations?series_id={id}&api_key={key}` - Get rate data
- `GET /series/search?search_text={query}&api_key={key}` - Search series

### Dependencies Between Tasks
- 1.1, 1.2 must be done first (critical bug)
- 1.3 should follow 1.1, 1.2
- 2.1-2.4 can be done after Phase 1
- 3.1-3.3 can be done in parallel with Phase 2
- 4.1-4.3 depend on Phases 1-3
- 5.1-5.3 should be done last (validation)
