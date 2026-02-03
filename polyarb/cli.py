"""Click-based CLI for Polymarket arbitrage analysis."""

import logging
import os
import sys
from typing import Optional

import click

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


class PolyarbContext:
    """Context object for CLI commands."""

    def __init__(self):
        self.verbose: bool = False
        self.fred_api_key: Optional[str] = None

    def log(self, msg: str, level: str = "info"):
        """Log a message at the specified level."""
        if level == "debug" and not self.verbose:
            return
        getattr(logger, level)(msg)


pass_context = click.make_pass_decorator(PolyarbContext, ensure=True)


@click.group()
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging (debug level).",
)
@click.pass_context
def main(ctx: click.Context, verbose: bool):
    """
    Polymarket Options-Implied Fair Value CLI.

    Compute risk-neutral fair values for Polymarket binary markets using
    options pricing models (digital and touch barrier).

    Environment variables:
      FRED_API_KEY    API key for FRED (Federal Reserve Economic Data)
    """
    # Initialize context
    ctx.obj = PolyarbContext()
    ctx.obj.verbose = verbose

    # Set logging level based on verbose flag
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    # Load FRED API key from environment
    from dotenv import load_dotenv
    load_dotenv()

    ctx.obj.fred_api_key = os.getenv("FRED_API_KEY")
    if ctx.obj.fred_api_key:
        logger.debug("FRED_API_KEY loaded from environment")
    else:
        logger.debug("FRED_API_KEY not found in environment")


