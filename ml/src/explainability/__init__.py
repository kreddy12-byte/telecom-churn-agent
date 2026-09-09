"""SHAP-based model explanation utilities.

Public entrypoint used by the rest of the system::

    from ml.src.explainability import explain_customer
"""

from ml.src.explainability.explainer import (
    ChurnExplainer,
    explain_customer,
    get_explainer,
)

__all__ = ["ChurnExplainer", "explain_customer", "get_explainer"]
