"""Explainability plots for reports and slide decks.

These images are a convenience for humans reviewing the model. The frontend does
**not** consume them: the API will serve the structured JSON produced by
``explainer.explain_customer`` instead.

Plots are drawn on the aggregated *original* features (19 of them) rather than
the 45 transformed columns, because a chart with "Contract_One year" and
"Contract_Two year" as separate bars is far harder to read than one "Contract"
bar carrying the feature's total contribution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

# Non-interactive backend: plots are written to files, never displayed, so this
# works on headless machines and in CI.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (import must follow backend selection)
import pandas as pd  # noqa: E402

from ml.src import config  # noqa: E402
from ml.src.logging_config import get_logger  # noqa: E402

logger = get_logger(__name__)

EXPLANATIONS_DIRNAME = "explanations"

COLOR_INCREASES_RISK = "#c0392b"  # red — pushes the customer toward churn
COLOR_DECREASES_RISK = "#27ae60"  # green — protects against churn


def get_explanations_dir(models_dir: Path | None = None) -> Path:
    """Return (and create) the directory that holds generated plots."""
    base_dir = Path(models_dir) if models_dir else config.MODELS_DIR
    output_dir = base_dir / EXPLANATIONS_DIRNAME
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def plot_global_importance(
    report: pd.DataFrame,
    top_n: int = 15,
    models_dir: Path | None = None,
    filename: str = "global_feature_importance.png",
) -> Path:
    """Horizontal bar chart of the most influential features overall.

    Args:
        report: Output of ``compute_global_importance``.
        top_n: How many features to show.
    """
    top_features = report.head(top_n).iloc[::-1]  # reversed so the top bar is largest

    figure, axes = plt.subplots(figsize=(9, 0.42 * len(top_features) + 2))
    axes.barh(
        top_features["feature"],
        top_features["mean_absolute_shap"],
        color="#2c6fbb",
    )
    axes.set_xlabel("Mean |SHAP value|  (log-odds)")
    axes.set_title("Global feature importance — what drives churn overall")
    axes.grid(axis="x", alpha=0.3)
    figure.tight_layout()

    output_path = get_explanations_dir(models_dir) / filename
    figure.savefig(output_path, dpi=150)
    plt.close(figure)

    logger.debug("Wrote global importance plot to %s", output_path)
    return output_path


def plot_customer_explanation(
    explanation: dict[str, Any],
    models_dir: Path | None = None,
    filename: str | None = None,
) -> Path:
    """Bar chart of one customer's top churn drivers, coloured by direction.

    Args:
        explanation: Output of ``ChurnExplainer.explain``.
    """
    drivers = explanation.get("top_drivers", [])
    if not drivers:
        raise ValueError("Explanation contains no drivers to plot.")

    # Reversed so the strongest driver sits at the top of the chart.
    ordered_drivers = list(reversed(drivers))
    labels = [
        f"{driver['feature']} = {driver['value']}" for driver in ordered_drivers
    ]
    contributions = [driver["shap_value"] for driver in ordered_drivers]
    colors = [
        COLOR_INCREASES_RISK if driver["direction"] == "increases_risk" else COLOR_DECREASES_RISK
        for driver in ordered_drivers
    ]

    figure, axes = plt.subplots(figsize=(9, 0.55 * len(labels) + 2.4))
    axes.barh(labels, contributions, color=colors)
    axes.axvline(0, color="#444444", linewidth=0.8)
    axes.set_xlabel("SHAP contribution to churn log-odds  (right = higher risk)")

    customer_id = explanation.get("customer_id") or "customer"
    axes.set_title(
        f"Why {customer_id} is {explanation.get('risk_level', 'UNKNOWN')} risk — "
        f"churn probability {explanation.get('churn_probability', float('nan')):.2%}"
    )
    axes.grid(axis="x", alpha=0.3)
    figure.tight_layout()

    safe_id = str(customer_id).replace("/", "-").replace("\\", "-")
    output_path = get_explanations_dir(models_dir) / (filename or f"customer_{safe_id}.png")
    figure.savefig(output_path, dpi=150)
    plt.close(figure)

    logger.debug("Wrote customer explanation plot to %s", output_path)
    return output_path
