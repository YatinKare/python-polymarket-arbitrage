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
@pass_context
def markets(ctx: PolyarbContext, search: Optional[str], slug: Optional[str], limit: int):
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
        markets_list = client.search_markets(query=search, limit=limit)

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
            expiry_date = market.end_date
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
        if market.end_date and expiry_date != market.end_date:
            click.echo(
                f"Warning: User-provided expiry ({expiry_date}) differs from "
                f"market end date ({market.end_date}).",
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

    # TODO: Task 7.4 will implement the orchestration logic here
    click.echo("\n=== Analysis ===")
    click.echo("Orchestration logic not yet implemented (task 7.4)")
    click.echo(f"Market ID: {market_id}")
    click.echo(f"Market Title: {market.title}")
    click.echo(f"Market End Date: {market.end_date}")
    click.echo(f"Ticker: {ticker}")
    click.echo(f"Event Type: {event_type}")
    click.echo(f"Level: {level}")
    click.echo(f"Expiry: {expiry_date}")
    click.echo(f"Rate: {rate}")
    click.echo(f"FRED Series ID: {fred_series_id}")
    click.echo(f"Div Yield: {div_yield}")
    click.echo(f"IV Mode: {iv_mode}")
    click.echo(f"IV: {iv}")
    click.echo(f"Outcome Label: {outcome_label}")


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

    ctx.log("Fetching data from FRED API...")

    # TODO: Implementation will be added in task 7.5
    click.echo("Rates command: Not yet implemented (task 7.5)")
    click.echo(f"  Series ID: {series_id}")
    click.echo(f"  Search: {search}")


if __name__ == "__main__":
    main()
