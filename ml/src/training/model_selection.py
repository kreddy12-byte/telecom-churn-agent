"""Candidate model definitions and the best-model selection strategy.

Selection strategy
------------------
A churn model that misses an at-risk customer costs a full customer lifetime;
a false positive costs one unnecessary retention offer. Accuracy alone rewards
predicting "no churn" for everyone (~73% on this dataset), so it is reported but
never used to pick the winner.

The winner maximises a weighted score::

    score = 0.45 * F1 + 0.35 * Recall + 0.20 * ROC AUC

F1 keeps precision honest, recall encodes the asymmetric business cost, and
ROC AUC rewards well-ranked probabilities, which matter because downstream
retention logic bands customers into LOW/MEDIUM/HIGH risk.

The score is computed from **5-fold cross-validated scores on the training
split**, never from the test set. Averaging over folds also favours models that
are stable rather than lucky on one split. The held-out test set is used solely
to report the final performance of the model that was already chosen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier

from ml.src import config
from ml.src.logging_config import get_logger

logger = get_logger(__name__)

try:  # XGBoost is an optional import so the pipeline degrades loudly, not silently.
    from xgboost import XGBClassifier

    XGBOOST_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    XGBClassifier = None  # type: ignore[assignment]
    XGBOOST_AVAILABLE = False


@dataclass
class ModelSelection:
    """Outcome of the selection strategy."""

    model_name: str
    selection_score: float
    reason: str
    ranking: list[dict[str, Any]]
    scored_on: str = "cross_validation"


def compute_scale_pos_weight(n_negative: int, n_positive: int) -> float:
    """Ratio used by XGBoost to compensate for class imbalance."""
    if n_positive <= 0:
        raise ValueError("Cannot compute scale_pos_weight without positive samples.")
    return float(n_negative) / float(n_positive)


def get_candidate_models(scale_pos_weight: float | None = None) -> dict[str, Any]:
    """Return the candidate estimators with sensible baseline hyperparameters.

    Class imbalance is handled with ``class_weight="balanced"`` where the
    estimator supports it and ``scale_pos_weight`` for XGBoost. KNN and Gaussian
    Naive Bayes support neither; they are trained unweighted and that limitation
    is recorded in the comparison report rather than being papered over with
    synthetic oversampling.
    """
    models: dict[str, Any] = {
        "LogisticRegression": LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=config.RANDOM_STATE,
        ),
        "DecisionTree": DecisionTreeClassifier(
            max_depth=6,
            min_samples_leaf=20,
            class_weight="balanced",
            random_state=config.RANDOM_STATE,
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=300,
            max_depth=12,
            min_samples_leaf=5,
            class_weight="balanced",
            n_jobs=-1,
            random_state=config.RANDOM_STATE,
        ),
        "KNeighbors": KNeighborsClassifier(n_neighbors=25, weights="distance"),
        "GaussianNB": GaussianNB(),
    }

    if XGBOOST_AVAILABLE:
        models["XGBoost"] = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            eval_metric="logloss",
            scale_pos_weight=scale_pos_weight or 1.0,
            n_jobs=-1,
            random_state=config.RANDOM_STATE,
        )
    else:
        logger.error(
            "xgboost is not installed — the XGBoost candidate will be skipped. "
            "Install it with `pip install xgboost` to train the full model set."
        )

    return models


def models_without_class_weighting() -> set[str]:
    """Candidates that cannot apply class weights."""
    return {"KNeighbors", "GaussianNB"}


def compute_selection_score(metrics: dict[str, float]) -> float:
    """Weighted score used to rank models."""
    return float(
        sum(weight * float(metrics.get(name, 0.0)) for name, weight in config.SELECTION_WEIGHTS.items())
    )


def _selection_metrics(result: Any) -> tuple[dict[str, float], bool]:
    """Return the metrics a model is scored on, preferring cross-validation.

    Falls back to test-set metrics only when cross-validation was skipped
    (``train --no-cv``); the fallback is flagged so it can be reported.
    """
    if result.cv_f1_mean is not None and result.cv_roc_auc_mean is not None:
        return (
            {
                "f1": result.cv_f1_mean,
                "recall": result.cv_recall_mean if result.cv_recall_mean is not None else result.recall,
                "roc_auc": result.cv_roc_auc_mean,
            },
            True,
        )
    return {"f1": result.f1, "recall": result.recall, "roc_auc": result.roc_auc}, False


def select_best_model(results: list[Any]) -> ModelSelection:
    """Pick the winning model from a list of :class:`ModelEvaluation` objects.

    Ranking uses cross-validated training scores so the test set stays untouched
    until final reporting. Ties break on recall, then ROC AUC, then on faster
    inference.
    """
    if not results:
        raise ValueError("Cannot select a best model from an empty result list.")

    used_cv = True
    scored: dict[str, dict[str, float]] = {}
    for result in results:
        metrics, from_cv = _selection_metrics(result)
        used_cv = used_cv and from_cv
        scored[result.model_name] = metrics
        result.selection_score = compute_selection_score(metrics)

    ranked = sorted(
        results,
        key=lambda item: (
            item.selection_score,
            scored[item.model_name]["recall"],
            scored[item.model_name]["roc_auc"],
            -item.inference_time_seconds,
        ),
        reverse=True,
    )
    winner = ranked[0]
    winner_metrics = scored[winner.model_name]

    weights = config.SELECTION_WEIGHTS
    basis = (
        f"{config.CV_FOLDS}-fold cross-validation on the training split"
        if used_cv
        else "held-out test metrics (cross-validation was skipped)"
    )
    reason = (
        f"{winner.model_name} achieved the highest weighted selection score "
        f"({winner.selection_score:.4f}) computed as "
        f"{weights['f1']}*F1 + {weights['recall']}*Recall + {weights['roc_auc']}*ROC_AUC "
        f"over {basis} (F1={winner_metrics['f1']:.4f}, Recall={winner_metrics['recall']:.4f}, "
        f"ROC_AUC={winner_metrics['roc_auc']:.4f}). Recall and F1 dominate the score because a "
        f"missed churner is more costly than an unnecessary retention offer; accuracy was "
        f"deliberately excluded because the majority class is ~73% of the data. On the untouched "
        f"test set this model scores F1={winner.f1:.4f}, Recall={winner.recall:.4f}, "
        f"ROC_AUC={winner.roc_auc:.4f}, Accuracy={winner.accuracy:.4f}."
    )

    if len(ranked) > 1:
        runner_up = ranked[1]
        reason += (
            f" Runner-up was {runner_up.model_name} (score={runner_up.selection_score:.4f})."
        )

    return ModelSelection(
        model_name=winner.model_name,
        selection_score=float(winner.selection_score),
        reason=reason,
        scored_on="cross_validation" if used_cv else "test_set",
        ranking=[
            {
                "model_name": result.model_name,
                "selection_score": result.selection_score,
                "scored_f1": scored[result.model_name]["f1"],
                "scored_recall": scored[result.model_name]["recall"],
                "scored_roc_auc": scored[result.model_name]["roc_auc"],
                "test_f1": result.f1,
                "test_recall": result.recall,
                "test_roc_auc": result.roc_auc,
                "test_accuracy": result.accuracy,
            }
            for result in ranked
        ],
    )
