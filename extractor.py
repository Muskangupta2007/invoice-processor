import os
import time
import requests
import re
from datetime import datetime

def extract_invoice_data(file_path, endpoint, api_key, doc_type="Invoice"):
    """
    Uploads invoice or delivery challan to Microsoft Azure Document Intelligence prebuilt-invoice API,
    polls for status, and parses the extracted fields according to the document type.
    """
    if not endpoint or not api_key:
        raise ValueError("Azure Document Intelligence endpoint and API key must be configured in settings.")
    
    # Standardize endpoint path
    endpoint = endpoint.strip().rstrip('/')
    url = f"{endpoint}/formrecognizer/documentModels/prebuilt-invoice:analyze?api-version=2023-07-31"
    
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type": "application/octet-stream"
    }
    
    # Read binary file data
    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
    except Exception as e:
        raise ValueError(f"Failed to read file: {e}")
        
    print(f"Sending request to Azure: {url}")
    
    try:
        response = requests.post(url, headers=headers, data=file_data, timeout=30)
    except Exception as e:
        raise RuntimeError(f"Connection to Azure failed: {e}")
        
    if response.status_code != 202:
        raise RuntimeError(f"Azure API error request trigger: {response.status_code} - {response.text}")
        
    operation_url = response.headers.get("Operation-Location")
    if not operation_url:
        raise RuntimeError("No Operation-Location header found in Azure response.")
        
    headers_poll = {
        "Ocp-Apim-Subscription-Key": api_key
    }
    
    print(f"Polling Azure Document Intelligence operation: {operation_url}")
    
    result = None
    max_polls = 40
    for i in range(max_polls):
        time.sleep(1)
        try:
            res_poll = requests.get(operation_url, headers=headers_poll, timeout=15)
        except Exception as e:
            print(f"Polling request failed: {e}")
            continue
            
        if res_poll.status_code != 200:
            raise RuntimeError(f"Azure API error polling: {res_poll.status_code} - {res_poll.text}")
            
        poll_data = res_poll.json()
        status = poll_data.get("status")
        
        if status == "succeeded":
            result = poll_data
            break
        elif status == "failed":
            error_details = poll_data.get("error", {})
            raise RuntimeError(f"Azure analysis failed: {error_details.get('message', 'Unknown error')}")
            
    if not result:
        raise RuntimeError("Azure Document Intelligence analysis operation timed out.")
        
    return parse_azure_invoice_result(result, doc_type)

def extract_eway_bill_number(result_json_or_content, raw_content=None):
    """
    Extracts 12-digit E-Way Bill Number from Azure Document Intelligence result JSON
    (Key-Value pairs & document fields) or raw OCR text content.
    """
    result_json = result_json_or_content if isinstance(result_json_or_content, dict) else {}
    content = raw_content if raw_content is not None else (result_json_or_content if isinstance(result_json_or_content, str) else "")

    # 1. Inspect Azure Document Intelligence Key-Value Pairs if present
    analyze_result = result_json.get("analyzeResult", {})
    kv_pairs = analyze_result.get("keyValuePairs", [])
    for kv in kv_pairs:
        key_text = str(kv.get("key", {}).get("content", "")).lower()
        val_text = str(kv.get("value", {}).get("content", ""))
        if "eway" in key_text or "e-way" in key_text or "ewb" in key_text:
            match = re.search(r'\b(\d{12}|\d{4}[ -]\d{4}[ -]\d{4})\b', val_text)
            if match:
                return re.sub(r'[- ]', '', match.group(1))

    # 2. Inspect Document Level Fields
    documents = analyze_result.get("documents", [])
    if documents:
        fields = documents[0].get("fields", {})
        for field_key in ["EwayBill", "EWayBill", "EwayBillNumber", "EWayBillNo", "EWBNumber", "EWBNo"]:
            if field_key in fields:
                f_val = str(fields[field_key].get("valueString") or fields[field_key].get("content") or "")
                match = re.search(r'\b(\d{12}|\d{4}[ -]\d{4}[ -]\d{4})\b', f_val)
                if match:
                    return re.sub(r'[- ]', '', match.group(1))

    if not content:
        return None
        
    normalized_content = " ".join(str(content).split())
    
    # 3. Regex matching 12-digit numbers near E-Way / EWB keywords in raw OCR content
    patterns = [
        r'(?i)(?:e[- ]?way|ewb)\s*(?:bill|no|number|num)?\s*(?:no|number|num)?\s*[\.:#-]*\s*(\b\d{12}\b|\b\d{4}[ -]\d{4}[ -]\d{4}\b)',
        r'(?i)(?:e[- ]?way|ewb)(?:[a-z0-9\s.,:-]{0,60})?(\b\d{12}\b|\b\d{4}[ -]\d{4}[ -]\d{4}\b)',
        r'(?i)(?:e[- ]?way|ewb)[^\d]{0,40}(\b\d{12}\b|\b\d{4}[ -]\d{4}[ -]\d{4}\b)'
    ]
    
    for pat in patterns:
        match = re.search(pat, normalized_content)
        if match:
            raw_val = match.group(1)
            clean_val = re.sub(r'[- ]', '', raw_val)
            if len(clean_val) == 12 and clean_val.isdigit():
                return clean_val
                
    return None

INVALID_CHALLAN_WORDS = {
    'MODE/TERMS', 'MODE', 'TERMS', 'PAYMENT', 'DELIVERY', 'REFERENCE', 'ORDER',
    'INVOICE', 'DATE', 'DATED', 'DISPATCH', 'DESTINATION', 'BUYER', 'SUPPLIER',
    'N/A', 'NONE', 'NULL', '-', 'BILL', 'DETAILS', 'TERMS OF DELIVERY',
    'OF', 'NO', 'NO.', 'NUMBER', 'NUM', 'REF', 'REF.', 'OTHER', 'MODES/TERMS'
}

