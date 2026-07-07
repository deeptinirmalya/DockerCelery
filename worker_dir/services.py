import json
import re
from datetime import datetime
from typing import Optional, Dict, Any
import requests
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

load_dotenv()




def sanitize_amount(amount_str: str) -> Optional[float]:
    try:
        clean_amount = re.sub(r'[^\d.]', '', str(amount_str).strip())
        return float(clean_amount) if clean_amount else None
    except (ValueError, AttributeError):
        return None


def normalize_bank_name(bank_str: str) -> str:
    if not bank_str:
        return "ippb" 
    
    normalized = str(bank_str).strip().lower()
    
    bank_mapping = {
        "ippb": ["ippb", "india post", "post payment"],
        "sbi": ["sbi", "state bank", "state bank of india"],
        "hdfc": ["hdfc", "hdfc bank"],
        "icici": ["icici", "icici bank"],
        "axis": ["axis", "axis bank"],
        "kotak": ["kotak", "kotak mahindra"],
        "yes": ["yes", "yes bank"],
        "idbi": ["idbi", "idbi bank"],
        "okaxis": ["okaxis", "ok axis"],
        "okybl": ["okybl", "ok ybl"],
        "oksbi": ["oksbi", "ok sbi"],
    }
    
    for standard_name, aliases in bank_mapping.items():
        if any(alias in normalized for alias in aliases):
            return standard_name
    
    return bank_str.strip()


def parse_date(date_str: str) -> str:

    if not date_str:
        return None
    
    date_str = str(date_str).strip()
    
    if date_str.lower() in ["today", "yesterday"]:
        return date_str.lower()
    
    date_formats = [
        "%d %b %Y",      
        "%d-%m-%Y",      
        "%d/%m/%Y",      
        "%d %B %Y",      
        "%d.%m.%Y",      
    ]
    
    for fmt in date_formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return date_str


def parse_time(time_str: str) -> str:
    if not time_str:
        return "00:00:00"
    
    time_str = str(time_str).strip().upper()
    time_str = re.sub(r'\s+', '', time_str)  
    
    time_12hr_formats = [
        "%I:%M%p",       
        "%I:%M:%S%p",   
        "%H:%M%p",       
    ]
    
    for fmt in time_12hr_formats:
        try:
            parsed = datetime.strptime(time_str, fmt)
            return parsed.strftime("%H:%M:%S")
        except ValueError:
            continue
    
    time_24hr_formats = [
        "%H:%M:%S",   
        "%H:%M",         
    ]
    
    for fmt in time_24hr_formats:
        try:
            parsed = datetime.strptime(time_str.replace("PM", "").replace("AM", ""), fmt)
            return parsed.strftime("%H:%M:%S")
        except ValueError:
            continue
    
    return "00:00:00"


def determine_mime_type(file_path: str, fallback_mime: str) -> str:

    if fallback_mime and "image/" in fallback_mime and "octet-stream" not in fallback_mime:
        return fallback_mime
        
    path_lower = file_path.lower()
    if path_lower.endswith('.png'):
        return 'image/png'
    elif path_lower.endswith('.webp'):
        return 'image/webp'
    elif path_lower.endswith('.gif'):
        return 'image/gif'
    
    return 'image/jpeg'



def extract_navi_transaction(
    file_id: str,
    bot_token: str,
    gemini_api_key: str,
    model: str = "gemini-2.5-flash",
) -> Dict[str, Any]:

    try:
        client = genai.Client(api_key=gemini_api_key)
        
        url_get_file = f"https://api.telegram.org/bot{bot_token}/getFile"
        response = requests.get(url_get_file, params={"file_id": file_id}, timeout=10)
        response.raise_for_status()
        file_path = response.json()["result"]["file_path"]
        
        image_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        image_response = requests.get(image_url, timeout=10)
        image_response.raise_for_status()
        image_bytes = image_response.content
        
        mime_type = determine_mime_type(file_path, image_response.headers.get("Content-Type", ""))
        
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        
        prompt = (
            "Extract data from this NAVI UPI receipt. Follow these rules:\n"
            "1. Find the transaction status: 'Payment successful' = debit (I sent money), 'Payment received' = credit (I received money)\n"
            "2. Extract amount: The large prominent ₹ number\n"
            "3. Extract recipient/sender name: After 'to' (if debit) or 'from' (if credit)\n"
            "4. Extract UPI ID: The identifier like Q6430407228@ybl or karayushman736@okaxis\n"
            "5. Extract date: Format like '9 Apr 2026' or '14 Feb 2026'\n"
            "6. Extract time: Format like '5:32 PM' or '10:38 PM'\n"
            "7. Extract bank name: Look for 'from BANKNAME' or 'to BANKNAME' (e.g., 'INDIA POST PAYMENTS BANK - 1377')\n"
            "8. Extract transaction ID: 'UPI txn ID: XXXXXXXXX'\n"
            "9. Determine transaction_type: 'debit' if 'Payment successful' or 'Paid to', 'credit' if 'Payment received' or 'from'"
        )
        
        response = client.models.generate_content(
            model=model,
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "amount": {"type": "STRING", "description": "Amount like '₹10'"},
                        "date": {"type": "STRING", "description": "Date like '9 Apr 2026'"},
                        "time": {"type": "STRING", "description": "Time like '5:32 PM'"},
                        "transaction_type": {"type": "STRING", "enum": ["debit", "credit"]},
                        "bank_name": {"type": "STRING", "description": "Bank name"},
                        "recipient_name": {"type": "STRING", "description": "Recipient or Sender name"},
                        "upi_id": {"type": "STRING", "description": "UPI ID"},
                        "transaction_id": {"type": "STRING", "description": "UPI txn ID"},
                    },
                    "required": [
                        "amount", "date", "time", "transaction_type", 
                        "bank_name", "recipient_name", "upi_id", "transaction_id"
                    ],
                },
            ),
        )
        
        extracted = json.loads(response.text)
        extracted = _sanitize_navi_data(extracted)
        
        return {
            "success": True,
            "telegram_image_url": image_url,
            "data": extracted,
            "error": None,
        }
        
    except requests.RequestException as e:
        return {"success": False, "error": f"Network error: {str(e)}", "data": None}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON response: {str(e)}", "data": None}
    except Exception as e:
        return {"success": False, "error": f"Extraction failed: {str(e)}", "data": None}


