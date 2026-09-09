# Explainability (SHAP)

How the system answers "**why** does the model think this customer will churn?"

```
Customer record
      ↓
Preprocessor (fitted ColumnTransformer)
      ↓
Transformed features            45 columns
      ↓
Trained Logistic Regression     best_model.joblib
      ↓
SHAP LinearExplainer            exact for linear models
      ↓
SHAP contributions              45 signed log-odds values
      ↓
Feature mapping + aggregation   45 columns → 19 original features
      ↓
Top risk drivers                ranked by |contribution|
      ↓
Human-readable explanation      JSON for the API and the UI
```

Module layout:

| File | Responsibility |
|------|----------------|
| `ml/src/explainability/explainer.py` | `ChurnExplainer`, `explain_customer` — the public entrypoint |
| `ml/src/explainability/feature_mapping.py` | Transformed column → original feature mapping and aggregation |
| `ml/src/explainability/background.py` | Builds and caches the SHAP reference distribution |
| `ml/src/explainability/global_importance.py` | Dataset-wide importance report |
| `ml/src/explainability/plots.py` | Static PNG charts for humans |

---

## 1. Why SHAP, and why it matters here

A churn score on its own is not actionable. A retention agent cannot act on
"0.81"; they can act on "this customer is on a month-to-month contract, has been
with us one month, and is paying above-average for fiber". SHAP turns the score
into that sentence.

Three concrete reasons this project needs it:

1. **The retention agent needs a reason.** Step 4 feeds these drivers to an LLM
   so the recommended offer targets the actual risk factor.
2. **Humans approve the actions.** A reviewer must be able to disagree with the
   model, which requires seeing its reasoning.
3. **Regulatory and trust pressure.** Automated decisions affecting customers
   need a defensible rationale.

SHAP specifically (rather than raw model coefficients) because it accounts for
each customer's *actual feature values*: a coefficient tells you what
`Contract=Two year` does in general, while a SHAP value tells you what it did
for **this** customer relative to the average customer.

## 2. Which explainer, and why

`shap.LinearExplainer`, chosen because the model selected in Step 2 is a Logistic
Regression:

- It is **exact** for linear models — no sampling, no approximation error.
- It is fast: SHAP reduces to `coefficient × (value − background mean)`, one
  matrix multiplication, so explaining all 5,634 training rows takes well under
  a second.
- Generic explainers (`shap.Explainer`, `KernelExplainer`) would sample
  coalitions to approximate the same numbers — slower and noisier for no gain.

The explainer refuses to run on a non-linear model rather than producing
something misleading: if `best_model.joblib` ever holds a tree model, `load()`
raises with a message telling the developer to add a model-appropriate explainer.
The test suite asserts additivity, which is the property that would break first
if the wrong explainer were ever used.

## 3. What a SHAP value means here

**SHAP values are computed on the model's log-odds output** (scikit-learn's
`decision_function`), not on the probability. This is stated in every
explanation payload as `"explained_output": "log_odds"`.

Why log-odds: a logistic regression is additive on that scale, and only there
does the SHAP decomposition hold exactly:

```
log_odds(customer) = base_value + Σ (all SHAP values)
```

Probabilities pass through a sigmoid and are **not** additive, so reporting SHAP
values as "probability points" would be mathematically wrong. Verified in
practice — reconstruction error on the real model is `2.2e-16`, i.e. floating
point noise. `ChurnExplainer.verify_additivity()` enforces this at runtime and a
unit test asserts it.

`base_value` is the average log-odds over the background distribution: the
model's prediction for a "typical" customer before any of this customer's own
attributes are considered. For the trained model it is **−0.372**, which
corresponds to a churn probability of about 41% for the reference customer.

### Sign convention

| SHAP value | Effect on log-odds | Reported direction |
|-----------:|--------------------|--------------------|
| `> 0` | pushes up | `increases_risk` |
| `< 0` | pushes down | `decreases_risk` |

The direction is derived purely from the sign of the SHAP contribution — never
from domain intuition. This matters: on the real trained model, a **low**
`MonthlyCharges` of 29.85 *increases* risk, because the fitted coefficient for
that feature is negative once the `InternetService` dummies absorb the pricing
signal. A hand-written rule based on "expensive plans churn more" would have
reported the opposite of what the model actually does.

## 4. The background (reference) distribution

A SHAP value measures deviation from a baseline, so a baseline must be defined.

- The background is a **200-row sample of the training split**, reproduced with
  the same `random_state=42` stratified split as training. Test rows are
  excluded so held-out data never leaks into the explanation baseline.
- Sampling is deterministic, so a given customer always receives the same
  explanation.
- It is cached as `ml/models/shap_background.joblib`, letting a deployed backend
  explain predictions without shipping the raw dataset. If the cache is missing
  and the dataset is unavailable, the layer raises a clear error instead of
  quietly substituting a different baseline.
