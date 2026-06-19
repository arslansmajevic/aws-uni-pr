"""
Unit tests for the receipt processing pipeline Lambda functions.

Tests cover:
- Decimal parsing (US, European, negative values, currency prefixes)
- normalize.py: date/time normalization, line-item extraction, categorization
- validate.py: line arithmetic, subtotal/total reconciliation, repairRequired logic
- repair_items.py: repair response validation (strict schema enforcement)
- preflight.py: file format detection
"""

import json
import sys
import os
import unittest
from decimal import Decimal

# Add the pipeline directory to the path so we can import the modules directly.
PIPELINE_DIR = os.path.join(os.path.dirname(__file__), "..", "lib", "storage", "lambdas", "pipeline")
sys.path.insert(0, PIPELINE_DIR)

# Stub out required environment variables so module-level reads don't fail.
os.environ.setdefault("BUCKET_NAME", "test-bucket")
os.environ.setdefault("RECEIPTS_TABLE_NAME", "test-table")
os.environ.setdefault("REPAIR_MODEL_ID", "eu.amazon.nova-pro-v1:0")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")

# ---------------------------------------------------------------------------
# normalize.py tests
# ---------------------------------------------------------------------------

from normalize import (
    parse_decimal,
    format_decimal,
    normalize_date,
    normalize_time,
    detect_currency,
    extract_summary,
    extract_line_items,
    classify_category,
)


class TestParseDecimal(unittest.TestCase):
    def test_us_decimal(self):
        self.assertEqual(parse_decimal("12.50"), Decimal("12.50"))

    def test_european_comma_decimal(self):
        self.assertEqual(parse_decimal("1,49"), Decimal("1.49"))

    def test_european_mixed_separators(self):
        self.assertEqual(parse_decimal("1.234,56"), Decimal("1234.56"))

    def test_multiple_dot_thousands_only(self):
        # "1.234.567" — all dots are thousands separators, no decimal part
        self.assertEqual(parse_decimal("1.234.567"), Decimal("1234567"))

    def test_us_thousands_separator(self):
        self.assertEqual(parse_decimal("1,234.56"), Decimal("1234.56"))

    def test_negative_plain(self):
        d = parse_decimal("-0.40")
        self.assertEqual(d, Decimal("-0.40"))

    def test_negative_accounting_parens(self):
        d = parse_decimal("(1.50)")
        self.assertEqual(d, Decimal("-1.50"))

    def test_negative_trailing_minus(self):
        d = parse_decimal("1.49-")
        self.assertEqual(d, Decimal("-1.49"))

    def test_currency_prefix_eur(self):
        self.assertEqual(parse_decimal("€ 12.50"), Decimal("12.50"))

    def test_currency_prefix_chf(self):
        self.assertEqual(parse_decimal("CHF 12.50"), Decimal("12.50"))

    def test_currency_prefix_usd(self):
        self.assertEqual(parse_decimal("$5.99"), Decimal("5.99"))

    def test_none_input(self):
        self.assertIsNone(parse_decimal(None))

    def test_empty_string(self):
        self.assertIsNone(parse_decimal(""))

    def test_non_numeric(self):
        self.assertIsNone(parse_decimal("N/A"))

    def test_zero(self):
        self.assertEqual(parse_decimal("0.00"), Decimal("0"))

    def test_large_amount(self):
        self.assertEqual(parse_decimal("1234.56"), Decimal("1234.56"))

    def test_integer_only(self):
        self.assertEqual(parse_decimal("10"), Decimal("10"))


