# ML Module — Telecom Churn Prediction

Production-oriented machine-learning pipeline for the Telecom Churn & Retention
Agent. It is a reusable Python package, not a notebook: the FastAPI backend will
import `ml.src.prediction.predictor` directly without touching training code.

---

## Dataset

| Item | Value |
|------|-------|
| Name | IBM Telco Customer Churn |
| Source | `https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv` (IBM's own public repository) |
| Rows | 7,043 |
| Columns | 21 (19 features + `customerID` + `Churn`) |
| Local path | `ml/data/raw/telco_customer_churn.csv` (git-ignored) |
| Target | `Churn` — `No -> 0`, `Yes -> 1` |
| Class balance | 5,174 `No` / 1,869 `Yes` (26.54% churn) |

The downloader verifies the source responds, that the payload is parseable CSV,
and that the expected Telco schema is present. A file that fails any check is
discarded rather than silently accepted as a substitute dataset.

### Features

**Numeric (4):** `SeniorCitizen`, `tenure`, `MonthlyCharges`, `TotalCharges`

**Categorical (15):** `gender`, `Partner`, `Dependents`, `PhoneService`,
`MultipleLines`, `InternetService`, `OnlineSecurity`, `OnlineBackup`,
`DeviceProtection`, `TechSupport`, `StreamingTV`, `StreamingMovies`, `Contract`,
`PaperlessBilling`, `PaymentMethod`

`customerID` is an identifier and is deliberately excluded from the feature set.

---

## Pipeline stages

```
download -> validate -> clean -> split -> preprocess -> train -> evaluate -> select -> persist -> predict -> explain
```

See [`docs/ML_PIPELINE.md`](../docs/ML_PIPELINE.md) for the detailed flow.

### Validation

`ml/src/data/validate_dataset.py` distinguishes blocking failures from
observations:

- **Blocking (raises `DatasetValidationError`):** empty file, missing required
  columns, missing/unknown target values.
- **Reported:** duplicate rows, duplicate IDs, missing values, blank strings,
  non-numeric values in numeric columns, negative charges, dtypes.

Nothing problematic is dropped silently; every observation is logged and stored
in `model_comparison.json`.

### Cleaning decisions

1. Whitespace stripped from text columns; blank strings become `NaN`.
2. `TotalCharges` / `MonthlyCharges` / `tenure` coerced to numeric; unparseable
   values become `NaN` instead of being discarded.
3. The 11 blank `TotalCharges` rows all have `tenure == 0` (customers not yet
   billed), so they are set to `0.0`. This is a row-wise domain rule applied
   identically during training and inference, so it introduces no leakage.
4. Exact duplicate rows are removed and counted.
5. Target mapped `No -> 0`, `Yes -> 1`; any other label raises.

Nothing that *learns* from data happens here.

### Preprocessing

A single `ColumnTransformer` (`ml/src/preprocessing/pipeline.py`) is fitted on
the training split only, inside a scikit-learn `Pipeline`:

| Feature type | Steps |
|--------------|-------|
| Numeric | `SimpleImputer(strategy="median")` → `StandardScaler()` |
| Categorical | `SimpleImputer(strategy="most_frequent")` → `OneHotEncoder(handle_unknown="ignore")` |

`handle_unknown="ignore"` means a category unseen during training (for example a
new payment method) produces an all-zero block instead of raising at inference.

### Train/test split

`train_test_split(test_size=0.2, random_state=42, stratify=y)`. The test set is
never used for preprocessing, cross-validation, or model selection — only for
final evaluation. Model comparison uses 5-fold stratified cross-validation on
the training split, with the preprocessor refitted inside every fold.

### Models trained

| Model | Imbalance handling |
|-------|--------------------|
| Logistic Regression | `class_weight="balanced"` |
| Decision Tree | `class_weight="balanced"` |
| Random Forest | `class_weight="balanced"` |
| XGBoost | `scale_pos_weight = n_negative / n_positive` |
| K-Nearest Neighbors | not supported — trained on the natural ratio |
| Gaussian Naive Bayes | not supported — trained on the natural ratio |

Class imbalance (26.5% positives) is handled with class weighting rather than
SMOTE. Weighting changes the loss without inventing synthetic customers, keeps
predicted probabilities interpretable for the LOW/MEDIUM/HIGH risk bands, and
avoids the leakage traps of resampling before cross-validation. Estimators that
cannot be weighted are still compared, and the limitation is recorded in their
evaluation notes.

Hyperparameters are sensible baselines; no large search is performed.

### Evaluation metrics

Per model: accuracy, precision, recall, F1, ROC AUC, confusion matrix
(TN/FP/FN/TP), cross-validated F1 and ROC AUC, training time, and inference
time. Results are written to:

- `ml/models/model_comparison.csv` — flat table
- `ml/models/model_comparison.json` — full report including validation warnings,
  cleaning notes, and class balance

### Model-selection strategy

Accuracy is reported but never used to choose the winner: predicting "no churn"
for everyone already scores ~73% on this dataset. A missed churner costs a
customer lifetime; a false positive costs one retention offer. The winner
maximises

```
score = 0.45 * F1 + 0.35 * Recall + 0.20 * ROC AUC
```

The score is computed from **5-fold cross-validated scores on the training
split**, so the test set plays no part in choosing the model — it only reports
the final performance of the already-chosen winner. Averaging across folds also
favours models that are stable rather than lucky on one split. Ties break on
recall, then ROC AUC, then inference speed. The exact reason for the selection,
plus the full ranking, is written into `ml/models/model_metadata.json`.

---

## Latest verified run

7,043 rows, 5,634 train / 1,409 test, `random_state=42`. Test-set metrics;
`cv_f1` and `cv_recall` are the training-split cross-validated values that drive
selection.

| Model | Accuracy | Precision | Recall | F1 | ROC AUC | cv_f1 | cv_recall | Score |
|-------|---------:|----------:|-------:|---:|--------:|------:|----------:|------:|
| **LogisticRegression** (selected) | 0.7381 | 0.5043 | 0.7834 | 0.6136 | 0.8416 | 0.6283 | 0.8013 | **0.7324** |
| GaussianNB | 0.6948 | 0.4589 | 0.8369 | 0.5928 | 0.8074 | 0.5974 | 0.8482 | 0.7299 |
| DecisionTree | 0.7395 | 0.5060 | 0.7914 | 0.6173 | 0.8336 | 0.6129 | 0.7873 | 0.7164 |
| XGBoost | 0.7567 | 0.5290 | 0.7567 | 0.6227 | 0.8352 | 0.6274 | 0.7518 | 0.7133 |
| RandomForest | 0.7722 | 0.5525 | 0.7460 | 0.6348 | 0.8412 | 0.6320 | 0.7318 | 0.7097 |
| KNeighbors | 0.7779 | 0.5874 | 0.5481 | 0.5671 | 0.8078 | 0.5794 | 0.5639 | 0.6209 |

Logistic Regression wins on the recall-weighted score while also posting the
best cross-validated ROC AUC (0.8460). Random Forest and KNN have higher
accuracy but recall 0.75 and 0.55 respectively — they miss more churners, which
is the expensive error here. Re-running `train.py` regenerates these numbers;
they are not hardcoded anywhere in the code.

---

## How to run

All commands run from the **repository root** so `ml` resolves as a package.

```bash
pip install -r ml/requirements.txt

# 1. Download the dataset (skips if already present; --force to refresh)
python -m ml.src.data.download_dataset

# 2. Inspect dataset health without training
python -m ml.src.data.validate_dataset --json

# 3. Train, evaluate, compare, select, and persist artifacts
python -m ml.src.training.train

# 4. Predict for a real customer from the dataset
python -m ml.src.prediction.predictor --customer-id 7590-VHVEG
python -m ml.src.prediction.predictor --row 0
python -m ml.src.prediction.predictor --json '{"tenure": 1, "MonthlyCharges": 70.7, ...}'
```

Useful training flags: `--no-cv` (faster), `--no-download` (fail instead of
fetching), `--models-dir`, `--dataset-path`.

```bash
# 5. Explain why a customer is at risk (SHAP)
python -m ml.src.explainability.explainer --customer-id 7590-VHVEG --top-k 5 --plot

# 6. Global feature importance across all customers
python -m ml.src.explainability.global_importance
```

### Programmatic use (how the backend will call it)

```python
from ml.src.prediction.predictor import predict_customer

result = predict_customer({
    "gender": "Female", "SeniorCitizen": 0, "Partner": "Yes", "Dependents": "No",
    "tenure": 1, "PhoneService": "No", "MultipleLines": "No phone service",
    "InternetService": "DSL", "OnlineSecurity": "No", "OnlineBackup": "Yes",
    "DeviceProtection": "No", "TechSupport": "No", "StreamingTV": "No",
    "StreamingMovies": "No", "Contract": "Month-to-month",
    "PaperlessBilling": "Yes", "PaymentMethod": "Electronic check",
    "MonthlyCharges": 29.85, "TotalCharges": 29.85,
})
# Actual output for customer 7590-VHVEG:
# {"churn_probability": 0.8064, "prediction": 1, "risk_level": "HIGH", "model_version": "1.0.0"}
```

Risk bands: `< 0.30` LOW, `0.30–0.60` MEDIUM, `>= 0.60` HIGH.

`ChurnPredictor` loads artifacts lazily and caches them, so a long-running API
process pays the load cost once.

---

## SHAP Explainability

Full detail lives in [`docs/EXPLAINABILITY.md`](../docs/EXPLAINABILITY.md); this
is the summary.

### Why SHAP, and why it matters for churn

A probability is not actionable. A retention agent cannot act on "0.81" but can
act on "month-to-month contract, one month of tenure, above-average charges".
SHAP converts the score into that reasoning, which this project needs because
(a) the Step 4 retention agent must target the actual risk factor, (b) a human
approves every action and needs to be able to disagree with the model, and
(c) automated decisions affecting customers require a defensible rationale.

SHAP is used rather than raw model coefficients because it accounts for each
customer's own feature values: a coefficient describes `Contract=Two year` in
general; a SHAP value describes what it did for *this* customer relative to an
average one.

### Which explainer

`shap.LinearExplainer`, because the model selected in Step 2 is a Logistic
Regression. It is **exact** for linear models (no sampling error) and reduces to
one matrix multiplication, so the whole training split can be explained in under
a second. The explainer raises rather than running if `best_model.joblib` ever
contains a non-linear model.

### What a SHAP value means

SHAP values are computed on the model's **log-odds** output
(`decision_function`), never on the probability, and every payload states this
as `"explained_output": "log_odds"`. Log-odds is the scale on which logistic
regression is additive, which makes the decomposition exact:

```
log_odds(customer) = base_value + Σ (all SHAP values)
```

Measured reconstruction error on the real model is `2.2e-16` — floating point
noise. Probabilities are squashed through a sigmoid and are not additive, so
calling SHAP values "probability points" would be wrong.

`base_value` (−0.372 for the trained model) is the average log-odds over the
background: the prediction for a typical customer before this customer's own
attributes are considered.

### Positive vs negative contributions

| SHAP value | Direction reported |
|-----------:|--------------------|
| `> 0` | `increases_risk` |
| `< 0` | `decreases_risk` |

Direction comes from the sign of the contribution, never from domain intuition.
On the real model a *low* `MonthlyCharges` **increases** risk, because the fitted
coefficient is negative once the `InternetService` dummies absorb the pricing
signal. A hand-written "expensive plans churn more" rule would report the
opposite of what the model actually does.

### The background distribution

SHAP measures deviation from a baseline, so one must be defined. The baseline is
a deterministic 200-row sample of the **training split** (same `random_state=42`
split as training — test rows are excluded so nothing leaks), cached as
`ml/models/shap_background.joblib` so a deployed backend can explain predictions
without the raw dataset.

### How categorical features are handled

One-hot encoding turns 19 original features into 45 transformed columns:

```
Contract → Contract_Month-to-month | Contract_One year | Contract_Two year
```

The mapping back is built from the fitted encoder's `categories_`, not by
splitting names on `"_"` (which breaks on category values containing
underscores), and is cross-checked against `get_feature_names_out()`.

**Aggregation strategy: sum.** SHAP is additive, so summing a feature's encoded
columns yields exactly that feature's total contribution and keeps
`output = base + Σ φ` intact — a unit test asserts the sum is preserved.
Averaging would unfairly shrink features with many categories; taking the max
would discard real contributions. Note that the zero columns of a one-hot block
still carry non-zero SHAP values (they encode "this customer is *not* on a
two-year contract"), and summing folds that in correctly.

### How top drivers are selected

Ranked by **absolute** aggregated SHAP value so the strongest influences come
first regardless of direction; `top_k` defaults to 5. Each driver reports
`feature`, the customer's `value`, `impact`, `direction`, and the raw
`shap_value`. `impact` is the normalised share of the customer's total absolute
contribution (`|φ| / Σ|φ|`), which keeps it in `[0, 1]` as the backend
`RiskDriver` schema requires while the un-normalised log-odds number stays
visible as `shap_value`.

### Local vs global

|  | Local | Global |
|--|-------|--------|
| Question | Why is *this* customer at risk? | What drives churn overall? |
| Call | `explain_customer(record, top_k=5)` | `python -m ml.src.explainability.global_importance` |
| Output | JSON `top_drivers` | `ml/models/global_feature_importance.csv` |

### Usage

```python
from ml.src.explainability import explain_customer

explanation = explain_customer(customer_record, top_k=5)
```

Real output for customer `7590-VHVEG` (churn probability 0.8064, HIGH):

| Feature | Value | Impact | Direction | SHAP (log-odds) |
|---------|-------|-------:|-----------|----------------:|
| tenure | 1 | 0.2768 | increases_risk | +1.3752 |
| MonthlyCharges | 29.85 | 0.1610 | increases_risk | +0.7998 |
| InternetService | DSL | 0.1388 | decreases_risk | −0.6895 |
| TotalCharges | 29.85 | 0.0915 | decreases_risk | −0.4549 |
| Contract | Month-to-month | 0.0821 | increases_risk | +0.4077 |

Global top five by mean |SHAP|: `tenure` (1.0229), `InternetService` (0.5933),
`MonthlyCharges` (0.5885), `Contract` (0.5389), `TotalCharges` (0.4042).

## Saved artifacts

| Path | Contents |
|------|----------|
| `ml/models/best_model.joblib` | Fitted estimator for the winning model |
| `ml/models/preprocessor.joblib` | Fitted `ColumnTransformer` (train-split statistics) |
| `ml/models/model_metadata.json` | Model name, version, features, metrics, selection reason, environment |
| `ml/models/model_comparison.csv` | Metric table for every candidate |
| `ml/models/model_comparison.json` | Full comparison report |
| `ml/models/shap_background.joblib` | SHAP reference distribution (200 training rows) |
| `ml/models/global_feature_importance.csv` | Mean absolute/signed SHAP per feature |
| `ml/models/explanations/*.png` | Global and per-customer explanation charts |

Model and preprocessor are saved separately so the prediction interface can
transform inputs explicitly and so the upcoming SHAP layer can attach to the
transformed feature space. `.joblib` files are git-ignored; the JSON/CSV reports
are committed.

---

## Tests

```bash
python -m pytest ml/tests -q      # from the repository root
```

Tests never download the dataset. They build a synthetic frame with the same
schema (including the blank-`TotalCharges` quirk) and train a small real model
into a temporary directory, so the load → validate → transform → predict path is
exercised end to end.

---

## Limitations

- Baseline hyperparameters only; no tuning search.
- The dataset is a public snapshot, not live telecom data; drift monitoring and
  periodic retraining are out of scope for this step.
- The 0.5 decision threshold is the default; the business-optimal threshold
  should be calibrated against real retention costs.
- Fairness across `gender` / `SeniorCitizen` has not been audited.
- `TotalCharges = 0` for zero-tenure customers is a documented assumption.
- SHAP explains **the model, not reality** — it shows what drove the prediction,
  not what would happen if a feature changed. The interventional background also
  assumes feature independence, which is imperfect for correlated inputs such as
  `tenure` / `TotalCharges` / `MonthlyCharges`.
- At 0.78 recall and 0.50 precision roughly half the flagged customers are false
  positives; their explanations explain a wrong prediction.
- The FastAPI prediction endpoint and the retention agent arrive in later steps.
