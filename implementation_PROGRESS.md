# Progress: implementation

## Status
RALPH_DONE

## Analysis

### What Exists vs What's Needed

The codebase is a well-structured Python CLI (`polyarb`) with layered architecture: API clients, pricing engines, vol extraction, and report generation. 237 unit tests pass. The investigation report in `implementation.md` correctly identifies the bugs. Below is a reconciliation of the plan against actual code.

#### Confirmed Bugs (verified by reading source)

1. **JSON string parsing — `polymarket_gamma.py:166-170`**
   - `outcomes_data` is iterated directly with `[str(outcome) for outcome in outcomes_data]`
   - When the real API returns `outcomes` as a JSON string like `'["Yes","No"]'`, this produces `['[', '"', 'Y', ...]`
   - No `import json` in the file
   - Same problem for `clobTokenIds` at lines 174-178: when it is a JSON string, neither the `isinstance(..., list)` check (line 183) nor the `isinstance(..., dict)` check (line 189) is True, so `clob_token_ids` stays `{}`

2. **Wrong search endpoint — `polymarket_gamma.py:85`**
   - Uses `GET /markets` with a `query` param that the API ignores
   - Plan says to use `GET /public-search?q=` which returns `{events: [{markets: [...]}]}`

3. **CLOB 404 not distinguished — `polymarket_clob.py:60-61, 91-92`**
   - All 404s raise `ClobClientError("Token {id} not found")`
   - The response body (`{"error":"No orderbook exists..."}`) is never read
   - Need to parse `e.response` body to distinguish "no orderbook" from truly invalid tokens

4. **Test fixtures don't match real API — `tests/test_gamma_client.py:20-21, 38, 46`**
   - Mock responses use Python lists (`["Yes", "No"]`) for `outcomes` and `clobTokenIds`
   - Real API returns JSON strings (`'["Yes", "No"]'`)
   - Tests pass because they never exercise the string-parsing path

#### Already Implemented (plan tasks that are NOT needed)

- **`--outcome` CLI flag (plan task 4.1):** Already exists as `--outcome-label` at `cli.py:224-228`. The analyze command already accepts it and uses it for multi-outcome selection at lines 448-470. No work needed here.

#### Latent Bug Discovered (not in plan, must be addressed)

- **`clob_client` scope bug — `cli.py:481-490`:** If the user provides `--yes-price` on the command line, the `clob_client = ClobClient()` instantiation at line 481 is skipped. Then at line 490, `no_price` fetch tries to call `clob_client.get_yes_price(...)` which will raise `NameError: name 'clob_client' is not defined`. This path is exercised whenever `--yes-price` is given without `--no-price`.

#### Dependency Map

```
Phase 1 (JSON parsing) ──► Phase 1 tests
        │
        ▼
Phase 2 (search endpoint) ──► Phase 2 tests
        │
        ├──► Phase 3 (CLOB 404 handling) ──► Phase 3 tests
        │
        ▼
   Phase 4 (CLI bug fix + expired market filter)
        │
        ▼
   Phase 5 (integration / full test run)
```

Phases 2 and 3 can proceed in parallel after Phase 1. Phase 4 depends on 1-3 because expired-market filtering requires search to work. Phase 5 is final validation.

---

## Task List

### Phase 1: Critical — Gamma JSON Parsing (blocks everything)

- [x] 1.1: Add `import json` to `polymarket_gamma.py` and parse `outcomes` when it is a string
  - File: `polyarb/clients/polymarket_gamma.py`
  - Added `import json` at top of file
  - Added `if isinstance(outcomes_data, str): outcomes_data = json.loads(outcomes_data)` before the emptiness check
  - All 237 tests pass

- [x] 1.2: Parse `clobTokenIds` when it is a string
  - File: `polyarb/clients/polymarket_gamma.py`
  - Added `if isinstance(clob_token_ids_raw, str): clob_token_ids_raw = json.loads(clob_token_ids_raw)` after the raw assignment, before the list/dict branch
  - All 237 tests pass

### Phase 2: Search Endpoint Fix

- [x] 2.1: Add `public_search` method to `GammaClient`
  - File: `polyarb/clients/polymarket_gamma.py`
  - Added method between `search_markets()` and `_parse_market()`
  - Hits `GET /public-search?q={query}&limit={limit}`
  - Parses `{"events": [{"markets": [...]}]}` — flattens all markets from all events
  - Each market parsed via `_parse_market()` with same skip-on-error pattern
  - All 237 tests pass

- [x] 2.2: Route `search_markets()` to use `public_search` when query is provided
  - File: `polyarb/clients/polymarket_gamma.py`
  - Added early return at top of `search_markets()`: when `query` is truthy, delegate to `self.public_search(query, limit)` and return
  - When `query` is None (listing without search), existing `/markets` endpoint logic is unchanged
  - Updated `test_search_markets_success` mock to return `{"events": [{"markets": [...]}]}` and assert URL is `/public-search` with param `q`
  - All 237 tests pass

- [x] 2.3: Add client-side expiry filter to `search_markets()` return
  - File: `polyarb/clients/polymarket_gamma.py`
  - Added `include_expired: bool = False` parameter to `search_markets()` signature
  - Filter applied in both code paths (public_search query path and /markets listing path)
  - Used `datetime.now(tz=timezone.utc)` for comparison since `parse_datetime` returns tz-aware datetimes
  - Added `timezone` to the `from datetime import` line
  - Updated `sample_markets_list_response` fixture dates to 2030 (future) so existing tests exercise default filter correctly
  - All 237 tests pass

### Phase 3: CLOB 404 Error Handling

