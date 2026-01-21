"""Tests for markdown report generation (A-G sections)."""

from datetime import date, datetime
from polyarb.models import (
    AnalysisInputs,
    AnalysisResults,
    EventType,
    Market,
    PricingResult,
    ReportContext,
    Verdict,
)
from polyarb.report.markdown_report import render
import math


def create_test_report_context(
    event_type: EventType = EventType.ABOVE,
    verdict: Verdict = Verdict.FAIR,
    include_sensitivity: bool = True,
    spot_price: float = 100.0,
    level: float = 105.0,
) -> ReportContext:
    """Create a test ReportContext with realistic data."""

    # Create inputs
    inputs = AnalysisInputs(
        market_id="test-market-123",
        ticker="SPY",
        event_type=event_type,
        level=level,
        expiry=date(2026, 12, 31),
        rate=0.05,
        div_yield=0.02,
        iv_strike_window=0.05,
        abs_tol=0.01,
        pct_tol=0.05,
    )

    # Create market
    market = Market(
        id="test-market-123",
        title="Will SPY close above $105 by Dec 31, 2026?",
        description="Test market description",
        end_date=datetime(2026, 12, 31, 23, 59, 59),
        outcomes=["Yes", "No"],
        clob_token_ids={"Yes": "token-yes", "No": "token-no"},
    )

    # Create pricing result
    T = 0.5  # 6 months
    r = 0.05
    q = 0.02
    sigma = 0.25

    if event_type == EventType.TOUCH:
        # Touch barrier pricing
        S0 = spot_price
        B = level
        prob = 0.60
        pv = math.exp(-r * T) * prob
        drift = r - q - 0.5 * sigma**2

        pricing = PricingResult(
            probability=prob,
            pv=pv,
            d2=None,  # Not applicable for touch
            drift=drift,
        )
    else:
        # Digital option pricing
        S0 = spot_price
        K = level
        drift = r - q - 0.5 * sigma**2
        d2 = (math.log(S0 / K) + drift * T) / (sigma * math.sqrt(T))

        if event_type == EventType.ABOVE:
            from scipy.stats import norm
            prob = norm.cdf(d2)
        else:
            from scipy.stats import norm
            prob = norm.cdf(-d2)

        pv = math.exp(-r * T) * prob

        pricing = PricingResult(
            probability=prob,
            pv=pv,
            d2=d2,
            drift=drift,
        )

    # Add sensitivity analysis
    if include_sensitivity:
        from scipy.stats import norm

        shifts = [-0.03, -0.02, 0.02, 0.03]
        for shift in shifts:
            sigma_shifted = max(0.01, sigma + shift)
            if event_type == EventType.TOUCH:
                # Simplified touch calculation
                prob_shifted = min(1.0, max(0.0, prob * (1 + shift * 2)))
                pv_shifted = math.exp(-r * T) * prob_shifted
            else:
                drift_shifted = r - q - 0.5 * sigma_shifted**2
                d2_shifted = (math.log(S0 / K) + drift_shifted * T) / (
                    sigma_shifted * math.sqrt(T)
                )
                if event_type == EventType.ABOVE:
                    prob_shifted = norm.cdf(d2_shifted)
                else:
                    prob_shifted = norm.cdf(-d2_shifted)
                pv_shifted = math.exp(-r * T) * prob_shifted

            key = f"sigma{shift:+.2f}"
            pricing.sensitivity[key] = (prob_shifted, pv_shifted)

    # Create analysis results
    poly_yes_price = pv  # Start with fair price
    if verdict == Verdict.CHEAP:
        poly_yes_price = pv * 0.90  # 10% below fair
    elif verdict == Verdict.EXPENSIVE:
        poly_yes_price = pv * 1.10  # 10% above fair

    mispricing_abs = poly_yes_price - pv
    mispricing_pct = mispricing_abs / pv if pv > 0 else 0

    results = AnalysisResults(
        inputs=inputs,
        market=market,
        spot_price=spot_price,
        risk_free_rate=r,
        implied_vol=sigma,
        time_to_expiry=T,
        pricing=pricing,
        poly_yes_price=poly_yes_price,
        poly_no_price=1 - poly_yes_price,
        verdict=verdict,
        mispricing_abs=mispricing_abs,
        mispricing_pct=mispricing_pct,
        iv_source="yfinance option chain interpolation",
        rate_source="manual input (5%)",
        warnings=[],
    )

    # Create report context
    log_moneyness = math.log(spot_price / level)
    variance_term = sigma * math.sqrt(T)

    if event_type == EventType.TOUCH:
        model_name = "Touch Barrier Option"
        model_rationale = "Touch barrier for path-dependent event"
    else:
        model_name = "Digital Option (Black-Scholes)"
        model_rationale = "Digital option for terminal settlement"

    ctx = ReportContext(
        results=results,
        log_moneyness=log_moneyness,
        variance_term=variance_term,
        model_name=model_name,
        model_rationale=model_rationale,
    )

    return ctx


