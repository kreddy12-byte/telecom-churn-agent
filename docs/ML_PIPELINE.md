# ML Pipeline

How raw telecom data becomes a churn probability that the FastAPI backend can
serve. Every stage is a separate module so it can be tested and replaced
independently.

```
Dataset            ml/src/data/download_dataset.py
   ↓
Validation         ml/src/data/validate_dataset.py
   ↓
Cleaning           ml/src/data/clean_dataset.py
   ↓
Train/Test Split   ml/src/training/train.py
   ↓
Preprocessing      ml/src/preprocessing/pipeline.py
   ↓
Model Training     ml/src/training/train.py
   ↓
Evaluation         ml/src/training/evaluate.py
   ↓
Model Selection    ml/src/training/model_selection.py
   ↓
Model Artifact     ml/models/*.joblib + model_metadata.json
   ↓
Prediction API     ml/src/prediction/predictor.py
```

---

## 1. Dataset acquisition

`download_dataset.py` fetches the IBM Telco Customer Churn CSV from IBM's public
repository. Guardrails, in order:

1. HEAD request confirms the source is reachable.
2. Payload must exceed a minimum size.
3. Payload must parse as CSV and contain rows.
4. The expected Telco schema must be present.

A download failing any check is deleted and the next configured source is tried.
If every source fails, `DatasetDownloadError` names each failure — the pipeline
never substitutes a different dataset to keep going.

Output: `ml/data/raw/telco_customer_churn.csv` (git-ignored).

## 2. Validation

`validate_dataset.py` returns a `ValidationReport` dataclass and separates:

- **Blocking** (raises `DatasetValidationError`): empty dataset, missing required
  columns, missing target column, unexpected or missing target labels.
- **Reported**: duplicate rows, duplicate `customerID`s, missing values, blank
  strings, non-numeric values in numeric columns, negative charges, dtypes,
  class distribution.

Reported observations are logged and persisted into `model_comparison.json`, so
data problems are visible rather than silently discarded.

## 3. Cleaning

`clean_dataset.py` contains only deterministic row-wise transformations —
whitespace stripping, numeric coercion, the zero-tenure `TotalCharges` rule,
duplicate removal, and target mapping.

`prepare_feature_frame()` holds the feature-side subset of that logic and is
called by **both** training and the predictor, which is what guarantees a single
prediction request is treated exactly like a training row.

Anything that learns from data lives in stage 5.

## 4. Train/test split

`train_test_split(test_size=0.2, random_state=42, stratify=y)`.

The test set is quarantined: it is not used for imputation statistics, scaling,
category vocabularies, cross-validation, or model selection.

## 5. Preprocessing

One `ColumnTransformer`:

- Numeric → median imputation → standard scaling
- Categorical → most-frequent imputation → `OneHotEncoder(handle_unknown="ignore")`

It is a step inside each candidate `Pipeline`, so `cross_validate` refits it per
fold. That is the mechanism that prevents leakage from validation folds — it is
not merely a convention.

## 6. Model training

Six candidates: Logistic Regression, Decision Tree, Random Forest, XGBoost,
K-Nearest Neighbors, Gaussian Naive Bayes. Each is wrapped in
`Pipeline([preprocessor, model])` and gets 5-fold stratified CV on the training
split followed by a fit on the full training split.

Class imbalance (~26.5% positives) is handled with `class_weight="balanced"`
and XGBoost's `scale_pos_weight`, not SMOTE. Weighting reshapes the loss without
fabricating customers and keeps probabilities usable for risk banding. KNN and
Naive Bayes cannot be weighted; that limitation is recorded per model.

If `xgboost` is not installed, the pipeline logs an error and continues with the
remaining candidates rather than crashing or pretending it ran.

## 7. Evaluation

`evaluate.py` computes accuracy, precision, recall, F1 (binary, positive class =
churn), ROC AUC, the confusion matrix, plus training and inference time. Results
are structured `ModelEvaluation` dataclasses, then exported to
`model_comparison.csv` and `model_comparison.json`.

## 8. Model selection

```
score = 0.45 * F1 + 0.35 * Recall + 0.20 * ROC AUC
```

Accuracy is deliberately excluded from the score: the majority class is ~73%, so
a "never churns" model would look strong on accuracy and be worthless. Recall
carries heavy weight because a missed churner costs a customer lifetime while a
false positive costs one retention offer. ROC AUC rewards well-ordered
probabilities, which the LOW/MEDIUM/HIGH bands depend on.

Ties break on recall, then ROC AUC, then inference speed. The winner, its score,
and the full ranking are written to `model_metadata.json`.

## 9. Artifacts

| File | Purpose |
|------|---------|
| `best_model.joblib` | Fitted estimator only |
| `preprocessor.joblib` | Fitted `ColumnTransformer` |
| `model_metadata.json` | Version, features, metrics, selection reason, environment |
| `model_comparison.csv` / `.json` | Candidate comparison |

Storing the estimator and preprocessor separately keeps the transform step
explicit for the predictor and gives the upcoming SHAP layer direct access to
the transformed feature space and its names.

## 10. Prediction interface

`ml/src/prediction/predictor.py` is the only module the backend will import.

```python
from ml.src.prediction.predictor import predict_customer, predict_customers
```

Per request: load artifacts (cached) → normalise input → validate against the
trained feature schema → apply shared cleaning → transform → `predict_proba` →
band the probability.

```json
{
  "churn_probability": 0.87,
  "prediction": 1,
  "risk_level": "HIGH",
  "model_version": "1.0.0"
}
```

Risk bands: `< 0.30` LOW, `0.30 ≤ p < 0.60` MEDIUM, `≥ 0.60` HIGH.

Errors are typed so the API layer can map them to status codes:

| Exception | Meaning | Likely HTTP status |
|-----------|---------|--------------------|
| `InvalidPredictionInputError` | Missing/malformed feature values | 422 |
| `ModelArtifactNotFoundError` | Model not trained yet | 503 |
| `DatasetNotFoundError` / `DatasetValidationError` | Data problem | 500 |
| `MLPipelineError` | Base class for the above | 500 |

## Reproducibility

`random_state=42` everywhere (split, CV shuffling, every estimator). Paths are
resolved from the module location with `pathlib`, and `ML_DATA_DIR` /
`ML_MODELS_DIR` can override them for containers — no absolute paths and no
dependency on the current working directory.

## Backend integration (next steps, not implemented here)

1. A backend service wraps `predict_customer` and maps the result onto the
   `PredictionResponse` schema in `backend/app/schemas/prediction.py`.
2. `top_drivers` will be filled by the SHAP layer in
   `ml/src/explainability/` (Step 3).
3. Training stays offline; the API only loads artifacts.