PINCODE_PATTERN = re.compile(r'^\d{6}$')
PHONE_PATTERN = re.compile(r'\b\d{10}\b')
EWAY_PATTERN = re.compile(r'^\d{12}$')

ADDRESS_WORDS = {
    'VADODARA', 'BARODA', 'SURAT', 'AHMEDABAD', 'MUMBAI', 'PUNE', 'GUJARAT',
    'MAHARASHTRA', 'DELHI', 'DESTINATION', 'DISPATCH', 'ADDRESS', 'ROAD', 'DIST',
    'PINCODE', 'PIN', 'STATE', 'CITY', 'HAZIRA', 'INDIA', 'SURVEY', 'VILLA', 'THANE',
    'BHAYANDAR', 'COMPLEX', 'PLOT', 'BUILDING', 'FLOOR', 'LANE', 'STREET', 'PHASE',
    'LARSEN', 'TOUBRO', 'CAMP', 'OFFICE'
}

TAX_LABEL_WORDS = {
    'GSTIN', 'GST', 'UIN', 'PAN', 'CIN', 'TAX', 'REGISTRATION', 'STATE', 'CODE',
    'GSTIN/UIN', 'ARN', 'SAC', 'HSN', 'IRN', 'MOBILE', 'MOB', 'PHONE', 'TEL', 'CONTACT', 'EMAIL'
}

MONTH_WORDS = {
    'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC',
    'JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'JUNE', 'JULY', 'AUGUST', 'SEPTEMBER',
    'OCTOBER', 'NOVEMBER', 'DECEMBER', 'DATED', 'DATE'
}

PAYMENT_TERMS_WORDS = {
    'DAYS', 'DAY', 'NET', 'CREDIT', 'ADVANCE', 'IMMEDIATE', 'CASH', 'PDC', 'COD',
    'PAYMENT', 'TERMS', 'MODE', 'CHEQUE', 'ONLINE', 'NEFT', 'RTGS', 'UPI', 'AGAINST',
    'DAYS/PAYMENT', 'MODE/TERMS'
}

DATE_PATTERN = re.compile(
    r'\b(?:\d{1,2}[-/\.\s]+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|\d{1,2})[-/\.\s]+\d{2,4}|\d{4}[-/\.\s]+\d{1,2}[-/\.\s]+\d{1,2})\b',
    re.IGNORECASE
)

PAYMENT_PATTERN = re.compile(r'\b\d{1,3}\s*(?:DAYS?|DAY)\b', re.IGNORECASE)

GSTIN_PATTERN = re.compile(r'\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]{3}\b', re.IGNORECASE)

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')

def is_valid_challan_number(val):
    if not val:
        return False
    clean = re.sub(r'^[/:#-]+\s*', '', str(val)).strip().upper().rstrip('.,;:')
    if not clean or len(clean) < 2 or clean in INVALID_CHALLAN_WORDS:
        return False
    if any(clean.startswith(w) for w in ['MODE/', 'TERMS/', 'PAYMENT/', 'DATE/', 'BUYER/', 'SUPPLIER/', 'REF/', 'OTHER/', 'GSTIN/', 'GST/', 'UIN/', 'MOBILE/', 'MOB/', 'PHONE/', 'TEL/', '45 ', '30 ', '60 ']):
        return False
    if any(k in clean for k in ['MOBILE', 'MOB:', 'PHONE', 'TEL:', 'FAX:', 'CONTACT', 'PAN NUMBER', 'PAN NO', 'GSTIN', 'EMAIL']):
        return False
    # Reject email addresses and URLs
    if '@' in clean or EMAIL_PATTERN.search(clean) or 'HTTP' in clean or 'WWW' in clean:
        return False
    # Reject long addresses, company names, or text blocks with 2 or more spaces or length > 30
    if len(clean) > 30 or clean.count(' ') >= 2:
        return False
    # Reject standalone short pure numbers without slashes/letters (e.g. "45", "30", "60", "15")
    if clean.isdigit() and (len(clean) <= 3 or int(clean) <= 100):
        return False
    # Reject payment terms (e.g. 45 Days, 30 Days, Net 30, Cash)
    if PAYMENT_PATTERN.search(clean):
        return False
    # Reject date strings (e.g. 9-Jul-26, 14/07/2026, 09-07-2026)
    if parse_and_validate_date(clean):
        return False
    # Reject GSTIN / UIN / Tax registration numbers
    if 'GSTIN' in clean or 'GST' in clean or 'UIN' in clean or 'PAN' in clean or 'CIN' in clean:
        return False
    if GSTIN_PATTERN.search(clean):
        return False
    # MUST contain at least one digit (0-9) to be a valid document number
    if not re.search(r'\d', clean):
        return False
    # Reject strings containing 6-digit pincodes anywhere (e.g. VADODARA - 390021 or 390021)
    if re.search(r'\b\d{6}\b', clean):
        return False
    # Reject strings containing 10-digit phone numbers or 12-digit Eway bill numbers anywhere
    if PHONE_PATTERN.search(clean) or EWAY_PATTERN.search(clean):
        return False
    # Reject address/city/month/payment strings
    tokens = set(re.findall(r'[A-Z]+', clean))
    if tokens & ADDRESS_WORDS or tokens & TAX_LABEL_WORDS or tokens & MONTH_WORDS or tokens & PAYMENT_TERMS_WORDS:
        return False
    return True