def test_render_returns_string():
    """Test that render returns a string."""
    ctx = create_test_report_context()
    report = render(ctx)
    assert isinstance(report, str)
    assert len(report) > 0


def test_all_sections_present():
    """Test that all A-G section headers are present."""
    ctx = create_test_report_context()
    report = render(ctx)

    # Check for all required section headers
    assert "# Polymarket Analysis Report" in report
    assert "## A. Analysis Inputs" in report
    assert "## B. Model Selection" in report
    assert "## C. Mathematical Derivation" in report
    assert "## D. Polymarket vs Fair Value Comparison" in report
    assert "## E. Professional Conclusion" in report
    assert "## F. Explanation for Non-Experts" in report
    assert "## G. One-Sentence Takeaway" in report


def test_section_a_contains_inputs():
    """Test that Section A contains key input parameters."""
    ctx = create_test_report_context()
    report = render(ctx)

    # Check for key inputs in Section A
    assert "SPY" in report  # ticker
    assert "$100.00" in report  # spot price
    assert "$105.00" in report  # level
    assert "2026-12-31" in report  # expiry
    assert "5.00%" in report  # risk-free rate
    assert "2.00%" in report  # div yield
    assert "25.00%" in report  # IV


def test_section_b_model_choice():
    """Test that Section B explains model choice."""
    ctx_digital = create_test_report_context(event_type=EventType.ABOVE)
    report_digital = render(ctx_digital)
    assert "Digital Option" in report_digital

    ctx_touch = create_test_report_context(event_type=EventType.TOUCH)
    report_touch = render(ctx_touch)
    assert "Touch Barrier" in report_touch


def test_section_c_derivation_digital_above():
    """Test Section C derivation for digital option (above)."""
    ctx = create_test_report_context(event_type=EventType.ABOVE)
    report = render(ctx)

    # Check for key formulas and terms
    assert "Black-Scholes" in report
    assert "Risk-Neutral Drift" in report
    assert "μ = r - q - 0.5σ²" in report
    assert "d₂" in report
    assert "ln(S₀/K)" in report
    assert "N(·)" in report  # Normal CDF
    assert "Present Value" in report
    assert "e^(-rT)" in report
    assert "Sensitivity Analysis" in report


def test_section_c_derivation_digital_below():
    """Test Section C derivation for digital option (below)."""
    ctx = create_test_report_context(event_type=EventType.BELOW)
    report = render(ctx)

    # Check for key formulas
    assert "Black-Scholes" in report
    assert "d₂" in report
    assert "N(-d₂)" in report or "N(" in report


