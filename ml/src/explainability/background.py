"""Background dataset used as the SHAP reference distribution.

Why a background dataset is needed
----------------------------------
A SHAP value answers "how much did this feature move the prediction *away from
the average prediction*?". That requires a reference distribution defining what
"average" means. For an interventional linear explainer the reference is the
mean of the background data.

Design decisions
----------------
* The background is drawn from the **training split only**, reproduced with the
  same ``random_state=42`` stratified split used in training. Using test rows
  would leak held-out information into the explanation baseline.
* The sample is cached as ``ml/models/shap_background.joblib`` so a deployed
  backend can explain predictions without shipping the raw dataset.
* Sampling is deterministic, so the same customer always gets the same
  explanation.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split

from ml.src import config
from ml.src.exceptions import DatasetNotFoundError, MLPipelineError
from ml.src.logging_config import get_logger

logger = get_logger(__name__)

BACKGROUND_FILENAME = "shap_background.joblib"
DEFAULT_BACKGROUND_SIZE = 200


def build_background_matrix(
    preprocessor: ColumnTransformer,
    sample_size: int = DEFAULT_BACKGROUND_SIZE,
    dataset_path: Path | None = None,
) -> np.ndarray:
    """Build the background matrix from a sample of the training split.

    Raises:
        DatasetNotFoundError: When the raw dataset is unavailable.
    """
    # Imported here to keep the module import-light for backend processes that
    # only ever load a cached background.
    from ml.src.data.clean_dataset import clean_dataset
    from ml.src.data.validate_dataset import load_raw_dataset
    from ml.src.preprocessing.pipeline import split_features_target

    raw_frame = load_raw_dataset(dataset_path)
    cleaned, _ = clean_dataset(raw_frame)
    features, target = split_features_target(cleaned)

    # Identical split parameters to training, so this really is the training set.
    x_train, _, _, _ = train_test_split(
        features,
        target,
        test_size=config.TEST_SIZE,
        random_state=config.RANDOM_STATE,
        stratify=target,
    )

    effective_size = min(sample_size, len(x_train))
    sampled = x_train.sample(n=effective_size, random_state=config.RANDOM_STATE)
    background = np.asarray(preprocessor.transform(sampled))

    logger.info(
        "Built SHAP background from %s training rows (of %s available).",
        effective_size,
        len(x_train),
    )
    return background


def save_background(background: np.ndarray, models_dir: Path) -> Path:
    """Persist the background matrix next to the model artifacts."""
    models_dir.mkdir(parents=True, exist_ok=True)
    path = models_dir / BACKGROUND_FILENAME
    joblib.dump(background, path)
    logger.info("Saved SHAP background to %s", path)
    return path


def load_or_build_background(
    preprocessor: ColumnTransformer,
    models_dir: Path,
    sample_size: int = DEFAULT_BACKGROUND_SIZE,
    rebuild: bool = False,
) -> np.ndarray:
    """Return the cached background, building and caching it when missing."""
    path = models_dir / BACKGROUND_FILENAME

    if path.exists() and not rebuild:
        background = np.asarray(joblib.load(path))
        logger.debug("Loaded cached SHAP background %s from %s", background.shape, path)
        return background

    try:
        background = build_background_matrix(preprocessor, sample_size=sample_size)
    except DatasetNotFoundError as exc:
        raise MLPipelineError(
            f"No cached SHAP background at {path} and the raw dataset is unavailable, "
            "so the explanation baseline cannot be established. Either run "
            "`python -m ml.src.data.download_dataset` or ship "
            f"'{BACKGROUND_FILENAME}' with the model artifacts. Original error: {exc}"
        ) from exc

    save_background(background, models_dir)
    return background