def _sanitize_navi_data(data: Dict[str, Any]) -> Dict[str, Any]:
    data["amount_numeric"] = sanitize_amount(data.get("amount"))
    bank = data.get("bank_name", "")
    data["bank_name"] = normalize_bank_name(bank) if bank else "ippb"
    data["date"] = parse_date(data.get("date", ""))
    data["time"] = parse_time(data.get("time", ""))
    data["platform"] = "navi"
    return data



def extract_phonepe_transaction(
    file_id: str,
    bot_token: str,
    gemini_api_key: str,
    model: str = "gemini-2.5-flash",
) -> Dict[str, Any]:

    try:
        client = genai.Client(api_key=gemini_api_key)
        
        url_get_file = f"https://api.telegram.org/bot{bot_token}/getFile"
        response = requests.get(url_get_file, params={"file_id": file_id}, timeout=10)
        response.raise_for_status()
        file_path = response.json()["result"]["file_path"]
        
        image_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        image_response = requests.get(image_url, timeout=10)
        image_response.raise_for_status()
        image_bytes = image_response.content
        
        mime_type = determine_mime_type(file_path, image_response.headers.get("Content-Type", ""))
        
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        
        prompt = (
            "Extract data from this PhonePe UPI receipt. Follow these rules:\n"
            "1. Determine transaction type: 'Received from' = credit (I received money), 'Paid to' = debit (I sent money)\n"
            "2. Extract amount: The prominent ₹ number\n"
            "3. Extract sender/recipient name: The person's name after 'Received from' or 'Paid to'\n"
            "4. Extract UPI ID: The UPI identifier (looks like xxx@oksbi or xxx@ybl)\n"
            "5. Extract date: Like '05 Jul 2026'\n"
            "6. Extract time: Like '07:22 PM'\n"
            "7. Extract bank name: After 'Credited to' (for credit) or 'Debited from' (for debit)\n"
            "8. Extract PhonePe Transaction ID: Long ID starting with T\n"
            "9. Extract UTR: The 12-15 digit number"
        )
        
        response = client.models.generate_content(
            model=model,
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "amount": {"type": "STRING", "description": "Amount like '₹1'"},
                        "date": {"type": "STRING", "description": "Date like '05 Jul 2026'"},
                        "time": {"type": "STRING", "description": "Time like '07:22 PM'"},
                        "transaction_type": {"type": "STRING", "enum": ["debit", "credit"]},
                        "bank_name": {"type": "STRING", "description": "Bank name like 'IPPB' or 'SBI'"},
                        "sender_name": {"type": "STRING", "description": "Sender or Recipient name"},
                        "upi_id": {"type": "STRING", "description": "UPI ID"},
                        "transaction_id": {"type": "STRING", "description": "PhonePe Transaction ID"},
                        "utr": {"type": "STRING", "description": "UTR number"},
                    },
                    "required": [
                        "amount", "date", "time", "transaction_type", "bank_name", 
                        "sender_name", "upi_id", "transaction_id", "utr"
                    ],
                },
            ),
        )
        
        extracted = json.loads(response.text)
        extracted = _sanitize_phonepe_data(extracted)
        
        return {
            "success": True,
            "telegram_image_url": image_url,
            "data": extracted,
            "error": None,
        }
        
    except requests.RequestException as e:
        return {"success": False, "error": f"Network error: {str(e)}", "data": None}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON response: {str(e)}", "data": None}
    except Exception as e:
        return {"success": False, "error": f"Extraction failed: {str(e)}", "data": None}