def fix_truncated_challan_number(val_str, content):
    """
    Heals truncated Delivery Note / Delivery Challan numbers (e.g. '/26-27/116')
    by searching the raw OCR content for the full string with its prefix (e.g. 'SKH/DC/26-27/116').
    """
    if not val_str:
        return ""
        
    # Normalize unicode dashes (en-dash \u2013, em-dash \u2014, minus \u2212) to standard ASCII hyphen
    clean_val = str(val_str).replace('–', '-').replace('—', '-').replace('−', '-').strip()
    norm_content = str(content or "").replace('–', '-').replace('—', '-').replace('−', '-')
    
    # If the value starts with a slash or hyphen (e.g. "/26-27/116"), it's missing its prefix!
    if clean_val.startswith('/') or clean_val.startswith('-'):
        if norm_content:
            # Build flexible regex matching tail digits in norm_content (e.g. 26-27/116 -> SKH/DC/26-27/116)
            tail_digits = re.findall(r'[a-zA-Z0-9]+', clean_val)
            if tail_digits:
                flex_pattern = r'[\s/\-_]*' + r'[\s/\-_]*'.join(re.escape(d) for d in tail_digits)
                match = re.search(r'\b([a-zA-Z0-9]+[a-zA-Z0-9/\-_]*' + flex_pattern + r')', norm_content)
                if match:
                    found = match.group(1).strip()
                    if is_valid_challan_number(found):
                        return found
                        
        # Strip leading slash/hyphen if no prefix match found in content
        clean_val = re.sub(r'^[/:#-]+\s*', '', clean_val).strip()

    if is_valid_challan_number(clean_val):
        return clean_val
        
    return ""

def get_analyze_result(result_json):
    if not isinstance(result_json, dict):
        return {}
    if "analyzeResult" in result_json:
        return result_json["analyzeResult"]
    if "result" in result_json and isinstance(result_json["result"], dict):
        res = result_json["result"]
        if "analyzeResult" in res:
            return res["analyzeResult"]
        return res
    return {}

def extract_line_under_delivery_note(result_json_or_content, raw_content=None):
    """
    Directly extracts whatever line is written under 'Delivery Note' / 'Delivery Challan'
    in the invoice image/OCR text while strictly respecting column spatial alignment.
    Supports returning 'DIRECT INVOICE' if explicitly written under Delivery Note.
    """
    result_json = result_json_or_content if isinstance(result_json_or_content, dict) else {}
    content = raw_content if raw_content is not None else (result_json_or_content if isinstance(result_json_or_content, str) else "")
    analyze_result = get_analyze_result(result_json)
    
    # 1. Spatial bounding-box line inspection from pages[].lines if available
    pages = analyze_result.get("pages", [])
    for page in pages:
        lines = page.get("lines", [])
        for idx, line in enumerate(lines):
            line_text = str(line.get("content") or "").strip()
            line_lower = line_text.lower()

            # First check inline pattern matching (e.g. 'Challan No.: SADC/26-27/4')
            if any(k in line_lower for k in ["challan no", "challan number", "delivery challan no", "dc no", "delivery note"]):
                m = re.search(r'(?:challan\s*no|challan\s*number|dc\s*no|dc\s*number|delivery\s*challan\s*no|delivery\s*note)\s*[:.#-]*\s*([a-zA-Z0-9/\-_]{2,30})', line_text, re.IGNORECASE)
                if m:
                    cand = m.group(1).strip()
                    healed = fix_truncated_challan_number(cand, content)
                    if healed and is_valid_challan_number(healed):
                        return healed
                    if is_valid_challan_number(cand):
                        return cand

            # Do NOT match "Delivery Note Date" as a standalone Delivery Note header!
            if "date" in line_lower and not any(k in line_lower for k in ["challan no", "challan number", "delivery challan no"]):
                continue

            if any(k in line_lower for k in ["delivery note", "delivery challan", "challan no", "challan number"]):
                # Calculate bounding box X-range for the Delivery Note header
                poly = line.get("polygon") or line.get("boundingBox") or []
                hdr_x_min, hdr_x_max = None, None
                if poly and len(poly) >= 8:
                    xs = [poly[i] for i in range(0, 8, 2)]
                    hdr_x_min, hdr_x_max = min(xs), max(xs)
                elif poly and len(poly) == 4:
                    hdr_x_min, hdr_x_max = poly[0], poly[0] + poly[2]

                for next_line in lines[idx + 1: idx + 6]:
                    nxt_text = str(next_line.get("content") or "").strip()
                    if not nxt_text:
                        continue

                    # Spatial Column alignment check: ignore lines that belong to right adjacent column (e.g. Mode/Terms of Payment)
                    nxt_poly = next_line.get("polygon") or next_line.get("boundingBox") or []
                    if hdr_x_max is not None and nxt_poly:
                        if len(nxt_poly) >= 8:
                            nxt_xs = [nxt_poly[i] for i in range(0, 8, 2)]
                            nxt_x_center = (min(nxt_xs) + max(nxt_xs)) / 2.0
                        elif len(nxt_poly) == 4:
                            nxt_x_center = nxt_poly[0] + (nxt_poly[2] / 2.0)
                        else:
                            nxt_x_center = None

                        hdr_w = max(hdr_x_max - hdr_x_min, 0.5)
                        if nxt_x_center is not None and nxt_x_center > (hdr_x_max + 0.25 * hdr_w):
                            continue # Skip line belonging to right column (e.g. Mode/Terms of Payment)

                    clean_nxt = re.sub(r'^[.:#-]+\s*', '', nxt_text).strip()
                    if "DIRECT INVOICE" in clean_nxt.upper():
                        return "DIRECT INVOICE"
                    if any(clean_nxt.upper().startswith(w) for w in ['MODE/', 'TERMS/', 'PAYMENT/', 'REFERENCE', 'REF', 'ORDER', 'DATED', 'BUYER', 'SUPPLIER', 'OTHER', 'DISPATCH', 'DESTINATION']):
                        continue
                    if PINCODE_PATTERN.match(clean_nxt) or PHONE_PATTERN.search(clean_nxt):
                        continue
                    healed = fix_truncated_challan_number(clean_nxt, content)
                    if healed and is_valid_challan_number(healed):
                        return healed
                    if is_valid_challan_number(clean_nxt):
                        return clean_nxt

    # 2. Line-by-line OCR content scanning
    norm_content = str(content or "").replace('–', '-').replace('—', '-').replace('−', '-')
    ocr_lines = [l.strip() for l in norm_content.splitlines() if l.strip()]
    for idx, l_text in enumerate(ocr_lines):
        l_lower = l_text.lower()
        if any(k in l_lower for k in ["challan no", "challan number", "delivery challan no", "dc no", "delivery note"]):
            m = re.search(r'(?:challan\s*no|challan\s*number|dc\s*no|dc\s*number|delivery\s*challan\s*no|delivery\s*note)\s*[:.#-]*\s*([a-zA-Z0-9/\-_]{2,30})', l_text, re.IGNORECASE)
            if m:
                cand = m.group(1).strip()
                healed = fix_truncated_challan_number(cand, norm_content)
                if healed and is_valid_challan_number(healed):
                    return healed
                if is_valid_challan_number(cand):
                    return cand

        if "date" in l_lower and not any(k in l_lower for k in ["challan no", "challan number", "delivery challan no"]):
            continue
        if any(k in l_lower for k in ["delivery note", "delivery challan", "challan no", "challan number"]):
            for nxt_text in ocr_lines[idx + 1: idx + 6]:
                clean_nxt = re.sub(r'^[.:#-]+\s*', '', nxt_text).strip()
                if "DIRECT INVOICE" in clean_nxt.upper():
                    return "DIRECT INVOICE"
                if any(clean_nxt.upper().startswith(w) for w in ['MODE/', 'TERMS/', 'PAYMENT/', 'REFERENCE', 'REF', 'ORDER', 'DATED', 'BUYER', 'SUPPLIER', 'OTHER']):
                    continue
                if PINCODE_PATTERN.match(clean_nxt) or PHONE_PATTERN.search(clean_nxt):
                    continue
                healed = fix_truncated_challan_number(clean_nxt, norm_content)
                if healed and is_valid_challan_number(healed):
                    return healed
                if is_valid_challan_number(clean_nxt):
                    return clean_nxt
                    
    return None

