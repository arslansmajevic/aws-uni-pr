import os
import json
import boto3
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])

textract = boto3.client("textract")
bedrock = boto3.client("bedrock-runtime")

BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5")



def now_iso():
    return datetime.now(timezone.utc).isoformat()


def update_status(user_id, receipt_id, status, extra_fields=None):
    update_expr = "SET processingStatus = :s, updatedAt = :u"
    expr_values = {":s": status, ":u": now_iso()}

    if extra_fields:
        for key, value in extra_fields.items():
            update_expr += f", {key} = :{key}"
            expr_values[f":{key}"] = value

    table.update_item(
        Key={"userId": user_id, "receiptId": receipt_id},
        UpdateExpression=update_expr,
        ExpressionAttributeValues=expr_values,
    )



def extract_receipt_data(bucket, key):
    response = textract.analyze_expense(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )

    result = {
        "merchantName": None,
        "receiptDate": None,
        "receiptTime": None,
        "totalAmount": None,
        "subtotalAmount": None,
        "taxAmount": None,
        "tipAmount": None,
        "currency": None,
        "lineItems": [],
        "rawText": "",
    }

    for doc in response.get("ExpenseDocuments", []):

        for field in doc.get("SummaryFields", []):
            field_type = field.get("Type", {}).get("Text", "")
            value = field.get("ValueDetection", {}).get("Text", "")

            if not value:
                continue

            mapping = {
                "VENDOR_NAME":            "merchantName",
                "INVOICE_RECEIPT_DATE":   "receiptDate",
                "TIME":                   "receiptTime",
                "TOTAL":                  "totalAmount",
                "SUBTOTAL":               "subtotalAmount",
                "TAX":                    "taxAmount",
                "GRATUITY":               "tipAmount",
                "CURRENCY":               "currency",
            }

            if field_type in mapping:
                result[mapping[field_type]] = value

        for group in doc.get("LineItemGroups", []):
            for line in group.get("LineItems", []):
                item = {}
                for field in line.get("LineItemExpenseFields", []):
                    field_type = field.get("Type", {}).get("Text", "")
                    value = field.get("ValueDetection", {}).get("Text", "")
                    if field_type == "ITEM":
                        item["description"] = value
                    elif field_type == "PRICE":
                        item["totalPrice"] = value
                    elif field_type == "QUANTITY":
                        item["quantity"] = value
                if item:
                    result["lineItems"].append(item)

    blocks = textract.detect_document_text(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    result["rawText"] = " ".join(
        b.get("Text", "")
        for b in blocks.get("Blocks", [])
        if b.get("BlockType") == "LINE"
    )

    return result



CATEGORIES = ["Groceries", "Dining", "Entertainment", "Transport",
               "Health", "Shopping", "Utilities", "Other"]

def categorize_receipt(extracted):
    merchant = extracted.get("merchantName") or "Unknown"
    items_text = ", ".join(
        i.get("description", "") for i in extracted.get("lineItems", []) if i.get("description")
    ) or "N/A"
    raw = (extracted.get("rawText") or "")[:500] # max 500 chars of raw text to avoid hitting token limits

    prompt = f"""You are a receipt categorization assistant.
                Categorize this receipt into EXACTLY ONE of these categories:
                {", ".join(CATEGORIES)}

                Receipt details:
                - Merchant: {merchant}
                - Items: {items_text}
                - Raw text snippet: {raw}

                Reply with ONLY the category name, nothing else."""

    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": prompt}],
        }),
    )

    body = json.loads(response["body"].read())
    category = body["content"][0]["text"].strip()

    if category not in CATEGORIES:
        print(f"Unexpected category from Bedrock: '{category}', defaulting to 'Other'")
        category = "Other"

    return category



def handler(event, context):
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]

        print(f"Processing: bucket={bucket}, key={key}")

        parts = key.split("/")
        if len(parts) < 4:
            print(f"Skipping unexpected key format: {key}")
            continue

        user_id = parts[1]
        receipt_id = parts[2]

        update_status(user_id, receipt_id, "PROCESSING")
        print(f"Status → PROCESSING")

        try:
            print("Calling Textract...")
            extracted = extract_receipt_data(bucket, key)
            print(f"Textract done. Merchant: {extracted.get('merchantName')}, Total: {extracted.get('totalAmount')}")

            print("Calling Bedrock...")
            category = categorize_receipt(extracted)
            print(f"Bedrock category: {category}")

            update_status(user_id, receipt_id, "CATEGORIZED", extra_fields={
                "merchantName":    extracted.get("merchantName"),
                "receiptDate":     extracted.get("receiptDate"),
                "receiptTime":     extracted.get("receiptTime"),
                "totalAmount":     extracted.get("totalAmount"),
                "subtotalAmount":  extracted.get("subtotalAmount"),
                "taxAmount":       extracted.get("taxAmount"),
                "tipAmount":       extracted.get("tipAmount"),
                "currency":        extracted.get("currency"),
                "lineItems":       extracted.get("lineItems", []),
                "category":        category,
            })
            print(f"Status → CATEGORIZED ✓")

        except Exception as e:
            print(f"Error processing {key}: {str(e)}")
            update_status(user_id, receipt_id, "FAILED", extra_fields={
                "errorMessage": str(e)
            })