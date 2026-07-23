"""Tests for the local London transaction rebuild."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "2_local_processing"))

from rebuild_london_transactions import (  # noqa: E402
    source_manifest_hash,
    validate_unique_transactions,
)


class LondonTransactionBuildTests(unittest.TestCase):
    def test_rejects_duplicate_transaction_ids(self) -> None:
        transactions = pd.DataFrame(
            {"transaction_id": ["id-1", "id-1", "id-2"]}
        )
        with self.assertRaisesRegex(ValueError, "duplicate transaction IDs"):
            validate_unique_transactions(transactions)

    def test_accepts_unique_transaction_ids(self) -> None:
        transactions = pd.DataFrame(
            {"transaction_id": ["id-1", "id-2", "id-3"]}
        )
        validate_unique_transactions(transactions)

    def test_source_manifest_fingerprint_changes_with_object_version(self) -> None:
        first = [{"Key": "year=2025/part.parquet", "ETag": '"abc"', "Size": 10}]
        second = [{"Key": "year=2025/part.parquet", "ETag": '"def"', "Size": 10}]
        self.assertNotEqual(source_manifest_hash(first), source_manifest_hash(second))


if __name__ == "__main__":
    unittest.main()