def extract_challan_number(result_json_or_content, raw_content=None):
    """
    Extracts Delivery Challan / Delivery Note Number according to rules:
    - If Delivery Note contains 'DIRECT INVOICE', returns 'DIRECT INVOICE'.
    - If Delivery Note contains a valid challan number, returns that challan number.
    - If Delivery Note is blank, leaves it 100% BLANK ('').
    """
    result_json = result_json_or_content if isinstance(result_json_or_content, dict) else {}
    content = raw_content if raw_content is not None else (result_json_or_content if isinstance(result_json_or_content, str) else "")
    norm_content = str(content or "").replace('–', '-').replace('—', '-').replace('−', '-')

    # 1. DIRECTLY extract whatever is written under "Delivery Note" / "Delivery Challan"
    under_delivery_note = extract_line_under_delivery_note(result_json, norm_content)
    if under_delivery_note:
        if "DIRECT INVOICE" in under_delivery_note.upper():
            return "DIRECT INVOICE"
        if is_valid_challan_number(under_delivery_note):
            return under_delivery_note

    # 2. Strict Key-Value Pairs check if present for "delivery note" key
    analyze_result = get_analyze_result(result_json)
    kv_pairs = analyze_result.get("keyValuePairs", [])
    target_keys = ["delivery note", "delivery challan"]
    
    for kv in kv_pairs:
        key_text = str(kv.get("key", {}).get("content", "")).lower()
        val_text = str(kv.get("value", {}).get("content", "")).strip()
        if any(k in key_text for k in target_keys) and val_text:
            clean_val = re.sub(r'^[.:#-]+\s*', '', val_text).strip()
            if "DIRECT INVOICE" in clean_val.upper():
                return "DIRECT INVOICE"
            healed = fix_truncated_challan_number(clean_val, norm_content)
            if healed and is_valid_challan_number(healed):
                return healed
            if is_valid_challan_number(clean_val):
                return clean_val

    # IF NOTHING VALID WRITTEN UNDER DELIVERY NOTE, LEAVE BLANK ('')
    return None

INVALID_MODE_WORDS = {
    'DATE', 'DATED', 'DOC', 'NO', 'NUMBER', 'REF', 'DESTINATION', 'TERMS', 'DELIVERY',
    'BUYER', 'SUPPLIER', 'OTHER', 'REFERENCES', 'DETAILS', 'INVOICE', 'CHALLAN', 'ADDRESS'
}

TRANSPORT_KEYWORDS = {
    'VEHICLE', 'ROAD', 'BY ROAD', 'BY VEHICLE', 'AIR', 'BY AIR', 'SEA', 'BY SEA',
    'COURIER', 'TEMPO', 'TRUCK', 'TRAIN', 'RAIL', 'HAND DELIVERY', 'BY HAND',
    'EXPRESS', 'SURFACE', 'CARGO', 'LOGISTICS', 'PARCEL', 'SPEED POST', 'CONTAINER',
    'LORRY', 'FLIGHT', 'VESSEL', 'TRANSPORT'
}