@main.command()
@click.option(
    "--search",
    type=str,
    help="Search markets by keyword.",
)
@click.option(
    "--slug",
    type=str,
    help="Filter by exact slug match (if supported by API).",
)
@click.option(
    "--limit",
    type=int,
    default=10,
    help="Maximum number of markets to return.",
)
@click.option(
    "--include-expired",
    is_flag=True,
    default=False,
    help="Include expired markets in listing.",
)
@pass_context
def markets(ctx: PolyarbContext, search: Optional[str], slug: Optional[str], limit: int, include_expired: bool):
    """
    List and search Polymarket markets.

    Examples:
      polyarb markets --search "BTC"
      polyarb markets --search "Trump" --limit 5
    """
    from polyarb.clients.polymarket_gamma import GammaClient

    ctx.log("Fetching markets from Polymarket Gamma API...")

    try:
        client = GammaClient()
        markets_list = client.search_markets(query=search, limit=limit, include_expired=include_expired)

        if not markets_list:
            click.echo("No markets found.")
            return

        # Output table header
        click.echo(f"\n{'ID':<25} {'End Date':<12} {'Title'}")
        click.echo("-" * 80)

        # Output each market
        for market in markets_list:
            # Truncate title if too long
            title = market.title
            if len(title) > 40:
                title = title[:37] + "..."

            # Format end date
            end_date = market.end_date.strftime("%Y-%m-%d") if market.end_date else "N/A"

            click.echo(f"{market.id:<25} {end_date:<12} {title}")

        click.echo(f"\nShowing {len(markets_list)} market(s)")

    except Exception as e:
        click.echo(f"Error fetching markets: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("market_id", type=str)
@click.option(
    "--ticker",
    type=str,
    help="yfinance ticker symbol (e.g., SPY, BTC-USD).",
)
@click.option(
    "--event-type",
    type=click.Choice(["touch", "above", "below"], case_sensitive=False),
    help="Type of event: touch (barrier hit), above (settle above), below (settle below).",
)
@click.option(
    "--level",
    type=float,
    help="Strike price (for digital) or barrier level (for touch).",
)
@click.option(
    "--expiry",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Expiry date in YYYY-MM-DD format (overrides market end date if provided).",
)
@click.option(
    "--yes-price",
    type=float,
    help="Polymarket Yes price (if not provided, fetches from CLOB).",
)
@click.option(
    "--no-price",
    type=float,
    help="Polymarket No price (if not provided, fetches from CLOB).",
)
@click.option(
    "--rate",
    type=float,
    help="Annual risk-free rate as decimal (e.g., 0.045 for 4.5%%).",
)
@click.option(
    "--fred-series-id",
    type=str,
    help="FRED series ID to fetch risk-free rate (e.g., DGS3MO for 3-month T-bill).",
)
@click.option(
    "--div-yield",
    type=float,
    default=0.0,
    help="Annual dividend yield as decimal (e.g., 0.02 for 2%%). Defaults to 0.",
)
@click.option(
    "--iv-mode",
    type=click.Choice(["auto", "manual"], case_sensitive=False),
    default="auto",
    help="IV selection mode: auto (extract from options) or manual (provide --iv).",
)
@click.option(
    "--iv",
    type=float,
    help="Implied volatility as decimal (e.g., 0.25 for 25%%). Required if --iv-mode=manual.",
)
@click.option(
    "--iv-strike-window",
    type=float,
    default=0.05,
    help="Moneyness window for strike region (e.g., 0.05 for ±5%%). Used in auto mode.",
)
@click.option(
    "--abs-tol",
    type=float,
    default=0.01,
    help="Absolute price tolerance for fair verdict (default: 0.01).",
)
@click.option(
    "--pct-tol",
    type=float,
    default=0.05,
    help="Percentage price tolerance for fair verdict (default: 0.05 = 5%%).",
)
@click.option(
    "--output",
    type=click.Path(),
    help="Output file path (if not provided, prints to stdout).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown"], case_sensitive=False),
    default="markdown",
    help="Output format (v1: markdown only).",
)
@click.option(
    "--outcome-label",
    type=str,
    help="Outcome label for multi-outcome markets (e.g., 'Yes', 'No').",
)
@pass_context
def analyze(
    ctx: PolyarbContext,
    market_id: str,
    ticker: Optional[str],
    event_type: Optional[str],
    level: Optional[float],
    expiry: Optional[click.DateTime],
    yes_price: Optional[float],
    no_price: Optional[float],
    rate: Optional[float],
    fred_series_id: Optional[str],
    div_yield: float,
    iv_mode: str,
    iv: Optional[float],
    iv_strike_window: float,
    abs_tol: float,
    pct_tol: float,
    output: Optional[str],
    output_format: str,
    outcome_label: Optional[str],
):
    """
    Analyze a Polymarket market and compute options-implied fair value.

    Produces a comprehensive A-G analysis report comparing Polymarket prices
    to risk-neutral fair values computed from options pricing models.

    MARKET_ID is the Polymarket market ID (e.g., from 'polyarb markets' command).

    Examples:
      polyarb analyze 12345 --ticker BTC-USD --event-type touch --level 80000
      polyarb analyze 67890 --ticker SPY --event-type above --level 500 --rate 0.045
    """
    from datetime import datetime, date
    from polyarb.clients.polymarket_gamma import GammaClient

    ctx.log(f"Analyzing market: {market_id}")

    # Step 1: Fetch market metadata from Gamma
    try:
        ctx.log("Fetching market data from Polymarket Gamma API...")
        gamma_client = GammaClient()
        market = gamma_client.get_market(market_id)
        ctx.log(f"Market: {market.title}")
    except Exception as e:
        click.echo(f"Error fetching market: {e}", err=True)
        sys.exit(1)

    # Step 2: Prompt for missing required inputs

    # Ticker (required)
    if not ticker:
        ticker = click.prompt("Enter yfinance ticker symbol (e.g., SPY, BTC-USD)", type=str)

    # Event type (required)
    if not event_type:
        event_type = click.prompt(
            "Select event type",
            type=click.Choice(["touch", "above", "below"], case_sensitive=False),
        )
    event_type = event_type.lower()

    # Level (required)
    if level is None:
        level = click.prompt(
            f"Enter {'barrier level' if event_type == 'touch' else 'strike price'}",
            type=float,
        )

    # Expiry (use market end date if not provided)
    if expiry is None:
        if market.end_date:
            # Convert datetime to date if needed
            expiry_date = market.end_date.date() if isinstance(market.end_date, datetime) else market.end_date
            ctx.log(f"Using market end date as expiry: {expiry_date.strftime('%Y-%m-%d')}")
        else:
            # Market has no end date, prompt user
            expiry_str = click.prompt("Enter expiry date (YYYY-MM-DD)", type=str)
            try:
                expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            except ValueError:
                click.echo(f"Error: Invalid date format '{expiry_str}'. Use YYYY-MM-DD.", err=True)
                sys.exit(1)
    else:
        # Convert click.DateTime to date
        expiry_date = expiry.date() if isinstance(expiry, datetime) else expiry
        # Warn if user override differs from market end date
        if market.end_date:
            market_end_date = market.end_date.date() if isinstance(market.end_date, datetime) else market.end_date
            if expiry_date != market_end_date:
                click.echo(
                    f"Warning: User-provided expiry ({expiry_date}) differs from "
                    f"market end date ({market_end_date}).",
                    err=True,
                )

    # Step 3: Validate inputs
    validation_errors = []

    # Expiry must be in the future
    today = date.today()
    if expiry_date <= today:
        validation_errors.append(f"Expiry date {expiry_date} must be in the future (today: {today})")

    # Level must be positive
    if level <= 0:
        validation_errors.append(f"Level/strike must be positive (got: {level})")

    # Yes/No prices must be in [0, 1] if provided
    if yes_price is not None and not (0 <= yes_price <= 1):
        validation_errors.append(f"Yes price must be in [0, 1] (got: {yes_price})")
    if no_price is not None and not (0 <= no_price <= 1):
        validation_errors.append(f"No price must be in [0, 1] (got: {no_price})")

    # IV must be positive if provided
    if iv is not None and iv <= 0:
        validation_errors.append(f"Implied volatility must be positive (got: {iv})")

    # Manual IV mode requires --iv
    if iv_mode.lower() == "manual" and iv is None:
        validation_errors.append("Manual IV mode requires --iv parameter")

    # Rate: must have either --rate OR --fred-series-id
    if rate is None and fred_series_id is None:
        validation_errors.append(
            "Must provide either --rate or --fred-series-id for risk-free rate"
        )

    # Both rate and fred-series-id provided (warn but allow, prefer user-provided rate)
    if rate is not None and fred_series_id is not None:
        click.echo(
            "Warning: Both --rate and --fred-series-id provided. Using --rate.",
            err=True,
        )

    # Validate rate is reasonable if provided
    if rate is not None and not (-0.1 <= rate <= 0.3):
        click.echo(
            f"Warning: Risk-free rate {rate:.1%} seems unusual (expected -10% to 30%).",
            err=True,
        )

    # Validate dividend yield is reasonable
    if not (0 <= div_yield <= 0.2):
        click.echo(
            f"Warning: Dividend yield {div_yield:.1%} seems unusual (expected 0% to 20%).",
            err=True,
        )

    # IV strike window must be positive
    if iv_strike_window <= 0:
        validation_errors.append(f"IV strike window must be positive (got: {iv_strike_window})")

    # Tolerances must be non-negative
    if abs_tol < 0:
        validation_errors.append(f"Absolute tolerance must be non-negative (got: {abs_tol})")
    if pct_tol < 0:
        validation_errors.append(f"Percentage tolerance must be non-negative (got: {pct_tol})")

    # Report validation errors
    if validation_errors:
        click.echo("Validation errors:", err=True)
        for error in validation_errors:
            click.echo(f"  - {error}", err=True)
        sys.exit(1)

    # Step 4: Warn about default dividend yield
    if div_yield == 0.0:
        ctx.log("Warning: Using default dividend yield of 0% (not provided)")

    # Step 5: Store validated inputs for orchestration (task 7.4)
    ctx.log("Input validation complete")
    ctx.log(f"  Market: {market.title}")
    ctx.log(f"  Ticker: {ticker}")
    ctx.log(f"  Event Type: {event_type}")
    ctx.log(f"  Level: {level}")
    ctx.log(f"  Expiry: {expiry_date}")
    ctx.log(f"  Risk-free rate: {'from FRED ' + fred_series_id if rate is None else f'{rate:.4f}'}")
    ctx.log(f"  Dividend yield: {div_yield:.4f}")
    ctx.log(f"  IV mode: {iv_mode}")

    # Step 6: Orchestration - fetch all data and run analysis
    try:
        # Import required modules
        from polyarb.clients.polymarket_clob import ClobClient, NoOrderbookError
        from polyarb.clients.fred import FredClient
        from polyarb.clients.yfinance_md import YFMarketData
        from polyarb.vol.iv_extract import extract_strike_region_iv
        from polyarb.vol.term_structure import interpolate_iv_term_structure, compute_time_to_expiry
        from polyarb.pricing.digital_bs import digital_price_with_sensitivity, compute_verdict
        from polyarb.pricing.touch_barrier import touch_price_with_sensitivity
        from polyarb.report.markdown_report import render
        from polyarb.models import ReportContext

        # 6.1: Map Yes/No outcomes to token IDs
        ctx.log("Mapping outcomes to token IDs...")

        # For markets with 2 outcomes (typical binary markets)
        if len(market.outcomes) == 2:
            # Try to find Yes/No automatically
            yes_outcome = None
            no_outcome = None

            for outcome_name, token_id in market.clob_token_ids.items():
                if outcome_name.lower() in ['yes', 'y']:
                    yes_outcome = outcome_name
                elif outcome_name.lower() in ['no', 'n']:
                    no_outcome = outcome_name

            # If not found, use first/second outcomes
            if yes_outcome is None or no_outcome is None:
                outcome_names = list(market.clob_token_ids.keys())
                yes_outcome = outcome_names[0]
                no_outcome = outcome_names[1] if len(outcome_names) > 1 else None
                ctx.log(f"Using outcomes: Yes='{yes_outcome}', No='{no_outcome}'")

        # For multi-outcome markets (>2 outcomes)
        elif len(market.outcomes) > 2:
            if outcome_label is None:
                # Prompt user to select outcome
                click.echo("\nThis market has multiple outcomes:")
                for i, outcome_name in enumerate(market.clob_token_ids.keys()):
                    click.echo(f"  {i+1}. {outcome_name}")
                outcome_label = click.prompt("Select outcome (enter name or number)", type=str)

                # Allow numeric selection
                try:
                    idx = int(outcome_label) - 1
                    outcome_label = list(market.clob_token_ids.keys())[idx]
                except (ValueError, IndexError):
                    pass

            # Validate outcome label exists
            if outcome_label not in market.clob_token_ids:
                click.echo(f"Error: Outcome '{outcome_label}' not found in market outcomes", err=True)
                click.echo(f"Available outcomes: {', '.join(market.clob_token_ids.keys())}", err=True)
                sys.exit(1)

            yes_outcome = outcome_label
            no_outcome = None
            ctx.log(f"Using selected outcome: '{yes_outcome}'")

        else:
            click.echo("Error: Market has no outcomes with token IDs", err=True)
            sys.exit(1)

        yes_token_id = market.clob_token_ids[yes_outcome]

        # 6.2: Fetch Polymarket prices from CLOB
        clob_client = ClobClient()
        try:
            if yes_price is None:
                ctx.log(f"Fetching Yes price from CLOB for token {yes_token_id}...")
                yes_price = clob_client.get_yes_price(yes_token_id)
                ctx.log(f"Yes price: ${yes_price:.4f}")
            else:
                ctx.log(f"Using provided Yes price: ${yes_price:.4f}")

            if no_price is None and no_outcome is not None:
                no_token_id = market.clob_token_ids[no_outcome]
                ctx.log(f"Fetching No price from CLOB for token {no_token_id}...")
                no_price = clob_client.get_yes_price(no_token_id)
                ctx.log(f"No price: ${no_price:.4f}")
        except NoOrderbookError:
            click.echo("Error: Market has no active orderbook. Use --yes-price to provide the price manually.", err=True)
            sys.exit(1)

        # 6.3: Fetch yfinance spot price
        ctx.log(f"Fetching spot price for {ticker}...")
        yf_client = YFMarketData()
        spot_price = yf_client.get_spot(ticker)
        ctx.log(f"Spot price: ${spot_price:,.2f}")

        # 6.4: Fetch or use provided risk-free rate
        if rate is None:
            ctx.log(f"Fetching risk-free rate from FRED series {fred_series_id}...")
            fred_client = FredClient(api_key=ctx.fred_api_key)
            rate_value, rate_date = fred_client.get_latest_observation(fred_series_id)
            rate = rate_value / 100.0  # Convert from percentage to decimal
            ctx.log(f"Risk-free rate: {rate:.4%} (from {rate_date})")
            rate_source = f"FRED {fred_series_id} ({rate_date})"
        else:
            ctx.log(f"Using provided rate: {rate:.4%}")
            rate_source = "User-provided"

        # 6.5: Select IV using vol module (strike region + term structure)
        if iv_mode.lower() == "manual":
            ctx.log(f"Using manual IV: {iv:.4f}")
            sigma = iv
            iv_source = "User-provided"
        else:
            ctx.log(f"Extracting IV from {ticker} option chain...")

            # Get available option expiries
            expiries = yf_client.get_option_expiries(ticker)
            ctx.log(f"Found {len(expiries)} option expiries")

            # For each expiry, extract strike-region IV
            expiry_iv_pairs = []
            for exp_date in expiries:
                try:
                    calls_df, puts_df = yf_client.get_chain(ticker, exp_date)

                    # Use calls for above/touch, puts for below
                    # For touch, use the chain that has the barrier (calls if barrier > spot, puts if barrier < spot)
                    if event_type == "below" or (event_type == "touch" and level < spot_price):
                        chain_df = puts_df
                        chain_type = "puts"
                    else:
                        chain_df = calls_df
                        chain_type = "calls"

                    # Extract IV for strike region
                    iv_value = extract_strike_region_iv(chain_df, level, iv_strike_window)
                    expiry_iv_pairs.append((exp_date, iv_value))
                    ctx.log(f"  {exp_date}: IV = {iv_value:.4f} (from {chain_type})")
                except Exception as e:
                    ctx.log(f"  {exp_date}: Skipped ({str(e)})", level="warning")

            if not expiry_iv_pairs:
                click.echo("Error: Could not extract IV from any option expiry", err=True)
                sys.exit(1)

            # Interpolate to target expiry using term structure
            ctx.log(f"Interpolating IV to target expiry {expiry_date}...")
            sigma = interpolate_iv_term_structure(expiry_date, expiry_iv_pairs, today)
            ctx.log(f"Interpolated IV: {sigma:.4f}")
            iv_source = f"yfinance option chain (interpolated from {len(expiry_iv_pairs)} expiries)"

        # 6.6: Choose pricing model and run analysis
        ctx.log(f"Running {event_type} pricing model...")

        T = compute_time_to_expiry(expiry_date, today)
        ctx.log(f"Time to expiry: {T:.4f} years ({(T * 365):.0f} days)")

        if event_type == "touch":
            # Touch barrier pricing
            result = touch_price_with_sensitivity(
                S0=spot_price,
                B=level,
                T=T,
                r=rate,
                q=div_yield,
                sigma=sigma,
            )
            model_name = "Touch Barrier"
        else:
            # Digital option pricing (above or below)
            result = digital_price_with_sensitivity(
                S0=spot_price,
                K=level,
                T=T,
                r=rate,
                q=div_yield,
                sigma=sigma,
                direction=event_type,
            )
            model_name = f"Digital Option ({'Above' if event_type == 'above' else 'Below'})"

        ctx.log(f"Event probability: {result.probability:.4%}")
        ctx.log(f"Fair PV: ${result.pv:.4f}")

        # 6.7: Compute verdict
        verdict = compute_verdict(yes_price, result.pv, abs_tol, pct_tol)
        mispricing_abs = yes_price - result.pv
        mispricing_pct = (mispricing_abs / result.pv) if result.pv > 0 else 0

        ctx.log(f"Verdict: {verdict}")
        ctx.log(f"Mispricing: ${mispricing_abs:+.4f} ({mispricing_pct:+.2%})")

        # 6.8: Build ReportContext
        ctx.log("Building report context...")

        from polyarb.models import AnalysisInputs, AnalysisResults, EventType, IVMode, Verdict
        import math

        # Build AnalysisInputs
        inputs = AnalysisInputs(
            market_id=market_id,
            ticker=ticker,
            event_type=EventType(event_type),
            level=level,
            expiry=expiry_date,
            yes_price=yes_price,
            no_price=no_price,
            spot_price=spot_price,
            rate=rate,
            fred_series_id=fred_series_id,
            div_yield=div_yield,
            iv_mode=IVMode(iv_mode.lower()),
            iv=iv if iv_mode.lower() == "manual" else sigma,
            iv_strike_window=iv_strike_window,
            abs_tol=abs_tol,
            pct_tol=pct_tol,
            output_path=output,
            output_format=output_format,
            outcome_label=outcome_label,
        )

        # Build AnalysisResults
        analysis_results = AnalysisResults(
            inputs=inputs,
            market=market,
            spot_price=spot_price,
            risk_free_rate=rate,
            implied_vol=sigma,
            time_to_expiry=T,
            pricing=result,
            poly_yes_price=yes_price,
            poly_no_price=no_price if no_price is not None else 0.0,
            verdict=Verdict(verdict),
            mispricing_abs=mispricing_abs,
            mispricing_pct=mispricing_pct,
            iv_source=iv_source,
            rate_source=rate_source,
        )

        # Compute additional values for report context
        log_moneyness = math.log(spot_price / level)
        variance_term = sigma * math.sqrt(T)

        # Build ReportContext
        report_ctx = ReportContext(
            results=analysis_results,
            log_moneyness=log_moneyness,
            variance_term=variance_term,
            model_name=model_name,
            model_rationale=None,  # Will use default generation
        )

        # 6.9: Generate markdown report
        ctx.log("Generating markdown report...")
        report_markdown = render(report_ctx)

        # 6.10: Output report
        if output:
            ctx.log(f"Writing report to {output}...")
            with open(output, 'w') as f:
                f.write(report_markdown)
            click.echo(f"Report written to: {output}")
        else:
            click.echo("\n" + "="*80)
            click.echo(report_markdown)
            click.echo("="*80)

        ctx.log("Analysis complete!")

    except Exception as e:
        click.echo(f"Error during analysis: {e}", err=True)
        if ctx.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@main.command()