def _sanitize_phonepe_data(data: Dict[str, Any]) -> Dict[str, Any]:
    data["amount_numeric"] = sanitize_amount(data.get("amount"))
    data["bank_name"] = normalize_bank_name(data.get("bank_name", ""))
    data["date"] = parse_date(data.get("date", ""))
    data["time"] = parse_time(data.get("time", ""))
    data["recipient_name"] = data.pop("sender_name", "")
    data["platform"] = "phonepe"
    return data


# ==================== GOOGLE PAY EXTRACTOR ====================

def extract_gpay_transaction(
    file_id: str,
    bot_token: str,
    gemini_api_key: str,
    model: str = "gemini-2.5-flash",
) -> Dict[str, Any]:
    """Extract transaction from Google Pay UPI receipt."""
    try:
        client = genai.Client(api_key=gemini_api_key)
        
        url_get_file = f"https://api.telegram.org/bot{bot_token}/getFile"
        response = requests.get(url_get_file, params={"file_id": file_id}, timeout=10)
        response.raise_for_status()
        file_path = response.json()["result"]["file_path"]
        
        image_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        image_response = requests.get(image_url, timeout=10)
        image_response.raise_for_status()
        image_bytes = image_response.content
        

        mime_type = determine_mime_type(file_path, image_response.headers.get("Content-Type", ""))
        
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        
        prompt = (
            "Extract data from this Google Pay UPI receipt. Follow these rules:\n"
            "1. Determine transaction type: 'From' = credit (I received), 'To' = debit (I sent)\n"
            "2. Extract amount: The prominent ₹ number\n"
            "3. Extract person name: After 'From' or 'To'\n"
            "4. Extract phone number: The +91 number shown\n"
            "5. Extract date: Like '5 Jan 2026' or '11 Dec 2025'\n"
            "6. Extract time: Like '2:30pm' or '11:03 pm'\n"
            "7. Extract bank name: Look for bank information (e.g., 'India Post Payment Bank 1377', 'SBI')\n"
            "8. Extract UPI Transaction ID: The numeric ID\n"
            "9. Extract Google Transaction ID: The code like 'CICAgJjww4GbZw'\n"
            "10. If 'Sent to: GPay' appears = debit, if 'Credited to:' appears = credit"
        )
        
        response = client.models.generate_content(
            model=model,
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "amount": {"type": "STRING", "description": "Amount like '₹300'"},
                        "date": {"type": "STRING", "description": "Date like '5 Jan 2026'"},
                        "time": {"type": "STRING", "description": "Time like '2:30pm'"},
                        "transaction_type": {"type": "STRING", "enum": ["debit", "credit"]},
                        "bank_name": {"type": "STRING", "description": "Bank name"},
                        "person_name": {"type": "STRING", "description": "Sender or Recipient name"},
                        "phone_number": {"type": "STRING", "description": "Phone number"},
                        "transaction_id": {"type": "STRING", "description": "UPI Transaction ID"},
                        "google_transaction_id": {"type": "STRING", "description": "Google Transaction ID"},
                    },
                    "required": [
                        "amount", "date", "time", "transaction_type", "bank_name"
                    ],
                },
            ),
        )
        
        extracted = json.loads(response.text)
        extracted = _sanitize_gpay_data(extracted)
        
        return {
            "success": True,
            "telegram_image_url": image_url,
            "data": extracted,
            "error": None,
        }
        
    except requests.RequestException as e:
        return {"success": False, "error": f"Network error: {str(e)}", "data": None}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON response: {str(e)}", "data": None}
    except Exception as e:
        return {"success": False, "error": f"Extraction failed: {str(e)}", "data": None}


def _sanitize_gpay_data(data: Dict[str, Any]) -> Dict[str, Any]:
    data["amount_numeric"] = sanitize_amount(data.get("amount"))
    data["bank_name"] = normalize_bank_name(data.get("bank_name", ""))
    data["date"] = parse_date(data.get("date", ""))
    data["time"] = parse_time(data.get("time", ""))
    data["recipient_name"] = data.pop("person_name", "")
    data["platform"] = "gpay"
    return data



def extract_transaction_from_telegram(
    file_id: str,
    bot_token: str,
    gemini_api_key: str,
    platform: str,
    model: str = "gemini-2.5-flash",
) -> Dict[str, Any]:
    """Universal transaction extractor wrapper."""
    platform = platform.lower().strip()
    
    if platform in ["navi"]:
        return extract_navi_transaction(file_id, bot_token, gemini_api_key, model)
    elif platform in ["phonepe", "phonpe", "phone_pe"]:
        return extract_phonepe_transaction(file_id, bot_token, gemini_api_key, model)
    elif platform in ["gpay", "google_pay", "google pay"]:
        return extract_gpay_transaction(file_id, bot_token, gemini_api_key, model)
    else:
        return {
            "success": False,
            "error": f"Unknown platform: {platform}. Use 'navi', 'phonepe', or 'gpay'",
            "data": None,
        }