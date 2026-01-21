"""Markdown report generator for A-G analysis sections.

This module generates comprehensive markdown reports that include:
- Section A: Input summary table
- Section B: Model choice explanation
- Section C: Full derivation with formulas
- Section D: Fair vs Polymarket comparison table
- Section E: Professional conclusion
- Section F: Layman explanation
- Section G: One-liner takeaway
"""

from polyarb.models import ReportContext, EventType, Verdict


def render(ctx: ReportContext) -> str:
    """Generate complete A-G markdown report from ReportContext.

    Args:
        ctx: ReportContext containing all analysis data

    Returns:
        Markdown-formatted report string with sections A-G
    """
    sections = [
        _render_header(ctx),
        _render_section_a_inputs(ctx),
        _render_section_b_model_choice(ctx),
        _render_section_c_derivation(ctx),
        _render_section_d_comparison(ctx),
        _render_section_e_conclusion(ctx),
        _render_section_f_layman(ctx),
        _render_section_g_takeaway(ctx),
    ]

    return "\n\n".join(sections)


def _render_header(ctx: ReportContext) -> str:
    """Render report header with market title."""
    market = ctx.results.market
    return f"""# Polymarket Analysis Report

**Market:** {market.title}

**Market ID:** {market.id}

**Analysis Date:** {ctx.results.market.end_date.strftime('%Y-%m-%d')}"""


def _render_section_a_inputs(ctx: ReportContext) -> str:
    """Section A: Input summary table."""
    r = ctx.results
    inputs = r.inputs

    # Format event type description
    if inputs.event_type == EventType.TOUCH:
        event_desc = f"Touch barrier at ${inputs.level:,.2f}"
    elif inputs.event_type == EventType.ABOVE:
        event_desc = f"Settle above ${inputs.level:,.2f}"
    else:  # BELOW
        event_desc = f"Settle below ${inputs.level:,.2f}"

    return f"""## A. Analysis Inputs

| Parameter | Value |
|-----------|-------|
| **Underlying Ticker** | {inputs.ticker} |
| **Spot Price (S₀)** | ${r.spot_price:,.2f} |
| **Event Type** | {event_desc} |
| **Strike/Barrier Level (K/B)** | ${inputs.level:,.2f} |
| **Expiry Date** | {inputs.expiry.strftime('%Y-%m-%d')} |
| **Time to Expiry (T)** | {r.time_to_expiry:.4f} years |
| **Risk-Free Rate (r)** | {r.risk_free_rate * 100:.2f}% |
| **Dividend Yield (q)** | {inputs.div_yield * 100:.2f}% |
| **Implied Volatility (σ)** | {r.implied_vol * 100:.2f}% |
| **Polymarket Yes Price** | ${r.poly_yes_price:.4f} |
| **Polymarket No Price** | ${r.poly_no_price:.4f} |

**Data Sources:**
- Implied Volatility: {r.iv_source}
- Risk-Free Rate: {r.rate_source}"""


def _render_section_b_model_choice(ctx: ReportContext) -> str:
    """Section B: Model choice explanation."""
    model_rationale = ctx.model_rationale or _generate_default_rationale(ctx)

    return f"""## B. Model Selection

**Selected Model:** {ctx.model_name}

**Rationale:**

{model_rationale}"""


def _generate_default_rationale(ctx: ReportContext) -> str:
    """Generate default model rationale based on event type."""
    event_type = ctx.results.inputs.event_type

    if event_type == EventType.TOUCH:
        return """A touch barrier option is appropriate for this event because the payout occurs if the underlying asset reaches or crosses the barrier level at any point before expiry. This is a path-dependent option that requires monitoring the entire price trajectory, not just the terminal value.

We use the geometric Brownian motion (GBM) first-passage probability formula with the reflection principle to compute the probability that the barrier is hit before expiry. The risk-neutral drift μ = r - q - 0.5σ² accounts for the risk-free rate, dividend yield, and volatility drag."""

    elif event_type == EventType.ABOVE:
        return """A digital call option (cash-or-nothing) is appropriate for this event because the payout depends solely on whether the underlying asset is above the strike level at expiry. This is a terminal-settle option that only depends on the final price, not the path taken.

We use the Black-Scholes framework to compute the risk-neutral probability that S_T > K at expiry. The standard d₂ parameter captures the adjusted log-return distribution under the risk-neutral measure."""

    else:  # BELOW
        return """A digital put option (cash-or-nothing) is appropriate for this event because the payout depends solely on whether the underlying asset is below the strike level at expiry. This is a terminal-settle option that only depends on the final price, not the path taken.

We use the Black-Scholes framework to compute the risk-neutral probability that S_T < K at expiry. The standard d₂ parameter captures the adjusted log-return distribution under the risk-neutral measure."""


