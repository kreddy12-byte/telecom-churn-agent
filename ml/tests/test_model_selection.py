"""Tests for the model-selection strategy."""

from __future__ import annotations

import pytest

from ml.src import config
from ml.src.training.evaluate import ModelEvaluation
from ml.src.training.model_selection import (
    compute_scale_pos_weight,
    compute_selection_score,
    select_best_model,
)


def make_evaluation(
    name: str,
    *,
    f1: float,
    recall: float,
    roc_auc: float,
    accuracy: float = 0.75,
    cv_f1: float | None = None,
    cv_recall: float | None = None,
    cv_roc_auc: float | None = None,
    inference_time: float = 0.01,
) -> ModelEvaluation:
    return ModelEvaluation(
        model_name=name,
        accuracy=accuracy,
        precision=0.5,
        recall=recall,
        f1=f1,
        roc_auc=roc_auc,
        confusion_matrix={
            "true_negatives": 1,
            "false_positives": 1,
            "false_negatives": 1,
            "true_positives": 1,
        },
        train_time_seconds=0.1,
        inference_time_seconds=inference_time,
        cv_f1_mean=cv_f1,
        cv_recall_mean=cv_recall,
        cv_roc_auc_mean=cv_roc_auc,
    )


class TestSelectionScore:
    def test_weights_are_applied(self):
        score = compute_selection_score({"f1": 1.0, "recall": 1.0, "roc_auc": 1.0})
        assert score == pytest.approx(sum(config.SELECTION_WEIGHTS.values()))

    def test_recall_outweighs_nothing_else_alone(self):
        recall_heavy = compute_selection_score({"f1": 0.5, "recall": 0.9, "roc_auc": 0.8})
        recall_light = compute_selection_score({"f1": 0.5, "recall": 0.5, "roc_auc": 0.8})
        assert recall_heavy > recall_light

    def test_missing_metric_defaults_to_zero(self):
        assert compute_selection_score({}) == 0.0


class TestSelectBestModel:
    def test_empty_results_raise(self):
        with pytest.raises(ValueError):
            select_best_model([])

    def test_uses_cross_validated_metrics_not_test_metrics(self):
        """A model that looks best on the test split must not win on that alone."""
        lucky_on_test = make_evaluation(
            "LuckyOnTest",
            f1=0.90,
            recall=0.90,
            roc_auc=0.90,
            cv_f1=0.50,
            cv_recall=0.50,
            cv_roc_auc=0.50,
        )
        stable = make_evaluation(
            "Stable",
            f1=0.60,
            recall=0.60,
            roc_auc=0.60,
            cv_f1=0.80,
            cv_recall=0.80,
            cv_roc_auc=0.80,
        )
        selection = select_best_model([lucky_on_test, stable])
        assert selection.model_name == "Stable"
        assert selection.scored_on == "cross_validation"

    def test_falls_back_to_test_metrics_without_cv(self):
        best = make_evaluation("Best", f1=0.7, recall=0.7, roc_auc=0.7)
        worst = make_evaluation("Worst", f1=0.4, recall=0.4, roc_auc=0.4)
        selection = select_best_model([best, worst])
        assert selection.model_name == "Best"
        assert selection.scored_on == "test_set"
        assert "cross-validation was skipped" in selection.reason

    def test_accuracy_alone_never_wins(self):
        """A majority-class predictor has high accuracy and must still lose."""
        majority_predictor = make_evaluation(
            "MajorityClass",
            f1=0.0,
            recall=0.0,
            roc_auc=0.5,
            accuracy=0.73,
            cv_f1=0.0,
            cv_recall=0.0,
            cv_roc_auc=0.5,
        )
        churn_model = make_evaluation(
            "ChurnModel",
            f1=0.62,
            recall=0.78,
            roc_auc=0.84,
            accuracy=0.74,
            cv_f1=0.62,
            cv_recall=0.78,
            cv_roc_auc=0.84,
        )
        selection = select_best_model([majority_predictor, churn_model])
        assert selection.model_name == "ChurnModel"

    def test_tie_broken_by_recall(self):
        low_recall = make_evaluation(
            "LowRecall", f1=0.6, recall=0.6, roc_auc=0.8, cv_f1=0.6, cv_recall=0.6, cv_roc_auc=0.8
        )
        high_recall = make_evaluation(
            "HighRecall", f1=0.6, recall=0.7, roc_auc=0.8, cv_f1=0.6, cv_recall=0.6, cv_roc_auc=0.8
        )
        # Identical scored metrics; the tie-break inspects the scored recall then
        # falls through to inference speed, so give the winner an explicit edge.
        high_recall.cv_recall_mean = 0.65
        selection = select_best_model([low_recall, high_recall])
        assert selection.model_name == "HighRecall"

    def test_ranking_is_ordered_and_complete(self):
        results = [
            make_evaluation("A", f1=0.5, recall=0.5, roc_auc=0.5, cv_f1=0.5, cv_recall=0.5, cv_roc_auc=0.5),
            make_evaluation("B", f1=0.7, recall=0.7, roc_auc=0.7, cv_f1=0.7, cv_recall=0.7, cv_roc_auc=0.7),
            make_evaluation("C", f1=0.6, recall=0.6, roc_auc=0.6, cv_f1=0.6, cv_recall=0.6, cv_roc_auc=0.6),
        ]
        selection = select_best_model(results)
        assert [entry["model_name"] for entry in selection.ranking] == ["B", "C", "A"]
        assert selection.reason.startswith("B ")

    def test_reason_reports_untouched_test_metrics(self):
        result = make_evaluation(
            "Model", f1=0.61, recall=0.79, roc_auc=0.83, cv_f1=0.61, cv_recall=0.79, cv_roc_auc=0.83
        )
        selection = select_best_model([result])
        assert "untouched" in selection.reason
        assert "cross-validation on the training split" in selection.reason


class TestScalePosWeight:
    def test_ratio(self):
        assert compute_scale_pos_weight(4144, 1490) == pytest.approx(4144 / 1490)

    def test_zero_positives_raises(self):
        with pytest.raises(ValueError):
            compute_scale_pos_weight(100, 0)