class TestFormatDecimal(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(format_decimal(Decimal("12.5")), "12.50")

    def test_none(self):
        self.assertIsNone(format_decimal(None))

    def test_negative(self):
        self.assertEqual(format_decimal(Decimal("-0.40")), "-0.40")


class TestNormalizeDate(unittest.TestCase):
    def test_iso_format(self):
        self.assertEqual(normalize_date("2024-12-25"), "2024-12-25")

    def test_eu_slashes(self):
        self.assertEqual(normalize_date("25/12/2024"), "2024-12-25")

    def test_us_slashes(self):
        self.assertEqual(normalize_date("12/25/2024"), "2024-12-25")

    def test_dot_separated(self):
        self.assertEqual(normalize_date("25.12.2024"), "2024-12-25")

    def test_month_name(self):
        self.assertEqual(normalize_date("25 Dec 2024"), "2024-12-25")

    def test_none(self):
        self.assertIsNone(normalize_date(None))

    def test_invalid(self):
        self.assertIsNone(normalize_date("not-a-date"))


class TestNormalizeTime(unittest.TestCase):
    def test_hhmmss(self):
        self.assertEqual(normalize_time("14:30:00"), "14:30:00")

    def test_hhmm(self):
        self.assertEqual(normalize_time("14:30"), "14:30:00")

    def test_12h(self):
        self.assertEqual(normalize_time("02:30 PM"), "14:30:00")

    def test_none(self):
        self.assertIsNone(normalize_time(None))


class TestClassifyCategory(unittest.TestCase):
    def test_grocery(self):
        self.assertEqual(classify_category("Migros", []), "Groceries")

    def test_dining(self):
        self.assertEqual(classify_category("Pizza Restaurant", []), "Dining")

    def test_transport(self):
        self.assertEqual(classify_category("Uber", []), "Transport")

    def test_health(self):
        self.assertEqual(classify_category("City Pharmacy", []), "Health")

    def test_other(self):
        # "Unknown Store" contains "store" which matches Shopping keywords.
        self.assertEqual(classify_category("Unknown Store", []), "Shopping")

    def test_shopping_store_keyword(self):
        self.assertEqual(classify_category("IKEA", []), "Shopping")

    def test_item_keyword(self):
        # Grocery detected via a supermarket keyword in item name
        self.assertEqual(
            classify_category(None, [{"name": "migros weekly deal"}, {"name": "apple"}]),
            "Groceries",
        )

    def test_fallback_other(self):
        # No recognizable keywords → Other
        self.assertEqual(classify_category(None, [{"name": "xyz123"}, {"name": "abc"}]), "Other")

    def test_none_merchant_none_items(self):
        self.assertEqual(classify_category(None, []), "Other")


class TestExtractLineItems(unittest.TestCase):
    def _make_doc(self, rows):
        """Build a minimal Textract ExpenseDocuments structure."""
        line_items = []
        for row in rows:
            fields = []
            for ftype, value, conf in row:
                fields.append({
                    "Type": {"Text": ftype},
                    "ValueDetection": {"Text": value, "Confidence": conf},
                })
            line_items.append({"LineItemExpenseFields": fields})
        return [{"SummaryFields": [], "LineItemGroups": [{"LineItems": line_items}]}]

    def test_unit_price_and_price_are_separate(self):
        """UNIT_PRICE → unitPrice  and  PRICE → lineTotal — must not collapse."""
        docs = self._make_doc([
            [("ITEM", "Widget", 99.0), ("UNIT_PRICE", "1.49", 98.0), ("PRICE", "2.98", 97.0), ("QUANTITY", "2", 99.0)],
        ])
        items, truncated = extract_line_items(docs)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["unitPrice"], "1.49")
        self.assertEqual(items[0]["lineTotal"], "2.98")
        self.assertEqual(items[0]["quantity"], "2")
        self.assertFalse(truncated)

    def test_negative_line_total_preserved(self):
        """Discount lines (negative amounts) must not be silently dropped."""
        docs = self._make_doc([
            [("ITEM", "Coupon", 95.0), ("PRICE", "-5.00", 92.0)],
        ])
        items, _ = extract_line_items(docs)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["lineTotal"], "-5.00")

    def test_truncation_flag(self):
        """More than MAX_LINE_ITEMS rows should set the truncated flag."""
        rows = [[("ITEM", f"Item {i}", 90.0), ("PRICE", "1.00", 90.0)] for i in range(110)]
        docs = self._make_doc(rows)
        items, truncated = extract_line_items(docs)
        self.assertTrue(truncated)
        self.assertEqual(len(items), 100)

    def test_source_confidence_min(self):
        """sourceConfidence should be the minimum field confidence / 100."""
        docs = self._make_doc([
            [("ITEM", "Bread", 80.0), ("PRICE", "2.50", 60.0)],
        ])
        items, _ = extract_line_items(docs)
        self.assertAlmostEqual(items[0]["sourceConfidence"], 0.60, places=2)

    def test_no_items(self):
        docs = [{"SummaryFields": [], "LineItemGroups": []}]
        items, truncated = extract_line_items(docs)
        self.assertEqual(items, [])
        self.assertFalse(truncated)


