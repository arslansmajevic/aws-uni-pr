"""
Unit tests for the Plaid token-save Lambda and the receipt-to-transaction
matching pipeline stage.

Covers:
- savePlaidToken.extract_token: field aliases, trimming, missing/blank values.
- match_transaction: amount normalization, date-diff, and the pure
  find_matching_transaction selection logic (amount + timestamp tolerances).
"""

import os
import sys
import unittest

# Make both the banking lambdas and the pipeline lambdas importable.
BANKING_DIR = os.path.join(
    os.path.dirname(__file__), "..", "lib", "banking", "lambdas"
)
PIPELINE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "lib", "storage", "lambdas", "pipeline"
)
sys.path.insert(0, BANKING_DIR)
sys.path.insert(0, PIPELINE_DIR)

# Stub required environment variables so module-level reads don't fail.
os.environ.setdefault("BUCKET_NAME", "test-bucket")
os.environ.setdefault("RECEIPTS_TABLE_NAME", "test-table")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")

import savePlaidToken  # noqa: E402
import savePlaidCredentials  # noqa: E402
import match_transaction  # noqa: E402


class ExtractTokenTests(unittest.TestCase):
    def _event(self, body):
        return {"body": body}

    def test_access_token_field(self):
        self.assertEqual(
            savePlaidToken.extract_token(self._event('{"accessToken": "abc"}')),
            "abc",
        )

    def test_alias_fields(self):
        for field in ("token", "plaidToken", "apiToken"):
            self.assertEqual(
                savePlaidToken.extract_token(self._event('{"%s": "xyz"}' % field)),
                "xyz",
            )

    def test_trims_whitespace(self):
        self.assertEqual(
            savePlaidToken.extract_token(self._event('{"accessToken": "  tok  "}')),
            "tok",
        )

    def test_blank_token_is_none(self):
        self.assertIsNone(
            savePlaidToken.extract_token(self._event('{"accessToken": "   "}'))
        )

    def test_missing_body(self):
        self.assertIsNone(savePlaidToken.extract_token({}))

    def test_invalid_json(self):
        self.assertIsNone(savePlaidToken.extract_token(self._event("not json")))

    def test_non_string_token(self):
        self.assertIsNone(
            savePlaidToken.extract_token(self._event('{"accessToken": 123}'))
        )


class ExtractCredentialsTests(unittest.TestCase):
    def _event(self, body):
        return {"body": body}

    def test_client_id_and_secret(self):
        cid, secret, env = savePlaidCredentials.extract_credentials(
            self._event('{"clientId": "cid", "secret": "sec"}')
        )
        self.assertEqual((cid, secret, env), ("cid", "sec", "sandbox"))

    def test_alias_fields(self):
        cid, secret, env = savePlaidCredentials.extract_credentials(
            self._event('{"client_id": "cid", "plaidSecret": "sec", "env": "production"}')
        )
        self.assertEqual((cid, secret, env), ("cid", "sec", "production"))

    def test_trims_whitespace(self):
        cid, secret, _ = savePlaidCredentials.extract_credentials(
            self._event('{"clientId": "  cid  ", "secret": "  sec  "}')
        )
        self.assertEqual((cid, secret), ("cid", "sec"))

    def test_missing_secret(self):
        cid, secret, _ = savePlaidCredentials.extract_credentials(
            self._event('{"clientId": "cid"}')
        )
        self.assertEqual(cid, "cid")
        self.assertIsNone(secret)

    def test_blank_values(self):
        cid, secret, _ = savePlaidCredentials.extract_credentials(
            self._event('{"clientId": "   ", "secret": "   "}')
        )
        self.assertIsNone(cid)
        self.assertIsNone(secret)

    def test_invalid_json(self):
        self.assertEqual(
            savePlaidCredentials.extract_credentials(self._event("not json")),
            (None, None, None),
        )

    def test_default_env_is_sandbox(self):
        _, _, env = savePlaidCredentials.extract_credentials(
            self._event('{"clientId": "cid", "secret": "sec"}')
        )
        self.assertEqual(env, "sandbox")

    def test_unknown_env_falls_back_to_sandbox(self):
        _, _, env = savePlaidCredentials.extract_credentials(
            self._event('{"clientId": "cid", "secret": "sec", "env": "../evil"}')
        )
        self.assertEqual(env, "sandbox")


class TransactionHelpersTests(unittest.TestCase):
    def test_amount_uses_absolute_value(self):
        self.assertEqual(match_transaction.transaction_amount({"amount": -12.5}), 12.5)
        self.assertEqual(match_transaction.transaction_amount({"amount": 12.5}), 12.5)

    def test_amount_handles_strings(self):
        self.assertEqual(match_transaction.transaction_amount({"amount": "9.99"}), 9.99)

    def test_amount_missing(self):
        self.assertIsNone(match_transaction.transaction_amount({}))

    def test_date_diff(self):
        self.assertEqual(
            match_transaction.date_diff_days("2024-01-10", "2024-01-13"), 3
        )
        self.assertEqual(
            match_transaction.date_diff_days("2024-01-13", "2024-01-10"), 3
        )

    def test_date_diff_handles_datetime_suffix(self):
        self.assertEqual(
            match_transaction.date_diff_days("2024-01-10T14:00:00Z", "2024-01-10"), 0
        )

    def test_date_diff_invalid(self):
        self.assertIsNone(match_transaction.date_diff_days("bad", "2024-01-10"))


class FindMatchingTransactionTests(unittest.TestCase):
    def setUp(self):
        self.transactions = [
            {"transaction_id": "t1", "amount": 5.00, "date": "2024-01-10"},
            {"transaction_id": "t2", "amount": 19.99, "date": "2024-01-11"},
            {"transaction_id": "t3", "amount": 19.99, "date": "2024-01-20"},
        ]

    def test_exact_amount_and_date(self):
        match = match_transaction.find_matching_transaction(
            self.transactions, 19.99, "2024-01-11"
        )
        self.assertEqual(match["transaction_id"], "t2")

    def test_date_outside_window_is_skipped(self):
        # t3 has the right amount but is 9 days away from the receipt date.
        match = match_transaction.find_matching_transaction(
            self.transactions, 19.99, "2024-01-11", max_day_diff=3
        )
        self.assertEqual(match["transaction_id"], "t2")

    def test_amount_outside_tolerance_is_skipped(self):
        match = match_transaction.find_matching_transaction(
            self.transactions, 19.50, "2024-01-11"
        )
        self.assertIsNone(match)

    def test_amount_within_tolerance(self):
        match = match_transaction.find_matching_transaction(
            self.transactions, 19.98, "2024-01-11", amount_tolerance=0.02
        )
        self.assertEqual(match["transaction_id"], "t2")

    def test_closest_amount_then_date_wins(self):
        txns = [
            {"transaction_id": "a", "amount": 20.01, "date": "2024-01-11"},
            {"transaction_id": "b", "amount": 20.00, "date": "2024-01-13"},
        ]
        match = match_transaction.find_matching_transaction(
            txns, 20.00, "2024-01-11", amount_tolerance=0.05, max_day_diff=3
        )
        # Exact amount wins over closer date.
        self.assertEqual(match["transaction_id"], "b")

    def test_none_when_no_candidates(self):
        self.assertIsNone(
            match_transaction.find_matching_transaction([], 10.0, "2024-01-11")
        )

    def test_none_when_target_amount_missing(self):
        self.assertIsNone(
            match_transaction.find_matching_transaction(
                self.transactions, None, "2024-01-11"
            )
        )


if __name__ == "__main__":
    unittest.main()