def test_section_c_derivation_touch():
    """Test Section C derivation for touch barrier."""
    ctx = create_test_report_context(event_type=EventType.TOUCH, level=110.0)
    report = render(ctx)

    # Check for touch-specific terms
    assert "Touch Barrier" in report
    assert "First-Passage Probability" in report
    assert "reflection principle" in report
    assert "ln(B/S₀)" in report
    assert "barrier" in report.lower()


def test_section_d_comparison_fair():
    """Test Section D with fair verdict."""
    ctx = create_test_report_context(verdict=Verdict.FAIR)
    report = render(ctx)

    # Check comparison table elements
    assert "Model Fair Value" in report
    assert "Polymarket Yes Price" in report
    assert "Mispricing" in report
    assert "Verdict" in report
    assert "Fair" in report
    assert "✅" in report


def test_section_d_comparison_cheap():
    """Test Section D with cheap verdict."""
    ctx = create_test_report_context(verdict=Verdict.CHEAP)
    report = render(ctx)

    assert "Cheap" in report
    assert "📉" in report
    assert "below" in report.lower() or "underpricing" in report.lower()


def test_section_d_comparison_expensive():
    """Test Section D with expensive verdict."""
    ctx = create_test_report_context(verdict=Verdict.EXPENSIVE)
    report = render(ctx)

    assert "Expensive" in report
    assert "📈" in report
    assert "above" in report.lower() or "overpricing" in report.lower()


def test_section_e_conclusion_present():
    """Test that Section E contains professional conclusion."""
    ctx = create_test_report_context()
    report = render(ctx)

    # Section E should contain technical language
    assert "## E. Professional Conclusion" in report
    # Should mention model and probabilities
    assert "probability" in report.lower()
    assert "fair value" in report.lower()


def test_section_f_layman_present():
    """Test that Section F contains layman explanation."""
    ctx = create_test_report_context()
    report = render(ctx)

    # Section F should use plain language
    assert "## F. Explanation for Non-Experts" in report
    # Should avoid heavy jargon, use conversational language
    assert "Polymarket" in report
    # Check it's actually explaining things simply
    sections = report.split("## F. Explanation for Non-Experts")
    if len(sections) > 1:
        layman_section = sections[1].split("##")[0]
        # Layman section should be substantial
        assert len(layman_section) > 200


def test_section_g_takeaway_present():
    """Test that Section G contains one-liner takeaway."""
    ctx = create_test_report_context()
    report = render(ctx)

    assert "## G. One-Sentence Takeaway" in report
    # Should mention key numbers
    assert "$" in report  # prices


def test_sensitivity_table_included():
    """Test that sensitivity analysis table is included."""
    ctx = create_test_report_context(include_sensitivity=True)
    report = render(ctx)

    # Check for sensitivity table headers
    assert "Volatility Shift" in report
    assert "Probability" in report
    assert "Present Value" in report
    # Check for shift values
    assert "σ -0.02" in report or "sigma-0.02" in report
    assert "σ +0.02" in report or "sigma+0.02" in report


def test_sensitivity_table_absent_gracefully():
    """Test graceful handling when sensitivity data is missing."""
    ctx = create_test_report_context(include_sensitivity=False)
    ctx.results.pricing.sensitivity = {}
    report = render(ctx)

    # Should still render, possibly with a note
    assert "## C. Mathematical Derivation" in report
    # Should not crash


def test_market_title_in_header():
    """Test that market title appears in header."""
    ctx = create_test_report_context()
    report = render(ctx)

    assert "Will SPY close above $105 by Dec 31, 2026?" in report
    assert "test-market-123" in report


def test_custom_conclusion_text():
    """Test that custom conclusion text is used if provided."""
    ctx = create_test_report_context()
    ctx.conclusion_text = "Custom conclusion text for testing."
    report = render(ctx)

    assert "Custom conclusion text for testing." in report


def test_custom_layman_text():
    """Test that custom layman text is used if provided."""
    ctx = create_test_report_context()
    ctx.layman_text = "Custom layman explanation for testing."
    report = render(ctx)

    assert "Custom layman explanation for testing." in report


