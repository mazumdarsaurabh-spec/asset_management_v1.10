import os
import base64
import requests
import json
import time
from django.conf import settings
from decimal import Decimal
CATEGORY_KEYWORDS = {
    "server": "Server",
    "docking": "Docking Station",
    "monitor": "Monitor",
    "printer": "Printer",
    "cable": "Cables",
    "charger": "Chargers",
    "laptop": "Laptop",
}

def map_category(item_name, description):
    """Map to category by keyword, fallback to 'Other'."""
    text = f"{item_name} {description}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    return "Other"

def normalize_items(scanned_items, invoice_number=None, temp_file_url=None):
    """Ensure all items are returned with consistent structure and safe defaults."""
    normalized = []

    for item in scanned_items or []:
        try:
            quantity = int(item.get("quantity", 1)) or 1
        except (ValueError, TypeError):
            quantity = 1

        try:
            unit_price = float(item.get("unit_price", 0.0)) or 0.0
        except (ValueError, TypeError):
            unit_price = 0.0

        total_price = item.get("total_price")
        if not total_price:
            total_price = quantity * unit_price

        normalized.append({
            "category": map_category(item.get("item_name", ""), item.get("description", "")),
            "item_name": item.get("item_name") or item.get("description", "") or "Unknown Item",
            "description": item.get("description", ""),
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": total_price,
            "serial_number": item.get("serial_number", ""),
            "invoice_number": invoice_number,
            "invoice_file_url": temp_file_url,
        })

    return normalized


def get_text_from_image(image_file):
    """
    Extracts structured JSON data from an invoice image using the Gemini API.
    Always returns a list of dictionaries with correct mapping.
    """
    try:
        image_data = image_file.read()
        encoded_image = base64.b64encode(image_data).decode("utf-8")
        mime_type = image_file.content_type

        # IMPORTANT: Ensure your GEMINI_API_KEY is correctly set in Django's settings.py
        # You cannot use a placeholder key or an invalid key.
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            print("Error: GEMINI_API_KEY is not set in Django settings")
            return []

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"

        prompt = (
            "You are an expert at extracting structured data from invoices. "
            "Analyze the provided image and extract all line items in a JSON array. "
            "Each line item should be an object with the following keys: "
            "'category': The category of the item. You should match with the keyword with the drop down list( 'Server', 'Laptop', etc.) ,if not found choose Other. "
            " - 'item_name': The name of the item (short name like 'Laptop', 'Monitor', etc.). "
            " - 'description': A longer description of the item (model, brand, details). "
            " - 'quantity': Quantity of the item as a number. "
            " - 'unit_price': The price per unit as a number. "
            " - 'total_price': The total price for that line item as a number. "
            " - 'serial_number': Serial number of the item, if available (string or null). "
            "If any detail is missing, use null. "
            "Do not add any explanation, only return valid JSON."
        )

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": mime_type, "data": encoded_image}}
                ]
            }],
            "generationConfig": {"responseMimeType": "application/json"}
        }

        max_retries = 5
        for retry_count in range(max_retries):
            try:
                response = requests.post(api_url, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
                response.raise_for_status()
                result = response.json()

                if result and result.get("candidates"):
                    text_content = result["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"✅ Gemini API Raw Response: \n{text_content}") # DEBUG PRINT
                    # Add a robust JSON parsing block
                    try:
                        parsed = json.loads(text_content)
                        print(f"✅ Parsed JSON Object: \n{json.dumps(parsed, indent=2)}")
                        return normalize_items(parsed)
                    except json.JSONDecodeError as e:
                        print(f"API returned invalid JSON: {e}")
                        print(f"Received content: {text_content}")
                        return []
                else:
                    print("API call succeeded but no candidates returned")
                    return []

            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                print(f"API call failed: {e}")
                if retry_count < max_retries - 1:
                    delay = 2 ** (retry_count + 1)
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    return []

    except Exception as e:
        print(f" An error occurred during OCR parsing: {e}")
        return []


def extract_details_with_llm(file_path):
    """
    Placeholder function to handle non-image files.
    """
    # ✅ FIX: This function must return a list, not a single dictionary.
    return [{
        "category": "Sample Category",
        "item_name": "Sample Item",
        "description": "Sample Item from Document",
        "quantity": 1,
        "unit_price": 99.99,
        "total_price": 99.99,
        "serial_number": "DOC-12345"
    }]