# Progress: implementation

## Status
IN_PROGRESS

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

- [ ] 2.2: Route `search_markets()` to use `public_search` when query is provided
  - File: `polyarb/clients/polymarket_gamma.py`
  - In `search_markets()`: when `query` is not None, delegate to `self.public_search(query, limit)` and return its result
  - When `query` is None (listing without search), keep existing `/markets` endpoint logic
  - Test: `uv run polyarb markets --query "fed"` — verify results are relevant to query

- [ ] 2.3: Add client-side expiry filter to `search_markets()` return
  - File: `polyarb/clients/polymarket_gamma.py`
  - After collecting markets list, filter out any where `market.end_date < datetime.now()` (unless a flag says otherwise)
  - Add a `include_expired: bool = False` parameter to `search_markets()` signature
  - Test: `uv run polyarb markets --query "2024"` — verify expired markets are filtered out by default

### Phase 3: CLOB 404 Error Handling

- [ ] 3.1: Add `NoOrderbookError` exception class to CLOB client
  - File: `polyarb/clients/polymarket_clob.py`
  - Add new class `NoOrderbookError(ClobClientError)` after `ClobClientError` definition (around line 12)
  - No other changes to the class hierarchy
  - Test: `uv run python -c "from polyarb.clients.polymarket_clob import NoOrderbookError; print('OK')"` — verify import works

- [ ] 3.2: Parse 404 response body in `get_price()` and `get_book()` to distinguish error types
  - File: `polyarb/clients/polymarket_clob.py`
  - In both `get_price()` (lines 59-61) and `get_book()` (lines 90-92) 404 handlers:
    - Read `e.response.text` or `e.response.json()` safely
    - If body contains "No orderbook exists", raise `NoOrderbookError(...)` instead of generic `ClobClientError`
    - Otherwise keep the existing `ClobClientError("Token ... not found")`
  - Test: Use a known market without orderbook, or verify via `uv run polyarb analyze <market-slug>` that error is raised correctly

- [ ] 3.3: Handle `NoOrderbookError` gracefully in CLI analyze command
  - File: `polyarb/cli.py`
  - Around lines 479-491 where CLOB prices are fetched, wrap in try/except
  - On `NoOrderbookError`: print user-friendly message "Market has no active orderbook. Use --yes-price to provide the price manually." and exit cleanly
  - Test: `uv run polyarb analyze <market-without-orderbook>` — verify friendly error message is shown

### Phase 4: CLI Bug Fix + Expired Market Filter

- [ ] 4.1: Fix `clob_client` scope bug in analyze command
  - File: `polyarb/cli.py`
  - Lines 479-491: `clob_client` is only instantiated inside the `if yes_price is None` block (line 481)
  - Move `clob_client = ClobClient()` to before the if/else block so it is always available
  - This fixes the `NameError` when user provides `--yes-price` but not `--no-price`
  - Test: `uv run polyarb analyze <market-slug> --yes-price 0.5` — verify no NameError when only --yes-price is provided

- [ ] 4.2: Add `--include-expired` flag to markets command
  - File: `polyarb/cli.py`
  - Add `@click.option("--include-expired", is_flag=True, default=False, help="Include expired markets in listing.")` to the `markets` command
  - Pass the flag through to `client.search_markets(..., include_expired=include_expired)`
  - Test: `uv run polyarb markets --query "2024" --include-expired` — verify expired markets now appear in results

### Phase 5: Validation

- [ ] 5.1: Run full test suite and verify all tests pass
  - Command: `uv run pytest -v`
  - Fix any regressions introduced by Phases 1-4

- [ ] 5.2: Verify unit tests cover the new code paths
  - Gamma: JSON string parsing, public_search, expired filtering
  - CLOB: NoOrderbookError distinction
  - CLI: --include-expired flag

---

## Completed This Iteration

- Task 2.1: Added `public_search(query, limit)` method to `GammaClient` in `polymarket_gamma.py`. The method hits `GET /public-search?q={query}&limit={limit}`, extracts the nested `events[*].markets` arrays, flattens them, and parses each market via the existing `_parse_market()`. Uses the same try/except skip pattern as `search_markets()` so unparseable markets don't crash the entire listing. All 237 tests pass.

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