def clean_mode_of_transport(val):
    if not val:
        return None
    clean = re.sub(r'^[.:#-]+\s*', '', str(val)).strip()
    clean = re.sub(r'^(?:dispatched\s*through|despatched\s*through|mode\s*of\s*transp(?:ort|ortation)?|transport\s*mode|transp\s*mode|transported\s*through|transported\s*by|carrier|transporter)\s*[:#-]*\s*', '', clean, flags=re.IGNORECASE).strip()
    clean_upper = clean.upper()

    if not clean or len(clean) < 2 or clean_upper in INVALID_MODE_WORDS:
        return None

    for kw in TRANSPORT_KEYWORDS:
        if kw in clean_upper:
            return clean_upper

    if clean_upper.startswith('BY ') or 'VEHICLE' in clean_upper or 'ROAD' in clean_upper:
        return clean_upper

    if len(clean) <= 25 and not re.search(r'\d', clean) and not any(w in clean_upper for w in INVALID_MODE_WORDS):
        return clean_upper

    return None

def extract_mode_of_transport(result_json_or_content, raw_content=None, default_val=None):
    """
    Extracts Mode of Transport (e.g. 'VEHICLE', 'BY ROAD', 'ROAD', 'COURIER', 'TEMPO', 'TRUCK', etc.)
    from Azure fields, Key-Value pairs, Azure tables, spatial OCR lines, and raw text content.
    """
    if default_val:
        cleaned = clean_mode_of_transport(default_val)
        if cleaned:
            return cleaned

    result_json = result_json_or_content if isinstance(result_json_or_content, dict) else {}
    content = raw_content if raw_content is not None else (result_json_or_content if isinstance(result_json_or_content, str) else "")
    analyze_result = get_analyze_result(result_json)

    # 1. Key-Value pairs inspection
    kv_pairs = analyze_result.get("keyValuePairs", [])
    for kv in kv_pairs:
        key_text = str(kv.get("key", {}).get("content", "")).lower()
        val_text = str(kv.get("value", {}).get("content", "")).strip()
        if any(k in key_text for k in ["dispatched through", "despatched through", "mode of transport", "transport mode", "transp mode", "means of transport", "transported through"]):
            cleaned = clean_mode_of_transport(val_text)
            if cleaned:
                return cleaned

    # 2. Azure Tables inspection
    tables = analyze_result.get("tables", [])
    for tbl in tables:
        cells = tbl.get("cells", [])
        for c in cells:
            cell_text = str(c.get("content") or "").strip().lower()
            if any(k in cell_text for k in ["dispatched through", "despatched through", "mode of transport", "transport mode", "transp mode", "means of transport"]):
                r_idx = c.get("rowIndex")
                c_idx = c.get("columnIndex")
                for target in cells:
                    if target.get("columnIndex") == c_idx and target.get("rowIndex") == r_idx + 1:
                        cleaned = clean_mode_of_transport(target.get("content"))
                        if cleaned:
                            return cleaned
                    if target.get("rowIndex") == r_idx and target.get("columnIndex") == c_idx + 1:
                        cleaned = clean_mode_of_transport(target.get("content"))
                        if cleaned:
                            return cleaned

    # 3. Spatial Layout Line Inspection
    pages = analyze_result.get("pages", [])
    for page in pages:
        lines = page.get("lines", [])
        for idx, line in enumerate(lines):
            line_text = str(line.get("content") or "").strip()
            line_lower = line_text.lower()
            if any(k in line_lower for k in ["dispatched through", "despatched through", "mode of transport", "transport mode", "transp mode", "means of transport", "transported through"]):
                m = re.search(r'(?:dispatched through|despatched through|mode of transport|transport mode|transp mode|transported through)\s*[:#-]*\s*(.+)', line_text, re.IGNORECASE)
                if m and m.group(1).strip():
                    cleaned = clean_mode_of_transport(m.group(1).strip())
                    if cleaned:
                        return cleaned
                for nxt_line in lines[idx + 1: idx + 4]:
                    nxt_text = str(nxt_line.get("content") or "").strip()
                    cleaned = clean_mode_of_transport(nxt_text)
                    if cleaned:
                        return cleaned

    # 4. Raw OCR Content Scanning
    norm_content = str(content or "").replace('–', '-').replace('—', '-').replace('−', '-')
    ocr_lines = [l.strip() for l in norm_content.splitlines() if l.strip()]
    for idx, l_text in enumerate(ocr_lines):
        l_lower = l_text.lower()
        if any(k in l_lower for k in ["dispatched through", "despatched through", "mode of transport", "transport mode", "transp mode", "means of transport", "transported through"]):
            m = re.search(r'(?:dispatched through|despatched through|mode of transport|transport mode|transp mode|transported through)\s*[:#-]*\s*(.+)', l_text, re.IGNORECASE)
            if m and m.group(1).strip():
                cleaned = clean_mode_of_transport(m.group(1).strip())
                if cleaned:
                    return cleaned
            for nxt_text in ocr_lines[idx + 1: idx + 4]:
                cleaned = clean_mode_of_transport(nxt_text)
                if cleaned:
                    return cleaned

    return ""

MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12,
    'JANUARY': 1, 'FEBRUARY': 2, 'MARCH': 3, 'APRIL': 4, 'JUNE': 6,
    'JULY': 7, 'AUGUST': 8, 'SEPTEMBER': 9, 'OCTOBER': 10, 'NOVEMBER': 11, 'DECEMBER': 12
}

