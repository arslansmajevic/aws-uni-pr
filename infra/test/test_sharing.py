"""
Unit tests for the receipt-sharing lambda helpers.

Covers:
- share_common.build_display_name / get_user_id / get_claims
- receipt_helpers.primary_image_key / collect_image_keys / normalize_receipt_items
- addShare.handler validation branches (missing viewer, self-share, success)
"""

import json
import os
import sys
import unittest

LAMBDAS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "lib", "sharing", "lambdas"
)
sys.path.insert(0, LAMBDAS_DIR)

# Stub required environment variables so module-level reads don't fail.
os.environ.setdefault("SHARES_TABLE_NAME", "test-shares")
os.environ.setdefault("VIEWER_INDEX_NAME", "ViewerIndex")
os.environ.setdefault("RECEIPTS_TABLE_NAME", "test-receipts")
os.environ.setdefault("BUCKET_NAME", "test-bucket")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")

import share_common  # noqa: E402
import receipt_helpers  # noqa: E402
import addShare  # noqa: E402


class BuildDisplayNameTests(unittest.TestCase):
    def test_full_name(self):
        self.assertEqual(
            share_common.build_display_name("Ada", "Lovelace", "ada@example.com"),
            "Ada Lovelace",
        )

    def test_falls_back_to_email(self):
        self.assertEqual(
            share_common.build_display_name("", "", "ada@example.com"),
            "ada@example.com",
        )

    def test_partial_name(self):
        self.assertEqual(
            share_common.build_display_name("Ada", None, "ada@example.com"),
            "Ada",
        )


class ClaimsTests(unittest.TestCase):
    def _event(self, claims):
        return {"requestContext": {"authorizer": {"claims": claims}}}

    def test_get_user_id(self):
        self.assertEqual(
            share_common.get_user_id(self._event({"sub": "user-1"})), "user-1"
        )

    def test_get_user_id_missing(self):
        self.assertIsNone(share_common.get_user_id({}))


class ReceiptHelpersTests(unittest.TestCase):
    def test_primary_image_key_aliases(self):
        self.assertEqual(receipt_helpers.primary_image_key({"key": "legacy"}), "legacy")

    def test_collect_image_keys_dedup(self):
        receipt = {"s3ObjectKey": "k0", "imageKeys": ["k1", "k0", "k2"]}
        self.assertEqual(
            receipt_helpers.collect_image_keys(receipt), ["k0", "k1", "k2"]
        )

    def test_normalize_items_from_total(self):
        items = receipt_helpers.normalize_receipt_items(
            {"merchantName": "Shop", "totalAmount": "10"}
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["price"], "10")


class AddShareHandlerTests(unittest.TestCase):
    def setUp(self):
        self._original_put = addShare.shares_table.put_item
        self.put_calls = []

        def fake_put(Item):  # noqa: N803 - matches boto3 signature
            self.put_calls.append(Item)
            return {}

        addShare.shares_table.put_item = fake_put

    def tearDown(self):
        addShare.shares_table.put_item = self._original_put

    def _event(self, body, sub="owner-1"):
        return {
            "httpMethod": "POST",
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "sub": sub,
                        "email": "owner@example.com",
                        "given_name": "Owner",
                        "family_name": "One",
                    }
                }
            },
            "body": json.dumps(body),
        }

    def test_missing_viewer_id(self):
        response = addShare.handler(self._event({}), None)
        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(self.put_calls, [])

    def test_cannot_share_with_self(self):
        response = addShare.handler(
            self._event({"viewerId": "owner-1"}), None
        )
        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(self.put_calls, [])

    def test_successful_share(self):
        response = addShare.handler(
            self._event(
                {
                    "viewerId": "viewer-9",
                    "viewerEmail": "viewer@example.com",
                    "viewerName": "Viewer Nine",
                }
            ),
            None,
        )
        self.assertEqual(response["statusCode"], 201)
        self.assertEqual(len(self.put_calls), 1)
        item = self.put_calls[0]
        self.assertEqual(item["ownerId"], "owner-1")
        self.assertEqual(item["viewerId"], "viewer-9")
        self.assertEqual(item["ownerName"], "Owner One")

    def test_viewer_name_defaults_to_email(self):
        addShare.handler(
            self._event(
                {"viewerId": "viewer-9", "viewerEmail": "viewer@example.com"}
            ),
            None,
        )
        self.assertEqual(self.put_calls[0]["viewerName"], "viewer@example.com")


if __name__ == "__main__":
    unittest.main()