# ---------------------------------------------------------------------------
# validate.py tests
# ---------------------------------------------------------------------------

from validate import (
    check_line_arithmetic,
    check_line_coverage,
    check_receipt_arithmetic,
    compute_confidence,
    validate_amount,
    validate_date,
    validate_currency,
)


class TestCheckLineArithmetic(unittest.TestCase):
    def test_correct_arithmetic(self):
        items = [{"quantity": "2", "unitPrice": "1.49", "lineTotal": "2.98"}]
        self.assertEqual(check_line_arithmetic(items), [])

    def test_mismatched_arithmetic(self):
        items = [{"quantity": "2", "unitPrice": "1.49", "lineTotal": "5.00"}]
        issues = check_line_arithmetic(items)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["severity"], "warning")
        self.assertTrue(issues[0].get("repairHint"))

    def test_missing_fields_skipped(self):
        items = [{"lineTotal": "5.00"}]  # no qty or unitPrice → skip check
        self.assertEqual(check_line_arithmetic(items), [])

    def test_discount_item(self):
        # discount: qty × unitPrice should equal lineTotal (both negative OK)
        items = [{"quantity": "1", "unitPrice": "-2.00", "lineTotal": "-2.00"}]
        self.assertEqual(check_line_arithmetic(items), [])


class TestCheckLineCoverage(unittest.TestCase):
    def test_matching_subtotal(self):
        items = [{"lineTotal": "5.00"}, {"lineTotal": "3.00"}]
        issues = check_line_coverage(items, "8.00")
        self.assertEqual(issues, [])

    def test_mismatched_subtotal(self):
        items = [{"lineTotal": "5.00"}, {"lineTotal": "3.00"}]
        issues = check_line_coverage(items, "20.00")
        self.assertEqual(len(issues), 1)
        self.assertTrue(issues[0].get("repairHint"))

    def test_no_subtotal(self):
        items = [{"lineTotal": "5.00"}]
        self.assertEqual(check_line_coverage(items, None), [])


class TestCheckReceiptArithmetic(unittest.TestCase):
    def test_simple_correct(self):
        data = {"totalAmount": "10.00", "subtotalAmount": "9.00", "taxAmount": "1.00"}
        self.assertEqual(check_receipt_arithmetic(data), [])

    def test_with_discount(self):
        data = {
            "totalAmount": "8.50",
            "subtotalAmount": "10.00",
            "taxAmount": "0.50",
            "discountAmount": "2.00",
        }
        self.assertEqual(check_receipt_arithmetic(data), [])

    def test_mismatch(self):
        data = {"totalAmount": "20.00", "subtotalAmount": "9.00", "taxAmount": "1.00"}
        issues = check_receipt_arithmetic(data)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["severity"], "warning")

    def test_missing_total_skipped(self):
        data = {"subtotalAmount": "9.00"}
        self.assertEqual(check_receipt_arithmetic(data), [])


class TestValidateAmount(unittest.TestCase):
    def test_valid_positive(self):
        self.assertEqual(validate_amount("12.50", "totalAmount"), [])

    def test_negative_not_allowed(self):
        issues = validate_amount("-1.00", "totalAmount", allow_negative=False)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["severity"], "error")

    def test_negative_allowed(self):
        self.assertEqual(validate_amount("-1.00", "discountAmount", allow_negative=True), [])

    def test_none_valid(self):
        self.assertEqual(validate_amount(None, "taxAmount"), [])

    def test_invalid_string(self):
        issues = validate_amount("abc", "totalAmount")
        self.assertEqual(len(issues), 1)


class TestValidateDate(unittest.TestCase):
    def test_valid_date(self):
        self.assertEqual(validate_date("2024-06-15"), [])

    def test_invalid_format(self):
        self.assertEqual(len(validate_date("15/06/24")), 1)

    def test_none(self):
        self.assertEqual(validate_date(None), [])

    def test_future_date(self):
        self.assertEqual(len(validate_date("2099-01-01")), 1)