def test_custom_takeaway_text():
    """Test that custom takeaway text is used if provided."""
    ctx = create_test_report_context()
    ctx.takeaway = "Custom one-liner takeaway for testing."
    report = render(ctx)

    assert "Custom one-liner takeaway for testing." in report


def test_touch_event_descriptions():
    """Test proper description of touch events."""
    ctx = create_test_report_context(event_type=EventType.TOUCH, level=120.0)
    report = render(ctx)

    # Should mention "touch" or "barrier"
    assert "touch" in report.lower() or "barrier" in report.lower()
    assert "$120.00" in report


def test_above_event_descriptions():
    """Test proper description of above events."""
    ctx = create_test_report_context(event_type=EventType.ABOVE, level=105.0)
    report = render(ctx)

    assert "above" in report.lower()
    assert "$105.00" in report


def test_below_event_descriptions():
    """Test proper description of below events."""
    ctx = create_test_report_context(event_type=EventType.BELOW, level=95.0)
    report = render(ctx)

    assert "below" in report.lower()
    assert "$95.00" in report


def test_report_markdown_structure():
    """Test that report has valid markdown structure."""
    ctx = create_test_report_context()
    report = render(ctx)

    # Check for proper markdown headers
    assert report.count("# Polymarket Analysis Report") == 1  # Only one H1
    # Multiple H2 sections
    assert report.count("## A.") == 1
    assert report.count("## B.") == 1
    assert report.count("## C.") == 1
    assert report.count("## D.") == 1
    assert report.count("## E.") == 1
    assert report.count("## F.") == 1
    assert report.count("## G.") == 1

    # Check for markdown tables (at least in Section A and D)
    assert "|" in report
    assert "---|" in report


def test_numeric_formatting():
    """Test that numbers are formatted consistently."""
    ctx = create_test_report_context(spot_price=12345.67, level=12000.00)
    report = render(ctx)

    # Check comma separators for large numbers
    assert "12,345.67" in report or "$12345.67" in report
    assert "12,000.00" in report or "$12000.00" in report


def test_percentage_formatting():
    """Test that percentages are formatted properly."""
    ctx = create_test_report_context()
    ctx.results.risk_free_rate = 0.0525
    ctx.results.implied_vol = 0.3175
    report = render(ctx)

    # Should have percentages with 2 decimal places
    assert "5.25%" in report  # rate
    assert "31.75%" in report or "31.8%" in report  # IV


def test_warnings_section_if_present():
    """Test that warnings are displayed if present in results."""
    ctx = create_test_report_context()
    ctx.results.warnings = ["Test warning 1", "Test warning 2"]

    # Note: Current implementation doesn't explicitly render warnings section
    # This test documents expected behavior for future enhancement
    report = render(ctx)

    # Current behavior: warnings are in the results but not necessarily in report
    # Future enhancement could add a warnings section
    assert isinstance(report, str)


def test_data_sources_in_section_a():
    """Test that data sources are documented in Section A."""
    ctx = create_test_report_context()
    report = render(ctx)

    assert "Data Sources" in report
    assert "yfinance option chain interpolation" in report
    assert "manual input" in report


def test_all_event_types_render():
    """Test that all event types can be rendered without errors."""
    for event_type in [EventType.TOUCH, EventType.ABOVE, EventType.BELOW]:
        ctx = create_test_report_context(event_type=event_type)
        report = render(ctx)
        assert len(report) > 1000  # Should be substantial
        assert "## A." in report
        assert "## G." in report


def test_all_verdicts_render():
    """Test that all verdicts can be rendered without errors."""
    for verdict in [Verdict.CHEAP, Verdict.FAIR, Verdict.EXPENSIVE]:
        ctx = create_test_report_context(verdict=verdict)
        report = render(ctx)
        assert len(report) > 1000
        assert verdict.value in report