def parse_and_validate_date(text):
    """
    Strictly parses and validates whether a text string contains a valid calendar date.
    Rejects invalid months (e.g. >12), invalid days, 3-digit years (e.g. '279'),
    or dates embedded in invoice numbers like 'SKH/26-27/279'.
    Returns 'YYYY-MM-DD' if valid, else None.
    """
    if not text:
        return None
    text_str = str(text).strip()

    # 1. ISO format: YYYY-MM-DD
    iso_match = re.search(r'\b(19\d\d|20\d\d)[-/\.](0?[1-9]|1[0-2])[-/\.](0?[1-9]|[12]\d|3[01])\b', text_str)
    if iso_match:
        y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        try:
            return datetime(y, m, d).strftime('%Y-%m-%d')
        except ValueError:
            pass

    # 2. Text month format: DD-MMM-YY / DD MMM YYYY / DD-MMM-YYYY (e.g. 23-Jul-26, 23 July 2026)
    text_month_pat = re.compile(
        r'\b(0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?[-/\.\s]+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)[-/\.\s]+(\d{2}|\d{4})\b',
        re.IGNORECASE
    )
    m = text_month_pat.search(text_str)
    if m:
        day_str, month_str, year_str = m.groups()
        day = int(day_str)
        month = MONTH_MAP[month_str.upper()]
        year = int(year_str)
        if len(year_str) == 2:
            year = 2000 + year
        try:
            return datetime(year, month, day).strftime('%Y-%m-%d')
        except ValueError:
            pass

    # 3. Numeric format: DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY or DD/MM/YY
    numeric_pat = re.compile(
        r'\b(0?[1-9]|[12]\d|3[01])[-/\.](0?[1-9]|1[0-2])[-/\.](\d{2}|\d{4})\b'
    )
    for m in numeric_pat.finditer(text_str):
        d_str, m_str, y_str = m.groups()
        start, end = m.span()
        # Reject if preceded or followed by slash/dash as part of an invoice sequence (e.g. /26-27/279 or POD/26/000956)
        if start > 0 and text_str[start - 1] in '/-':
            continue
        if end < len(text_str) and text_str[end] in '/-':
            continue

        day = int(d_str)
        month = int(m_str)
        year = int(y_str)
        if len(y_str) == 2:
            year = 2000 + year
        try:
            return datetime(year, month, day).strftime('%Y-%m-%d')
        except ValueError:
            pass

    return None

def format_date_str(date_str):
    if not date_str:
        return None
    return parse_and_validate_date(date_str) or str(date_str).strip()

def extract_true_invoice_date(result_json, content, default_date=None):
    """
    Directly extracts the true Invoice Date from:
    0. Azure InvoiceDate field raw OCR text content (rejecting Azure's faulty normalized valueDate if misread).
    1. Azure table cells (extracting from the exact 'Dated' box attached on the side of 'Invoice No.').
    2. Key-value pairs.
    3. Spatial side-by-side line layout bounding boxes.
    4. Top OCR text content lines.
    Avoids picking lower Buyer Order dates (e.g. 21-Jul-26) or misreading invoice numbers (e.g. SKH/26-27/279).
    """
    result_json = result_json if isinstance(result_json, dict) else {}
    analyze_result = get_analyze_result(result_json)

    # 0. Check Azure Document Level 'InvoiceDate' field raw OCR text content first
    documents = analyze_result.get("documents", [])
    if documents:
        fields = documents[0].get("fields", {})
        inv_date_field = fields.get("InvoiceDate", {})
        raw_inv_date_text = inv_date_field.get("content") or inv_date_field.get("valueString")
        if raw_inv_date_text:
            valid = parse_and_validate_date(raw_inv_date_text)
            if valid:
                return valid

    # 1. Table Spatial Box Inspection (Highest Priority: exact 'Dated' box on the side of 'Invoice No.')
    tables = analyze_result.get("tables", [])
    for tbl in tables:
        cells = tbl.get("cells", [])
        inv_no_row = None
        dated_col_idx = None

        # Pass A: Look for header row with 'Invoice No.' and 'Dated'
        for c in cells:
            cell_text = str(c.get("content") or "").strip().lower()
            row_idx = c.get("rowIndex")
            col_idx = c.get("columnIndex")
            if "invoice no" in cell_text or "invoice id" in cell_text or "invoice number" in cell_text:
                inv_no_row = row_idx
            if ("dated" in cell_text or "invoice date" in cell_text) and not any(bad in cell_text for bad in ["buyer", "order", "po", "lr", "challan"]):
                if inv_no_row is not None and row_idx == inv_no_row:
                    dated_col_idx = col_idx

        if inv_no_row is not None and dated_col_idx is not None:
            # Check cells in the dated column at inv_no_row and inv_no_row + 1 (the data row directly under 'Dated')
            for c in cells:
                if c.get("columnIndex") == dated_col_idx and c.get("rowIndex") in [inv_no_row, inv_no_row + 1]:
                    valid = parse_and_validate_date(c.get("content"))
                    if valid:
                        return valid

        # Pass B: Look for cell containing both 'Invoice No.' and 'Dated' or date in same row
        for c in cells:
            cell_text = str(c.get("content") or "").strip()
            if "invoice no" in cell_text.lower() or "dated" in cell_text.lower():
                valid = parse_and_validate_date(cell_text)
                if valid:
                    return valid

    # 2. Key-Value Pairs inspection
    kv_pairs = analyze_result.get("keyValuePairs", [])
    for kv in kv_pairs:
        key_text = str(kv.get("key", {}).get("content", "")).lower()
        val_text = str(kv.get("value", {}).get("content", "")).strip()
        if any(k in key_text for k in ["invoice date", "date of invoice", "dated", "inv date"]):
            if not any(bad in key_text for bad in ["buyer", "order", "po", "lr", "challan", "delivery", "dispatch", "transport"]):
                valid = parse_and_validate_date(val_text)
                if valid:
                    return valid

    # 3. Spatial Side-by-Side Layout Line Inspection (top 45% of page)
    pages = analyze_result.get("pages", [])
    for page in pages:
        lines = page.get("lines", [])
        page_h = float(page.get("height") or 1.0)

        for idx, line in enumerate(lines):
            line_text = str(line.get("content") or "").strip()
            line_lower = line_text.lower()

            poly = line.get("polygon") or line.get("boundingBox") or []
            if poly and len(poly) >= 8:
                y_center = sum([poly[i] for i in range(1, 8, 2)]) / 4.0
            elif poly and len(poly) == 4:
                y_center = poly[1] + poly[3] / 2.0
            else:
                y_center = 0.0

            if y_center <= page_h * 0.45:
                # Check lines containing 'dated' or 'invoice date'
                if any(k in line_lower for k in ["dated", "invoice date", "date of invoice", "inv date"]):
                    if not any(bad in line_lower for bad in ["buyer", "order", "po", "lr", "challan", "delivery note", "dispatch"]):
                        for nxt_line in lines[idx: idx + 5]:
                            nxt_text = str(nxt_line.get("content") or "").strip()
                            valid = parse_and_validate_date(nxt_text)
                            if valid:
                                return valid

                # Check lines near Invoice No
                if "invoice no" in line_lower or "invoice id" in line_lower:
                    for nxt_line in lines[idx: idx + 5]:
                        nxt_text = str(nxt_line.get("content") or "").strip()
                        valid = parse_and_validate_date(nxt_text)
                        if valid:
                            return valid

    # 4. Line-by-line OCR content scanning (top 20 lines)
    norm_content = str(content or "").replace('–', '-').replace('—', '-').replace('−', '-')
    ocr_lines = [l.strip() for l in norm_content.splitlines() if l.strip()]
    for idx, l_text in enumerate(ocr_lines[:20]):
        l_lower = l_text.lower()
        if any(k in l_lower for k in ["dated", "invoice date", "date of invoice", "inv date"]):
            if not any(bad in l_lower for bad in ["buyer", "order", "po", "lr", "challan", "delivery note", "dispatch"]):
                for nxt_text in ocr_lines[idx: idx + 5]:
                    valid = parse_and_validate_date(nxt_text)
                    if valid:
                        return valid

    # 5. Fallback to default_date if valid
    if default_date:
        valid = parse_and_validate_date(default_date)
        if valid:
            return valid

    return default_date