def _render_section_c_derivation(ctx: ReportContext) -> str:
    """Section C: Full derivation with formulas and intermediate values."""
    r = ctx.results
    event_type = r.inputs.event_type

    if event_type == EventType.TOUCH:
        return _render_touch_derivation(ctx)
    else:
        return _render_digital_derivation(ctx)


def _render_digital_derivation(ctx: ReportContext) -> str:
    """Render derivation for digital (terminal) options."""
    r = ctx.results
    inputs = r.inputs
    pricing = r.pricing

    # Determine direction
    direction = "above" if inputs.event_type == EventType.ABOVE else "below"

    # Compute intermediate values
    S0 = r.spot_price
    K = inputs.level
    T = r.time_to_expiry
    r_rate = r.risk_free_rate
    q = inputs.div_yield
    sigma = r.implied_vol

    log_moneyness = ctx.log_moneyness
    drift = pricing.drift
    d2 = pricing.d2
    prob = pricing.probability
    pv = pricing.pv
    discount_factor = pv / prob if prob > 0 else 0

    return f"""## C. Mathematical Derivation

### Black-Scholes Digital Option Framework

For a digital option that pays $1 if S_T {">=" if direction == "above" else "<="} K at expiry:

**1. Risk-Neutral Drift:**

The risk-neutral drift accounts for the cost of carry:

```
μ = r - q - 0.5σ²
  = {r_rate:.6f} - {q:.6f} - 0.5 × {sigma:.6f}²
  = {drift:.6f}
```

**2. Standardized Log-Return (d₂):**

The d₂ parameter measures how many standard deviations the forward price is from the strike:

```
d₂ = [ln(S₀/K) + μT] / (σ√T)
   = [ln({S0:.2f}/{K:.2f}) + {drift:.6f} × {T:.4f}] / ({sigma:.6f} × √{T:.4f})
   = [{log_moneyness:.6f} + {drift * T:.6f}] / {ctx.variance_term:.6f}
   = {d2:.6f}
```

**3. Risk-Neutral Probability:**

The probability that S_T {">=" if direction == "above" else "<="} K is:

```
P(S_T {">=" if direction == "above" else "<="} K) = N({"" if direction == "above" else "-"}d₂)
                  = N({d2 if direction == "above" else -d2:.6f})
                  = {prob:.6f}
```

where N(·) is the standard normal cumulative distribution function.

**4. Present Value:**

The fair value is the discounted expected payout:

```
PV = e^(-rT) × P(event)
   = e^(-{r_rate:.6f} × {T:.4f}) × {prob:.6f}
   = {discount_factor:.6f} × {prob:.6f}
   = {pv:.6f}
```

### Sensitivity Analysis

The fair value varies with implied volatility:

{_render_sensitivity_table(pricing)}"""


def _render_touch_derivation(ctx: ReportContext) -> str:
    """Render derivation for touch barrier options."""
    r = ctx.results
    inputs = r.inputs
    pricing = r.pricing

    # Compute intermediate values
    S0 = r.spot_price
    B = inputs.level
    T = r.time_to_expiry
    r_rate = r.risk_free_rate
    q = inputs.div_yield
    sigma = r.implied_vol

    a = ctx.log_moneyness  # ln(B/S0)
    drift = pricing.drift
    prob = pricing.probability
    pv = pricing.pv
    discount_factor = pv / prob if prob > 0 else 0

    # Determine barrier direction
    barrier_direction = "upper" if B > S0 else "lower"

    return f"""## C. Mathematical Derivation

### Touch Barrier Option Framework

For a barrier option that pays $1 if the price touches B = ${B:,.2f} before expiry:

**1. Risk-Neutral Drift:**

The risk-neutral drift for geometric Brownian motion:

```
μ = r - q - 0.5σ²
  = {r_rate:.6f} - {q:.6f} - 0.5 × {sigma:.6f}²
  = {drift:.6f}
```

**2. Log-Distance to Barrier:**

The log-distance from spot to barrier ({barrier_direction} barrier):

```
a = ln(B/S₀)
  = ln({B:.2f}/{S0:.2f})
  = {a:.6f}
```

**3. First-Passage Probability:**

Using the reflection principle for drifted Brownian motion, the probability of hitting the barrier is:

```
λ = μ / σ² = {drift:.6f} / {sigma:.6f}² = {drift / (sigma ** 2):.6f}

P(hit) = N(-[a - μT] / [σ√T]) + e^(2λa) × N(-[a + μT] / [σ√T])
```

Computing each term:
```
Term 1: N(-[{a:.6f} - {drift * T:.6f}] / {ctx.variance_term:.6f}) = N({-(a - drift * T) / ctx.variance_term:.6f})
Term 2: e^(2 × {drift / (sigma ** 2):.6f} × {a:.6f}) × N(-[{a:.6f} + {drift * T:.6f}] / {ctx.variance_term:.6f})

P(hit) = {prob:.6f}
```

**4. Present Value:**

The fair value is the discounted expected payout:

```
PV = e^(-rT) × P(hit)
   = e^(-{r_rate:.6f} × {T:.4f}) × {prob:.6f}
   = {discount_factor:.6f} × {prob:.6f}
   = {pv:.6f}
```

### Sensitivity Analysis

The fair value varies with implied volatility:

{_render_sensitivity_table(pricing)}"""