class TestValidateCurrency(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_currency("CHF"), [])

    def test_invalid(self):
        self.assertEqual(len(validate_currency("swiss franc")), 1)

    def test_none(self):
        self.assertEqual(validate_currency(None), [])


class TestComputeConfidence(unittest.TestCase):
    def test_full_data_no_issues(self):
        data = {
            "merchantName": "Migros",
            "totalAmount": "25.00",
            "receiptDate": "2024-06-15",
            "receiptItems": [{"lineTotal": "25.00"}],
            "currency": "CHF",
            "subtotalAmount": "24.00",
            "taxAmount": "1.00",
            "category": "Groceries",
        }
        conf = compute_confidence(data, [])
        self.assertGreater(conf, 0.8)

    def test_empty_data(self):
        conf = compute_confidence({}, [])
        self.assertEqual(conf, 0.0)

    def test_errors_reduce_confidence(self):
        data = {"merchantName": "Shop", "totalAmount": "10.00", "receiptDate": "2024-01-01"}
        no_issues = compute_confidence(data, [])
        with_errors = compute_confidence(data, [{"severity": "error"}, {"severity": "error"}])
        self.assertGreater(no_issues, with_errors)


# ---------------------------------------------------------------------------
# repair_items.py tests
# ---------------------------------------------------------------------------

from repair_items import validate_repair_response, _validate_patch


class TestValidateRepairPatch(unittest.TestCase):
    def _make_items(self, n=5):
        return [{"name": f"Item {i}", "lineTotal": "1.00"} for i in range(n)]

    def test_valid_patch(self):
        patch = {"itemIndex": 0, "field": "quantity", "value": "2", "confidence": 0.9}
        valid, reason = _validate_patch(patch, 5, self._make_items())
        self.assertTrue(valid)

    def test_invalid_index_negative(self):
        patch = {"itemIndex": -1, "field": "quantity", "value": "2"}
        valid, reason = _validate_patch(patch, 5, self._make_items())
        self.assertFalse(valid)

    def test_invalid_index_out_of_range(self):
        patch = {"itemIndex": 10, "field": "quantity", "value": "2"}
        valid, reason = _validate_patch(patch, 5, self._make_items())
        self.assertFalse(valid)

    def test_invalid_field(self):
        patch = {"itemIndex": 0, "field": "invalidField", "value": "x"}
        valid, reason = _validate_patch(patch, 5, self._make_items())
        self.assertFalse(valid)

    def test_invalid_money_value(self):
        patch = {"itemIndex": 0, "field": "unitPrice", "value": "not-money"}
        valid, reason = _validate_patch(patch, 5, self._make_items())
        self.assertFalse(valid)

    def test_valid_negative_discount(self):
        patch = {"itemIndex": 0, "field": "discount", "value": "-2.50"}
        valid, reason = _validate_patch(patch, 5, self._make_items())
        self.assertTrue(valid)

    def test_null_value_allowed(self):
        patch = {"itemIndex": 0, "field": "quantity", "value": None}
        valid, reason = _validate_patch(patch, 5, self._make_items())
        self.assertTrue(valid)

    def test_invalid_confidence_out_of_range(self):
        patch = {"itemIndex": 0, "field": "name", "value": "Widget", "confidence": 1.5}
        valid, reason = _validate_patch(patch, 5, self._make_items())
        self.assertFalse(valid)

    def test_validate_response_filters_invalid(self):
        raw = {
            "patches": [
                {"itemIndex": 0, "field": "quantity", "value": "2", "confidence": 0.9},   # valid
                {"itemIndex": 99, "field": "quantity", "value": "2"},                       # invalid index
                {"itemIndex": 1, "field": "badField", "value": "x"},                        # invalid field
            ]
        }
        accepted = validate_repair_response(raw, 5, self._make_items())
        self.assertEqual(len(accepted), 1)

    def test_validate_response_empty_patches(self):
        accepted = validate_repair_response({"patches": []}, 5, self._make_items())
        self.assertEqual(accepted, [])

    def test_validate_response_malformed(self):
        with self.assertRaises(ValueError):
            validate_repair_response("not a dict", 5, self._make_items())

    def test_validate_response_missing_patches_key(self):
        with self.assertRaises(ValueError):
            validate_repair_response({"other": []}, 5, self._make_items())