- The masker is constructed with `max_samples` equal to the full background
  size; otherwise SHAP silently subsamples to 100 rows and warns.

## 5. Mapping 45 transformed columns back to 19 features

One-hot encoding expands each categorical feature into one column per category:

```
Contract  →  Contract_Month-to-month
             Contract_One year
             Contract_Two year
```

SHAP produces a value per *transformed* column, but a human needs "Contract".

**How the mapping is built:** from the fitted encoder's `categories_` attribute,
walking the `ColumnTransformer` in output order — never by splitting names on
`"_"`, which would break for any category value containing an underscore and
would silently mis-group features. As a safety net, the constructed names are
compared against `preprocessor.get_feature_names_out()`; a mismatch raises rather
than producing a misaligned explanation.

**Aggregation strategy: sum.** The contribution of an original feature is the
sum of the SHAP values of all its encoded columns.

Why summing is the mathematically defensible choice:

- SHAP is additive: `output = base + Σ φ`. Summing within a group preserves
  that identity exactly, so the grouped explanation still reconstructs the model
  output. A unit test asserts `Σ(aggregated) == Σ(raw)`.
- Averaging would arbitrarily shrink features with many categories (a 4-category
  `PaymentMethod` would be divided by 4 while numeric `tenure` is not), making
  importances incomparable.
- Taking the maximum would discard real contributions.

A subtlety worth stating: within a one-hot block only one column equals 1 and
the rest equal 0, **but the zero columns still carry non-zero SHAP values**.
`φ = coef × (0 − mean)` encodes the information "this customer is *not* on a
two-year contract", which is genuinely part of the explanation. Summing folds
that correctly into the single reported `Contract` value.

## 6. Selecting and reporting top drivers

Features are ranked by **absolute** aggregated SHAP value, so the strongest
influences appear first regardless of direction. `top_k` defaults to 5.

Each driver reports:

| Field | Meaning |
|-------|---------|
| `feature` | Original feature name, e.g. `Contract` |
| `value` | The customer's own value, after cleaning, e.g. `"Month-to-month"` |
| `impact` | Share of this customer's total absolute contribution, in `[0, 1]` |
| `direction` | `increases_risk` / `decreases_risk` |
| `shap_value` | The raw signed log-odds contribution |

`impact` is normalised (`|φ| / Σ|φ|` across all 19 features) for two reasons: it
makes drivers directly comparable as "this factor accounts for 28% of what moved
the prediction", and it satisfies the `RiskDriver` schema in
`backend/app/schemas/prediction.py`, which constrains impact to `[0, 1]`. The
un-normalised log-odds contribution is always available as `shap_value`, so
nothing is hidden.

## 7. Local vs global explanations

|  | Local | Global |
|--|-------|--------|
| Question | Why is *this* customer at risk? | What drives churn *in general*? |
| Entry point | `explain_customer(record, top_k=5)` | `python -m ml.src.explainability.global_importance` |
| Computation | SHAP for one row | Mean of `\|SHAP\|` across the training split |
| Output | JSON with `top_drivers` | `ml/models/global_feature_importance.csv` |
| Used by | The API and the retention agent, per customer | Model review, reporting, slides |

The global report includes both:

- `mean_absolute_shap` — how much the feature moves predictions, ignoring
  direction. A feature that pushes some customers toward churn and others away
  still matters.
- `mean_signed_shap` — the average direction. Positive means the feature pushes
  the average customer toward churn.

Both are reported because either alone is misleading. The report is computed
over the full training split (5,634 rows); since the explainer is linear, that
costs one matrix multiplication, so no subsampling is needed. `--sample-size`
takes a deterministic sample when a cheaper run is wanted.

## 8. Integration with prediction

The explainability layer does **not** re-implement any prediction logic. It
holds a `ChurnPredictor` and calls `transform_customers()` for validation,
cleaning, and preprocessing, and `predict()` for the probability and risk band.
Explanation and prediction therefore cannot disagree about the same customer —
a unit test asserts they return the same probability.

Planned backend flow (Step 4 onward, not implemented yet):

```
customer data → predict_customer() → churn probability
                                   ↓
                explain_customer() → top drivers
                                   ↓
                        AI agent → retention recommendation
```

The explanation output maps onto the existing `PredictionResponse` /
`RiskDriver` schemas without further transformation.

## 9. Known limitations

- SHAP explains **the model, not reality**. It shows what drove the prediction,
  not a causal claim about what would happen if the feature changed.
- Logistic regression with correlated features (`tenure`, `TotalCharges`,
  `MonthlyCharges`, `InternetService`) can split credit between them in ways
  that look surprising. The interventional background used here assumes feature
  independence, which is standard but imperfect for correlated inputs.
- The explanation is only as trustworthy as the model: at 0.78 recall and 0.50
  precision, roughly half of the flagged customers are false positives, and
  their explanations are explanations of a wrong prediction.
- Explanations are computed for the positive (churn) class only.