def _render_sensitivity_table(pricing) -> str:
    """Render sensitivity analysis table."""
    if not pricing.sensitivity:
        return "*Sensitivity analysis not available.*"

    lines = ["| Volatility Shift | Probability | Present Value |",
             "|------------------|-------------|---------------|"]

    # Sort by shift amount
    shifts = sorted(pricing.sensitivity.items(), key=lambda x: float(x[0].replace("sigma", "")))

    for shift_key, (prob, pv) in shifts:
        # Parse shift key like "sigma-0.02" or "sigma+0.03"
        shift_str = shift_key.replace("sigma", "σ ")
        lines.append(f"| {shift_str:16s} | {prob:11.6f} | {pv:13.6f} |")

    return "\n".join(lines)


def _render_section_d_comparison(ctx: ReportContext) -> str:
    """Section D: Fair vs Polymarket comparison table with verdict."""
    r = ctx.results

    verdict_emoji = {
        Verdict.CHEAP: "📉",
        Verdict.FAIR: "✅",
        Verdict.EXPENSIVE: "📈"
    }

    emoji = verdict_emoji.get(r.verdict, "")

    return f"""## D. Polymarket vs Fair Value Comparison

| Metric | Value |
|--------|-------|
| **Model Fair Value (PV)** | ${r.pricing.pv:.6f} |
| **Polymarket Yes Price** | ${r.poly_yes_price:.6f} |
| **Absolute Mispricing** | ${r.mispricing_abs:+.6f} |
| **Percentage Mispricing** | {r.mispricing_pct * 100:+.2f}% |
| **Verdict** | **{r.verdict.value}** {emoji} |

### Interpretation

{_render_verdict_explanation(ctx)}"""


def _render_verdict_explanation(ctx: ReportContext) -> str:
    """Generate explanation for the verdict."""
    r = ctx.results
    inputs = r.inputs

    if r.verdict == Verdict.CHEAP:
        return f"""The Polymarket Yes token is trading **below** its model fair value by ${abs(r.mispricing_abs):.6f} ({abs(r.mispricing_pct) * 100:.2f}%). This suggests the market may be underpricing the event probability relative to the options-implied risk-neutral measure.

Based on the configured tolerances (absolute: ${inputs.abs_tol:.2f}, percentage: {inputs.pct_tol * 100:.1f}%), the market price is considered **Cheap** relative to the model fair value."""

    elif r.verdict == Verdict.EXPENSIVE:
        return f"""The Polymarket Yes token is trading **above** its model fair value by ${abs(r.mispricing_abs):.6f} ({abs(r.mispricing_pct) * 100:.2f}%). This suggests the market may be overpricing the event probability relative to the options-implied risk-neutral measure.

Based on the configured tolerances (absolute: ${inputs.abs_tol:.2f}, percentage: {inputs.pct_tol * 100:.1f}%), the market price is considered **Expensive** relative to the model fair value."""

    else:  # FAIR
        diff = abs(r.mispricing_abs)
        pct_diff = abs(r.mispricing_pct) * 100
        return f"""The Polymarket Yes token is trading **within tolerance** of its model fair value (difference: ${diff:.6f}, {pct_diff:.2f}%). The market price and model fair value are reasonably aligned.

Based on the configured tolerances (absolute: ${inputs.abs_tol:.2f}, percentage: {inputs.pct_tol * 100:.1f}%), the market price is considered **Fair** relative to the model fair value."""


def _render_section_e_conclusion(ctx: ReportContext) -> str:
    """Section E: Professional one-paragraph conclusion."""
    conclusion = ctx.conclusion_text or _generate_default_conclusion(ctx)

    return f"""## E. Professional Conclusion

{conclusion}"""