# ---------------------------------------------------------------------------
# preflight.py tests
# ---------------------------------------------------------------------------

from preflight import _detect_format


class TestDetectFormat(unittest.TestCase):
    def test_jpeg(self):
        header = b"\xff\xd8\xff\xe0" + b"\x00" * 12
        self.assertEqual(_detect_format(header), "jpeg")

    def test_png(self):
        header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
        self.assertEqual(_detect_format(header), "png")

    def test_pdf(self):
        header = b"%PDF-1.4" + b"\x00" * 8
        self.assertEqual(_detect_format(header), "pdf")

    def test_tiff_le(self):
        header = b"II\x2a\x00" + b"\x00" * 12
        self.assertEqual(_detect_format(header), "tiff_le")

    def test_tiff_be(self):
        header = b"MM\x00\x2a" + b"\x00" * 12
        self.assertEqual(_detect_format(header), "tiff_be")

    def test_webp(self):
        header = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 4
        self.assertEqual(_detect_format(header), "webp")

    def test_unknown(self):
        header = b"\x00\x01\x02\x03" + b"\x00" * 12
        self.assertEqual(_detect_format(header), "unknown")


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Multi-image pipeline: preflight + extract_textract
# ---------------------------------------------------------------------------

from unittest.mock import patch, MagicMock, call
from preflight import _validate_and_copy, handler as preflight_handler
from extract_textract import _analyze_expense, handler as textract_handler


class TestPreflightMultiImage(unittest.TestCase):
    """Preflight handler supports a 'keys' array for multi-image receipts."""

    def _make_s3(self, file_size=1024, fmt_header=b"\xff\xd8\xff" + b"\x00" * 13):
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {"ContentLength": file_size}
        body_mock = MagicMock()
        body_mock.read.return_value = fmt_header
        mock_s3.get_object.return_value = {"Body": body_mock}
        mock_s3.copy_object.return_value = {}
        return mock_s3

    def test_single_key_produces_single_normalized_key(self):
        event = {
            "bucket": "test-bucket",
            "key": "uploads/user1/receipt1/img.jpg",
            "userId": "user1",
            "receiptId": "receipt1",
        }
        with patch("preflight.s3_client", self._make_s3()):
            result = preflight_handler(event, None)

        self.assertIn("normalizedInputKey", result)
        self.assertIn("normalizedInputKeys", result)
        self.assertEqual(len(result["normalizedInputKeys"]), 1)
        self.assertEqual(result["normalizedInputKey"], result["normalizedInputKeys"][0])

    def test_keys_array_produces_multiple_normalized_keys(self):
        event = {
            "bucket": "test-bucket",
            "key": "uploads/user1/receipt1/img-0.jpg",
            "keys": [
                "uploads/user1/receipt1/img-0.jpg",
                "uploads/user1/receipt1/img-1.jpg",
            ],
            "userId": "user1",
            "receiptId": "receipt1",
        }
        with patch("preflight.s3_client", self._make_s3()):
            result = preflight_handler(event, None)

        self.assertEqual(len(result["normalizedInputKeys"]), 2)
        # normalizedInputKey must equal the first entry (backward compat).
        self.assertEqual(result["normalizedInputKey"], result["normalizedInputKeys"][0])
        # Each normalized key should contain an index suffix.
        self.assertIn("receipt-0", result["normalizedInputKeys"][0])
        self.assertIn("receipt-1", result["normalizedInputKeys"][1])

    def test_keys_array_preserves_original_fields(self):
        event = {
            "bucket": "test-bucket",
            "key": "uploads/user1/receipt1/img-0.jpg",
            "keys": ["uploads/user1/receipt1/img-0.jpg", "uploads/user1/receipt1/img-1.jpg"],
            "userId": "user1",
            "receiptId": "receipt1",
        }
        with patch("preflight.s3_client", self._make_s3()):
            result = preflight_handler(event, None)

        self.assertEqual(result["userId"], "user1")
        self.assertEqual(result["receiptId"], "receipt1")
        self.assertIn("preflightAt", result)