def parse_azure_invoice_result(result, doc_type="Invoice"):
    """
    Helper function to parse Azure Analyze Result JSON and map it to our target schema.
    Supports joining item descriptions, quantities, units, and unit prices with newlines.
    """
    analyze_result = get_analyze_result(result)
    content = analyze_result.get("content", "")
    documents = analyze_result.get("documents", [])
    
    doc = documents[0] if documents else {}
    fields = doc.get("fields", {})
    
    def get_field_val(name, val_type="valueString"):
        if not fields:
            return None
        f = fields.get(name, {})
        if not f:
            return None
        if val_type in f:
            return f[val_type]
        for key in ["valueString", "valueDate", "valueNumber", "valueInteger", "content"]:
            if key in f:
                return f[key]
        return None

    # Get Customer name or Customer Address as Bill To
    bill_to = get_field_val("CustomerName") or get_field_val("CustomerAddress") or get_field_val("VendorName")
    if not bill_to and content:
        for line in str(content).splitlines():
            line_str = line.strip()
            if any(k in line_str.lower() for k in ["consignee", "bill to", "delivered to", "buyer"]):
                clean_name = re.sub(r'(?i)^(?:consignee|bill to|delivered to|buyer)\s*[:#-]*\s*', '', line_str).strip()
                if clean_name and len(clean_name) > 3:
                    bill_to = clean_name.upper()
                    break
        
    # Extract line items
    items = fields.get("Items", {}).get("valueArray", [])
    raw_items = []
    
    for item in items:
        item_fields = item.get("valueObject", {})
        
        # Description
        desc_field = item_fields.get("Description", {})
        desc = desc_field.get("valueString") or desc_field.get("content") or ""
        
        # Quantity
        qty_field = item_fields.get("Quantity", {})
        qty_val = qty_field.get("valueNumber") or qty_field.get("valueInteger") or qty_field.get("content") or ""
        
        # Unit (UOM)
        unit_field = item_fields.get("Unit", {})
        unit_val = unit_field.get("valueString") or unit_field.get("content") or ""
        
        # Check raw quantity text content for UOM (e.g., "30 nos")
        qty_content = str(qty_field.get("content") or "").strip()
        if qty_content and not unit_val:
            match = re.match(r'^([\d\.,\s]+)\s*([a-zA-Z]+[a-zA-Z\s\./]*)$', qty_content)
            if match:
                unit_val = match.group(2).strip()
        
        # Unit Price
        price_field = item_fields.get("UnitPrice", {})
        price_val = price_field.get("valueNumber") or price_field.get("valueInteger") or price_field.get("content") or ""
        
        # Total Amount
        amount_field = item_fields.get("Amount", {})
        amount_val = amount_field.get("valueNumber") or amount_field.get("valueInteger") or amount_field.get("content") or ""
        
        raw_items.append({
            "desc": str(desc).strip() if desc else "",
            "qty": str(qty_val).strip() if qty_val else "",
            "unit": str(unit_val).strip() if unit_val else "",
            "price": str(price_val).strip() if price_val else "",
            "amount": str(amount_val).strip() if amount_val else ""
        })
        
    # Merge item descriptions that are split across multiple lines
    merged_items = []
    for item in raw_items:
        # A continuation has a description but lacks quantity, price, and amount
        is_continuation = item["desc"] and not item["qty"] and not item["price"] and not item["amount"]
        
        if is_continuation and merged_items:
            # Append this text block to the previous item's description
            merged_items[-1]["desc"] += " " + item["desc"]
        else:
            merged_items.append(item)
            
    # Format and populate lists
    item_descriptions = []
    deliver_qty_list = []
    uom_list = []
    unit_price_list = []
    
    for item in merged_items:
        desc = item["desc"]
        qty_val = item["qty"]
        unit_val = item["unit"]
        price_val = item["price"]
        
        # Parse quantity and unit if they appear together in the quantity field (e.g. "30 nos")
        if qty_val:
            match = re.match(r'^([\d\.,\s]+)\s*([a-zA-Z]+[a-zA-Z\s\./]*)$', qty_val)
            if match:
                qty_val = match.group(1).strip()
                extracted_unit = match.group(2).strip()
                if not unit_val:
                    unit_val = extracted_unit
                    
        if desc or qty_val or unit_val or price_val:
            # Replace internal newlines inside item descriptions with ' - '
            # to prevent alignment offsets when joined with '\n'
            clean_desc = str(desc).replace('\n', ' - ').strip()
            item_descriptions.append(clean_desc)
            deliver_qty_list.append(qty_val)
            uom_list.append(unit_val)
            unit_price_list.append(price_val)

    # Format fields depending on doc_type
    if doc_type == "Challan":
        item_description = "\n".join(item_descriptions) if item_descriptions else "Materials"
        deliver_qty = "\n".join(deliver_qty_list) if deliver_qty_list else "1"
        uom = "\n".join(uom_list) if uom_list else "Pcs"
        unit_price = "\n".join(unit_price_list) if unit_price_list else "0.0"
        po_qty = "\n".join(["0" for _ in item_descriptions]) if item_descriptions else "0"
        po_status = "OPEN"
    else:
        item_description = ", ".join(item_descriptions) if item_descriptions else "Materials"
        deliver_qty = ""
        uom = ""
        unit_price = ""
        po_qty = ""
        po_status = ""
    
    # Get total amount
    amount = None
    invoice_total_field = fields.get("InvoiceTotal", {})
    if invoice_total_field:
        currency_val = invoice_total_field.get("valueCurrency")
        if currency_val and isinstance(currency_val, dict):
            amount = currency_val.get("amount")
        if amount is None:
            amount = invoice_total_field.get("valueNumber") or invoice_total_field.get("valueInteger")
            
    if amount is not None:
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            amount = 0.0
    else:
        amount = 0.0

    inv_date_field = fields.get("InvoiceDate", {}) if fields else {}
    raw_azure_date = inv_date_field.get("content") or inv_date_field.get("valueString")
    azure_date = parse_and_validate_date(raw_azure_date) or get_field_val("InvoiceDate", "valueDate")
    doc_date = extract_true_invoice_date(result, content, default_date=azure_date)
    
    if doc_type == "Challan":
        doc_no = extract_challan_number(result, content) or get_field_val("InvoiceId") or extract_line_under_delivery_note(result, content)
        if not doc_no and content:
            dc_match = re.search(r'(?i)(?:challan\s*no|challan\s*number|dc\s*no|dc\s*number|delivery\s*challan\s*no)\s*[:#-]*\s*([a-zA-Z0-9/\-_]{3,30})', str(content))
            if dc_match:
                cand = dc_match.group(1).strip()
                if is_valid_challan_number(cand):
                    doc_no = cand
        invoice_no = ""
        challan_no = doc_no or ""
    else:
        doc_no = get_field_val("InvoiceId")
        invoice_no = doc_no or ""
        extracted_challan = extract_challan_number(result, content)
        challan_no = extracted_challan if extracted_challan else ""

    # Compute E-way Bill based on amount and scanned content
    eway_bill_val = "PENDING"
    eway_bill_no_val = ""
    if doc_type == "Invoice":
        extracted_no = extract_eway_bill_number(result, content)
        if extracted_no:
            eway_bill_no_val = extracted_no
            eway_bill_val = "DONE"
        else:
            if amount < 50000:
                eway_bill_val = "N/A"
            else:
                eway_bill_val = "PENDING"

    # Map directly to our spreadsheet database format
    data = {
        "doc_no": doc_no,
        "doc_date": doc_date,
        "invoice_no": invoice_no,
        "challan_no": challan_no,
        "bill_to": bill_to or "LARSEN & TOUBRO",
        "po_wo_no": get_field_val("PurchaseOrder"),
        "item_description": item_description,
        "amount": amount,
        "eway_bill": eway_bill_val,
        "eway_bill_no": eway_bill_no_val,
        "asn_no": get_field_val("ASNNo") or get_field_val("ASNNumber") or "",
        "mode_of_transp": extract_mode_of_transport(result, content, default_val=get_field_val("ModeOfTransport")),
        "dock_code": "",
        "delivery_date": doc_date if doc_type == "Invoice" else (get_field_val("InvoiceDate", "valueDate") or doc_date),
        "delivery_site": get_field_val("ShippingAddress") or get_field_val("ShippingAddressRecipient") or "",
        
        # Challan fields
        "deliver_qty": deliver_qty,
        "uom": uom,
        "unit_price": unit_price,
        "po_status": po_status,
        "po_qty": po_qty,
        
        # Post-processing workflow defaults
        "mrn_status": "PENDING",
        "mrn_date": "",
        "mrn_no": "",
        "remarks": ""
    }
    
    def clean_date(date_str):
        if not date_str:
            return ""
        date_str_clean = str(date_str).split("T")[0].strip()
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]:
            try:
                dt = datetime.strptime(date_str_clean, fmt)
                return dt.strftime("%d %B %Y")
            except ValueError:
                continue
        return date_str_clean

    data["doc_date"] = clean_date(data["doc_date"])
    data["delivery_date"] = clean_date(data["delivery_date"])
    
    if not data["doc_no"]:
        prefix = "INV" if doc_type == "Invoice" else "DC"
        data["doc_no"] = f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        if doc_type == "Challan":
            data["challan_no"] = data["doc_no"]
        else:
            data["invoice_no"] = data["doc_no"]

    return data
