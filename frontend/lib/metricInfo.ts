// Short, plain-language descriptions shown as info tooltips next to each metric.
export const METRIC_INFO = {
  alpha:
    "Excess return versus the Nifty 50 benchmark after adjusting for market risk. Positive alpha means the fund beat the market on a risk-adjusted basis.",
  beta:
    "Sensitivity to market movements. Beta above 1 means the fund swings more than the market; below 1 means it's steadier.",
  sharpe:
    "Return earned per unit of total risk (volatility), annualised. Higher is better — more reward for the bumpiness.",
  sortino:
    "Like Sharpe, but only penalises downside volatility. Higher is better — it ignores 'good' upside swings.",
  treynor:
    "Annualised excess return per unit of market risk (beta), shown as a %. Higher means you're better rewarded for the market risk taken.",
  maxDrawdown:
    "The largest peak-to-trough fall in NAV over the period. Closer to 0 is better — it shows the worst loss you'd have ridden through.",
  expense:
    "Annual fee the fund charges as a % of assets. Lower is better. Sourced from the fund factsheet — not available from the NAV feed yet.",
  turnover:
    "How often the fund replaces its holdings in a year. High turnover can mean higher trading costs. From the fund factsheet — not available from the NAV feed yet.",
} as const;
