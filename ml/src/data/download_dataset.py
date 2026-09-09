"""Download the IBM Telco Customer Churn dataset from a stable public source.

Run as a module::

    python -m ml.src.data.download_dataset

The download is verified before it replaces any existing file: the response must
be reachable, non-empty, parseable as CSV, and contain the expected Telco
schema. A file that fails those checks is discarded rather than accepted.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

from ml.src import config
from ml.src.exceptions import DatasetDownloadError, DatasetValidationError
from ml.src.logging_config import configure_logging, get_logger

logger = get_logger(__name__)

_REQUEST_TIMEOUT_SECONDS = 60
_MIN_EXPECTED_BYTES = 100_000
_USER_AGENT = "telecom-churn-agent/1.0 (dataset downloader)"


def check_source_available(url: str, timeout: int = _REQUEST_TIMEOUT_SECONDS) -> bool:
    """Return True when ``url`` responds successfully to a HEAD request."""
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        logger.warning("Dataset source unreachable (%s): %s", url, exc)
        return False

    if not 200 <= status < 300:
        logger.warning("Dataset source returned status %s: %s", status, url)
        return False
    return True


def _download_to_temp(url: str, timeout: int) -> Path:
    """Fetch ``url`` into a temporary file and return its path."""
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise DatasetDownloadError(f"Failed to download dataset from {url}: {exc}") from exc

    if len(payload) < _MIN_EXPECTED_BYTES:
        raise DatasetDownloadError(
            f"Downloaded file from {url} is only {len(payload)} bytes, which is far smaller "
            f"than the expected Telco dataset (~{_MIN_EXPECTED_BYTES} bytes). Refusing to use it."
        )

    handle = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    try:
        handle.write(payload)
    finally:
        handle.close()
    return Path(handle.name)


def _verify_downloaded_csv(path: Path, url: str) -> None:
    """Ensure a downloaded file is really the expected Telco churn dataset."""
    try:
        frame = pd.read_csv(path)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise DatasetDownloadError(f"Downloaded file from {url} is not valid CSV: {exc}") from exc

    if frame.empty:
        raise DatasetDownloadError(f"Downloaded dataset from {url} contains no rows.")

    missing = [column for column in config.REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise DatasetDownloadError(
            f"Downloaded file from {url} does not match the expected "
            f"{config.DATASET_NAME} schema. Missing columns: {missing}. "
            "Refusing to substitute a different dataset."
        )

    logger.info(
        "Verified download from %s: %s rows, %s columns", url, len(frame), frame.shape[1]
    )


def download_dataset(
    destination: Path | None = None,
    url: str | None = None,
    force: bool = False,
    timeout: int = _REQUEST_TIMEOUT_SECONDS,
) -> Path:
    """Download the raw dataset and return the path it was written to.

    Args:
        destination: Target CSV path. Defaults to ``ml/data/raw/``.
        url: Explicit source URL. Defaults to the configured IBM source plus fallbacks.
        force: Re-download even when the file already exists.
        timeout: Per-request timeout in seconds.

    Raises:
        DatasetDownloadError: When no configured source yields a valid dataset.
    """
    target = Path(destination) if destination else config.RAW_DATASET_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and not force:
        logger.info("Dataset already present at %s (use force=True to re-download).", target)
        return target

    candidate_urls = [url] if url else [config.DATASET_URL, *config.DATASET_FALLBACK_URLS]
    seen: set[str] = set()
    failures: list[str] = []

    for candidate in candidate_urls:
        if candidate in seen:
            continue
        seen.add(candidate)

        logger.info("Checking dataset source: %s", candidate)
        if not check_source_available(candidate, timeout=timeout):
            failures.append(f"{candidate}: source not reachable")
            continue

        try:
            temp_path = _download_to_temp(candidate, timeout=timeout)
        except DatasetDownloadError as exc:
            failures.append(str(exc))
            continue

        try:
            _verify_downloaded_csv(temp_path, candidate)
            shutil.move(str(temp_path), target)
        except DatasetDownloadError as exc:
            temp_path.unlink(missing_ok=True)
            failures.append(str(exc))
            continue

        logger.info("Dataset saved to %s (%s bytes)", target, target.stat().st_size)
        return target

    raise DatasetDownloadError(
        "Could not obtain the "
        f"{config.DATASET_NAME} dataset from any configured source.\n"
        + "\n".join(f"  - {failure}" for failure in failures)
        + "\nFix the network/proxy configuration or download the CSV manually to "
        f"{target} before training."
    )


def ensure_dataset(force: bool = False) -> Path:
    """Return the raw dataset path, downloading it first when necessary."""
    if config.RAW_DATASET_PATH.exists() and not force:
        return config.RAW_DATASET_PATH
    return download_dataset(force=force)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download the IBM Telco Customer Churn dataset.")
    parser.add_argument("--force", action="store_true", help="Re-download even if the file exists.")
    parser.add_argument("--url", default=None, help="Override the dataset source URL.")
    parser.add_argument(
        "--destination", default=None, help="Override the destination CSV path."
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = _parse_args()
    try:
        path = download_dataset(
            destination=Path(args.destination) if args.destination else None,
            url=args.url,
            force=args.force,
        )
    except (DatasetDownloadError, DatasetValidationError) as exc:
        logger.error("%s", exc)
        return 1

    logger.info("Dataset ready: %s", path)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
