"""
Unit tests for the multi-image receipt helpers.

Covers:
- receiptDetailedSummary.collect_image_keys: ordering, de-duplication, legacy
  fallbacks and the empty case.
- addReceiptImage._existing_image_keys / _execution_name: key collection and
  Step Functions execution-name constraints.
"""

import os
import sys
import unittest

# Add the storage lambdas directory to the path so we can import the modules.
LAMBDAS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "lib", "storage", "lambdas"
)
sys.path.insert(0, LAMBDAS_DIR)

# Stub required environment variables so module-level reads don't fail.
os.environ.setdefault("BUCKET_NAME", "test-bucket")
os.environ.setdefault("RECEIPTS_TABLE_NAME", "test-table")
os.environ.setdefault("STATE_MACHINE_ARN", "arn:aws:states:::stateMachine/test")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")

import addReceiptImage  # noqa: E402
import receiptDetailedSummary  # noqa: E402


class CollectImageKeysTests(unittest.TestCase):
    def test_primary_first_and_deduplicated(self):
        receipt = {"s3ObjectKey": "k0", "imageKeys": ["k1", "k0", "k2"]}
        self.assertEqual(
            receiptDetailedSummary.collect_image_keys(receipt),
            ["k0", "k1", "k2"],
        )

    def test_legacy_scalar_only(self):
        self.assertEqual(
            receiptDetailedSummary.collect_image_keys({"key": "legacy"}),
            ["legacy"],
        )

    def test_image_keys_without_primary(self):
        receipt = {"imageKeys": ["a", "b"]}
        self.assertEqual(
            receiptDetailedSummary.collect_image_keys(receipt),
            ["a", "b"],
        )

    def test_non_list_image_keys_ignored(self):
        receipt = {"s3ObjectKey": "k0", "imageKeys": "not-a-list"}
        self.assertEqual(
            receiptDetailedSummary.collect_image_keys(receipt),
            ["k0"],
        )

    def test_empty_receipt(self):
        self.assertEqual(receiptDetailedSummary.collect_image_keys({}), [])


class AddReceiptImageHelperTests(unittest.TestCase):
    def test_existing_keys_match_summary(self):
        receipt = {"s3ObjectKey": "k0", "imageKeys": ["k1", "k0"]}
        self.assertEqual(
            addReceiptImage._existing_image_keys(receipt),
            ["k0", "k1"],
        )

    def test_existing_keys_empty(self):
        self.assertEqual(addReceiptImage._existing_image_keys({}), [])

    def test_execution_name_constraints(self):
        name = addReceiptImage._execution_name(
            "11111111-2222-3333-4444-555555555555",
            "uploads/user/receipt/file.jpg",
        )
        self.assertLessEqual(len(name), 80)
        self.assertRegex(name, r"^[a-zA-Z0-9_-]+$")

    def test_execution_name_is_unique_per_key(self):
        receipt_id = "11111111-2222-3333-4444-555555555555"
        first = addReceiptImage._execution_name(receipt_id, "uploads/u/r/a.jpg")
        second = addReceiptImage._execution_name(receipt_id, "uploads/u/r/b.jpg")
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