- [x] 3.1: Add `NoOrderbookError` exception class to CLOB client
  - File: `polyarb/clients/polymarket_clob.py`
  - Added `class NoOrderbookError(ClobClientError)` after `ClobClientError` definition
  - All 239 tests pass

- [x] 3.2: Parse 404 response body in `get_price()` and `get_book()` to distinguish error types
  - File: `polyarb/clients/polymarket_clob.py`
  - In both `get_price()` and `get_book()` 404 handlers: check `e.response.text` for "No orderbook exists"
  - If present, raise `NoOrderbookError`; otherwise keep existing `ClobClientError("Token ... not found")`
  - Updated existing 404 test mocks to set `.text = "Not Found"` (required because Mock doesn't support `in` operator)
  - Added `test_get_price_no_orderbook_error` and `test_get_book_no_orderbook_error` tests
  - All 239 tests pass

- [x] 3.3: Handle `NoOrderbookError` gracefully in CLI analyze command
  - File: `polyarb/cli.py`
  - Added `NoOrderbookError` to the local import of `polymarket_clob` (line 420)
  - Moved `clob_client = ClobClient()` before the yes/no price if/else block (fixes task 4.1 scope bug simultaneously)
  - Wrapped both price-fetch blocks in `try/except NoOrderbookError` → prints friendly message and exits
  - All 239 tests pass

### Phase 4: CLI Bug Fix + Expired Market Filter

- [x] 4.1: Fix `clob_client` scope bug in analyze command
  - File: `polyarb/cli.py`
  - Moved `clob_client = ClobClient()` out of the `if yes_price is None` block to before the try/except
  - Fixed as part of task 3.3 — single edit accomplishes both
  - All 239 tests pass

- [x] 4.2: Add `--include-expired` flag to markets command
  - File: `polyarb/cli.py`
  - Added `@click.option("--include-expired", ...)` to the `markets` command decorator stack
  - Added `include_expired: bool` parameter to the `markets()` function signature
  - Passed flag through to `client.search_markets(..., include_expired=include_expired)`
  - Done as part of task 2.3 (the CLI flag is the consumer of the filter)

### Phase 5: Validation

- [x] 5.1: Run full test suite and verify all tests pass
  - 241 tests pass, 0 failures, 6 warnings (all pre-existing UserWarnings in iv_extract)

- [x] 5.2: Verify unit tests cover the new code paths
  - Added `test_parse_market_json_string_fields` — exercises `json.loads` paths for both `outcomes` and `clobTokenIds` (lines 227-228, 243-244)
  - Added `test_search_markets_filters_expired` — exercises `include_expired` filter in the /markets listing path (lines 143-145), verifies default excludes expired and `include_expired=True` includes them
  - Existing tests already cover: public_search routing, NoOrderbookError in get_price and get_book

---

## Completed This Iteration

- Task 5.1: Ran `uv run pytest -v` — all 241 tests pass with zero failures.
- Task 5.2: Added two tests to `tests/test_gamma_client.py`:
  - `test_parse_market_json_string_fields` — verifies `_parse_market()` correctly handles `outcomes` and `clobTokenIds` as JSON-encoded strings (the real API format). Exercises the `json.loads` branches added in tasks 1.1/1.2.
  - `test_search_markets_filters_expired` — verifies `search_markets()` excludes markets with past `endDate` by default and includes them when `include_expired=True`. Uses a mock that returns one expired (2020) and one future (2099) market.
  - Confirmed existing tests already cover: `/public-search` routing, `NoOrderbookError` in both `get_price` and `get_book`.

## Notes

### Exact locations for each fix

| Task | File | Lines to touch |
|------|------|----------------|
| 1.1 | `polyarb/clients/polymarket_gamma.py` | After line 166; add json import at top |
| 1.2 | `polyarb/clients/polymarket_gamma.py` | After lines 174-178 |
| 2.1 | `polyarb/clients/polymarket_gamma.py` | New method, ~20 lines |
| 2.2 | `polyarb/clients/polymarket_gamma.py` | Lines 85-98 (search_markets body) |
| 2.3 | `polyarb/clients/polymarket_gamma.py` | End of search_markets, add filter |
| 3.1 | `polyarb/clients/polymarket_clob.py` | After line 12 |
| 3.2 | `polyarb/clients/polymarket_clob.py` | Lines 60-61, 91-92 |
| 3.3 | `polyarb/cli.py` | Lines 479-491 |
| 4.1 | `polyarb/cli.py` | Line 481 — move ClobClient() up |
| 4.2 | `polyarb/cli.py` | Add option to markets command (lines 74-91) |

### Things the plan got wrong (do NOT follow blindly)

- Plan task 4.1 ("Add --outcome flag") is **already done** as `--outcome-label` at cli.py:224. Skip it.
- Plan task 4.3 ("Add CLI enhancement tests") — `--outcome-label` has no dedicated test but is exercised indirectly. Low priority; not included in task list to avoid over-engineering.
- Plan tasks 5.1-5.2 ("integration test with real API") — these hit live network and are fragile. Replaced with "run full unit test suite" as Phase 5.

### Latent bug not in original plan

The `clob_client` variable scope bug (task 4.1 here) is a real crash path when `--yes-price` is given without `--no-price`. Must be fixed.

### API response structures (verified from plan)

- `/public-search?q=X` returns: `{"events": [{"markets": [{...}, ...], ...}, ...]}`
- Each market inside events has the same schema as `/markets/{id}` response
- `outcomes` and `clobTokenIds` fields are JSON-encoded strings in real responses

### Documentation Reference

Use the **agno-docs MCP** (`mcp__agno-docs__ask`) to double-check any questions about the Polymarket Gamma/CLOB API during implementation. This provides accurate, up-to-date documentation for endpoint structures, parameters, and response formats.