class TestExtractTextractMultiImage(unittest.TestCase):
    """extract_textract handler merges ExpenseDocuments from multiple images."""

    def _make_mocks(self, doc_lists):
        """
        doc_lists: list of lists, one per image call.
        Returns (mock_s3, mock_textract).
        """
        mock_s3 = MagicMock()
        mock_textract = MagicMock()

        side_effects = []
        for docs in doc_lists:
            side_effects.append({"ExpenseDocuments": docs})
        mock_textract.analyze_expense.side_effect = side_effects

        return mock_s3, mock_textract

    def test_single_normalized_key_path(self):
        """Falls back to normalizedInputKey when normalizedInputKeys is absent."""
        event = {
            "bucket": "test-bucket",
            "key": "uploads/u/r/img.jpg",
            "normalizedInputKey": "normalized-inputs/u/r/receipt-0.jpg",
            "userId": "u",
            "receiptId": "r",
        }
        docs = [{"SummaryFields": [], "LineItemGroups": []}]
        mock_s3, mock_textract = self._make_mocks([docs])

        with patch("extract_textract.s3_client", mock_s3), \
             patch("extract_textract.textract_client", mock_textract):
            result = textract_handler(event, None)

        mock_textract.analyze_expense.assert_called_once()
        self.assertEqual(result["textractKey"], "raw-extractions/u/r/textract.json")

    def test_multi_normalized_keys_merged(self):
        """All ExpenseDocuments from multiple images are merged into one JSON."""
        event = {
            "bucket": "test-bucket",
            "key": "uploads/u/r/img-0.jpg",
            "normalizedInputKeys": [
                "normalized-inputs/u/r/receipt-0.jpg",
                "normalized-inputs/u/r/receipt-1.jpg",
            ],
            "userId": "u",
            "receiptId": "r",
        }
        docs_0 = [{"SummaryFields": [{"Type": {"Text": "VENDOR_NAME"}}], "LineItemGroups": []}]
        docs_1 = [{"SummaryFields": [{"Type": {"Text": "TOTAL"}}], "LineItemGroups": []}]
        mock_s3, mock_textract = self._make_mocks([docs_0, docs_1])

        captured = {}

        def capture_put(**kwargs):
            import json as _json
            captured["body"] = _json.loads(kwargs["Body"])
            return {}

        mock_s3.put_object.side_effect = lambda **kw: captured.update(
            {"body": __import__("json").loads(kw["Body"])}
        ) or {}

        with patch("extract_textract.s3_client", mock_s3), \
             patch("extract_textract.textract_client", mock_textract):
            result = textract_handler(event, None)

        self.assertEqual(mock_textract.analyze_expense.call_count, 2)
        # The merged JSON written to S3 should contain docs from both images.
        put_call_args = mock_s3.put_object.call_args
        import json as _json
        merged = _json.loads(put_call_args.kwargs["Body"])
        self.assertEqual(len(merged["ExpenseDocuments"]), 2)

    def test_multi_keys_returns_single_textract_key(self):
        """Only one textractKey is returned regardless of image count."""
        event = {
            "bucket": "test-bucket",
            "key": "uploads/u/r/img-0.jpg",
            "normalizedInputKeys": [
                "normalized-inputs/u/r/receipt-0.jpg",
                "normalized-inputs/u/r/receipt-1.jpg",
                "normalized-inputs/u/r/receipt-2.jpg",
            ],
            "userId": "u",
            "receiptId": "r",
        }
        mock_s3, mock_textract = self._make_mocks([[], [], []])

        with patch("extract_textract.s3_client", mock_s3), \
             patch("extract_textract.textract_client", mock_textract):
            result = textract_handler(event, None)

        self.assertEqual(mock_textract.analyze_expense.call_count, 3)
        self.assertEqual(result["textractKey"], "raw-extractions/u/r/textract.json")
        self.assertEqual(result["extractionProvider"], "TEXTRACT_ANALYZE_EXPENSE")