def _generate_default_conclusion(ctx: ReportContext) -> str:
    """Generate default professional conclusion."""
    r = ctx.results
    inputs = r.inputs

    # Event description
    if inputs.event_type == EventType.TOUCH:
        event_desc = f"touches ${inputs.level:,.2f}"
    elif inputs.event_type == EventType.ABOVE:
        event_desc = f"settles above ${inputs.level:,.2f}"
    else:
        event_desc = f"settles below ${inputs.level:,.2f}"

    # Model name
    model = "barrier option" if inputs.event_type == EventType.TOUCH else "digital option"

    # Verdict description
    if r.verdict == Verdict.CHEAP:
        verdict_desc = f"undervalued by approximately {abs(r.mispricing_pct) * 100:.1f}%"
        action = "suggesting a potential buying opportunity"
    elif r.verdict == Verdict.EXPENSIVE:
        verdict_desc = f"overvalued by approximately {abs(r.mispricing_pct) * 100:.1f}%"
        action = "suggesting caution for buyers"
    else:
        verdict_desc = "fairly priced"
        action = "indicating efficient market pricing"

    return f"""Based on {model} pricing using {r.implied_vol * 100:.1f}% implied volatility sourced from {r.iv_source} and a {r.risk_free_rate * 100:.2f}% risk-free rate, the model fair value for the event "{inputs.ticker} {event_desc} by {inputs.expiry.strftime('%Y-%m-%d')}" is ${r.pricing.pv:.4f}. The Polymarket Yes token is currently trading at ${r.poly_yes_price:.4f}, indicating the market price is {verdict_desc} relative to the options-implied risk-neutral probability of {r.pricing.probability * 100:.2f}%. This analysis uses standard quantitative finance techniques to derive a risk-neutral fair value, {action}. However, investors should note that model assumptions (e.g., log-normal returns, constant volatility) may not perfectly capture real-world dynamics, and Polymarket prices may reflect information or risk preferences not captured in the model."""


def _render_section_f_layman(ctx: ReportContext) -> str:
    """Section F: Layman explanation without jargon."""
    layman = ctx.layman_text or _generate_default_layman(ctx)

    return f"""## F. Explanation for Non-Experts

{layman}"""


def _generate_default_layman(ctx: ReportContext) -> str:
    """Generate default layman explanation."""
    r = ctx.results
    inputs = r.inputs

    # Event description
    if inputs.event_type == EventType.TOUCH:
        event_desc = f"the price of {inputs.ticker} reaches ${inputs.level:,.2f} at any point"
    elif inputs.event_type == EventType.ABOVE:
        event_desc = f"{inputs.ticker} is above ${inputs.level:,.2f} on {inputs.expiry.strftime('%B %d, %Y')}"
    else:
        event_desc = f"{inputs.ticker} is below ${inputs.level:,.2f} on {inputs.expiry.strftime('%B %d, %Y')}"

    # Verdict in plain language
    if r.verdict == Verdict.CHEAP:
        verdict_plain = "cheaper than it should be"
        implication = "This might be a good opportunity to buy Yes tokens if you believe the model is correct."
    elif r.verdict == Verdict.EXPENSIVE:
        verdict_plain = "more expensive than it should be"
        implication = "This suggests caution—you might be paying too much for Yes tokens."
    else:
        verdict_plain = "priced about right"
        implication = "The market price is reasonably aligned with what the model thinks it should be."

    return f"""This analysis looks at a Polymarket prediction market and tries to figure out if the current price makes sense compared to what options traders in the traditional financial markets are implicitly betting.

**What's the bet?** The Polymarket question is about whether {event_desc}.

**What's the current price?** On Polymarket, a Yes token (which pays $1 if the event happens) is trading at ${r.poly_yes_price:.4f}. This means the market thinks there's roughly a {r.poly_yes_price * 100:.1f}% chance the event will occur.

**What does the model say?** By looking at how options traders are pricing similar bets in traditional markets (using something called "implied volatility"), we can calculate what the "fair" price should be under certain assumptions. The model says the fair price is ${r.pricing.pv:.4f}, which corresponds to a {r.pricing.probability * 100:.1f}% probability.

**What's the difference?** The Polymarket price is currently {verdict_plain}. {implication}

**Important caveat:** This model makes simplifying assumptions (like assuming prices move in a specific mathematical way) and uses data from traditional options markets. Real-world events might behave differently than the model predicts, and Polymarket traders might have information or perspectives that aren't captured in the model. Always do your own research before making any trading decisions."""


def _render_section_g_takeaway(ctx: ReportContext) -> str:
    """Section G: One-liner takeaway with key numbers."""
    takeaway = ctx.takeaway or _generate_default_takeaway(ctx)

    return f"""## G. One-Sentence Takeaway

**{takeaway}**"""


def _generate_default_takeaway(ctx: ReportContext) -> str:
    """Generate default one-liner takeaway."""
    r = ctx.results

    if r.verdict == Verdict.CHEAP:
        direction = "undervalued"
        emoji = "📉"
    elif r.verdict == Verdict.EXPENSIVE:
        direction = "overvalued"
        emoji = "📈"
    else:
        direction = "fairly valued"
        emoji = "✅"

    return f"The Polymarket Yes token at ${r.poly_yes_price:.4f} is {direction} compared to the model fair value of ${r.pricing.pv:.4f} (implied probability: {r.pricing.probability * 100:.1f}%). {emoji}"