@click.option(
    "--series-id",
    type=str,
    help="FRED series ID (e.g., DGS3MO for 3-month T-bill rate).",
)
@click.option(
    "--search",
    type=str,
    help="Search for rate series by keyword.",
)
@pass_context
def rates(ctx: PolyarbContext, series_id: Optional[str], search: Optional[str]):
    """
    Fetch risk-free rates from FRED (Federal Reserve Economic Data).

    Requires FRED_API_KEY environment variable.

    Examples:
      polyarb rates --series-id DGS3MO
      polyarb rates --search "treasury"
    """
    # Check for API key
    if not ctx.fred_api_key:
        click.echo(
            "Error: FRED_API_KEY environment variable not set.\n"
            "Get a free API key at: https://fred.stlouisfed.org/docs/api/api_key.html",
            err=True,
        )
        sys.exit(1)

    if not series_id and not search:
        click.echo("Error: Must provide either --series-id or --search", err=True)
        sys.exit(1)

    from polyarb.clients.fred import FredClient

    try:
        fred_client = FredClient(api_key=ctx.fred_api_key)

        if search:
            # Search for series by keyword
            ctx.log(f"Searching for series matching '{search}'...")
            results = fred_client.search_series(query=search, limit=10)

            if not results:
                click.echo(f"No series found matching '{search}'")
                return

            click.echo(f"\nFound {len(results)} series:\n")
            for i, series in enumerate(results, 1):
                title = series.get("title", "N/A")
                series_id_result = series.get("id", "N/A")
                units = series.get("units", "N/A")
                frequency = series.get("frequency", "N/A")

                click.echo(f"{i}. {series_id_result}")
                click.echo(f"   Title: {title}")
                click.echo(f"   Units: {units}, Frequency: {frequency}")
                click.echo()

        if series_id:
            # Fetch latest observation for the series
            ctx.log(f"Fetching latest observation for series {series_id}...")

            # Get series info
            info = fred_client.get_series_info(series_id)
            title = info.get("title", "N/A")
            units = info.get("units", "N/A")

            # Get latest observation
            value, obs_date = fred_client.get_latest_observation(series_id)

            click.echo(f"\nSeries: {series_id}")
            click.echo(f"Title: {title}")
            click.echo(f"Units: {units}")
            click.echo(f"Latest observation: {value} (as of {obs_date})")

            # If units indicate percentage, also show as decimal
            if "percent" in units.lower():
                decimal_value = value / 100
                click.echo(f"Decimal form: {decimal_value:.6f}")

    except Exception as e:
        ctx.log(f"Error fetching FRED data: {e}", level="error")
        if ctx.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
