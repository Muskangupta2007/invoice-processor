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
    'DIRECT INVOICE', 'N/A', 'NONE', 'NULL', '-', 'BILL', 'DETAILS', 'TERMS OF DELIVERY',
    'OF', 'NO', 'NO.', 'NUMBER', 'NUM', 'REF', 'REF.', 'OTHER', 'MODES/TERMS'
}

PINCODE_PATTERN = re.compile(r'^\d{6}$')
PHONE_PATTERN = re.compile(r'^\d{10}$')
EWAY_PATTERN = re.compile(r'^\d{12}$')

ADDRESS_WORDS = {
    'VADODARA', 'BARODA', 'SURAT', 'AHMEDABAD', 'MUMBAI', 'PUNE', 'GUJARAT',
    'MAHARASHTRA', 'DELHI', 'DESTINATION', 'DISPATCH', 'ADDRESS', 'ROAD', 'DIST',
    'PINCODE', 'PIN', 'STATE', 'CITY', 'HAZIRA', 'INDIA'
}

TAX_LABEL_WORDS = {
    'GSTIN', 'GST', 'UIN', 'PAN', 'CIN', 'TAX', 'REGISTRATION', 'STATE', 'CODE',
    'GSTIN/UIN', 'ARN', 'SAC', 'HSN', 'IRN'
}

GSTIN_PATTERN = re.compile(r'\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]{3}\b', re.IGNORECASE)

def is_valid_challan_number(val):
    if not val:
        return False
    clean = re.sub(r'^[/:#-]+\s*', '', str(val)).strip().upper().rstrip('.,;:')
    if not clean or len(clean) < 2 or clean in INVALID_CHALLAN_WORDS:
        return False
    if any(clean.startswith(w) for w in ['MODE/', 'TERMS/', 'PAYMENT/', 'DATE/', 'BUYER/', 'SUPPLIER/', 'REF/', 'OTHER/', 'GSTIN/', 'GST/', 'UIN/']):
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
    # Reject strings containing 10-digit phone numbers or 12-digit Eway bill numbers
    if PHONE_PATTERN.search(clean) or EWAY_PATTERN.search(clean):
        return False
    # Reject address/city strings
    tokens = set(re.findall(r'[A-Z]+', clean))
    if tokens & ADDRESS_WORDS or tokens & TAX_LABEL_WORDS:
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
    in the invoice image/OCR text.
    """
    result_json = result_json_or_content if isinstance(result_json_or_content, dict) else {}
    content = raw_content if raw_content is not None else (result_json_or_content if isinstance(result_json_or_content, str) else "")
    analyze_result = get_analyze_result(result_json)
    
    # 1. Spatial bounding-box line inspection from pages[].lines if available
    pages = analyze_result.get("pages", [])
    for page in pages:
        lines = page.get("lines", [])
        for idx, line in enumerate(lines):
            line_text = str(line.get("content") or "").strip().lower()
            if any(k in line_text for k in ["delivery note", "delivery challan", "challan no", "challan number"]):
                for next_line in lines[idx + 1: idx + 6]:
                    nxt_text = str(next_line.get("content") or "").strip()
                    if not nxt_text:
                        continue
                    clean_nxt = re.sub(r'^[.:#-]+\s*', '', nxt_text).strip()
                    if any(clean_nxt.upper().startswith(w) for w in ['MODE/', 'TERMS/', 'PAYMENT/', 'REFERENCE', 'REF', 'ORDER', 'DATED', 'BUYER', 'SUPPLIER', 'OTHER']):
                        continue
                    if PINCODE_PATTERN.match(clean_nxt) or PHONE_PATTERN.match(clean_nxt):
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
        if any(k in l_lower for k in ["delivery note", "delivery challan", "challan no", "challan number"]):
            for nxt_text in ocr_lines[idx + 1: idx + 6]:
                clean_nxt = re.sub(r'^[.:#-]+\s*', '', nxt_text).strip()
                if any(clean_nxt.upper().startswith(w) for w in ['MODE/', 'TERMS/', 'PAYMENT/', 'REFERENCE', 'REF', 'ORDER', 'DATED', 'BUYER', 'SUPPLIER', 'OTHER']):
                    continue
                if PINCODE_PATTERN.match(clean_nxt) or PHONE_PATTERN.match(clean_nxt):
                    continue
                healed = fix_truncated_challan_number(clean_nxt, norm_content)
                if healed and is_valid_challan_number(healed):
                    return healed
                if is_valid_challan_number(clean_nxt):
                    return clean_nxt
                    
    return None

def extract_challan_number(result_json_or_content, raw_content=None):
    """
    Extracts Delivery Challan / Delivery Note Number from Azure Document Intelligence result JSON
    (Key-Value pairs & document fields) or raw OCR text content.
    """
    result_json = result_json_or_content if isinstance(result_json_or_content, dict) else {}
    content = raw_content if raw_content is not None else (result_json_or_content if isinstance(result_json_or_content, str) else "")

    norm_content = str(content or "").replace('–', '-').replace('—', '-').replace('−', '-')
    
    # 0. DIRECTLY extract whatever is written under "Delivery Note" / "Delivery Challan"
    under_delivery_note = extract_line_under_delivery_note(result_json, norm_content)
    if under_delivery_note:
        return under_delivery_note

    extracted_cand = None

    # 1. Inspect Azure Document Intelligence Key-Value Pairs if present
    analyze_result = get_analyze_result(result_json)
    kv_pairs = analyze_result.get("keyValuePairs", [])
    target_keys = ["delivery note", "challan", "dc no", "dc number", "delivery challan", "dc #", "challan #"]
    
    for kv in kv_pairs:
        key_text = str(kv.get("key", {}).get("content", "")).lower()
        val_text = str(kv.get("value", {}).get("content", "")).strip()
        if any(k in key_text for k in target_keys) and val_text:
            clean_val = re.sub(r'^[.:#-]+\s*', '', val_text).strip()
            if is_valid_challan_number(clean_val) or clean_val.startswith('/') or clean_val.startswith('-'):
                extracted_cand = clean_val
                break

    # 2. Inspect Document Level Fields if no KV candidate
    if not extracted_cand:
        documents = analyze_result.get("documents", [])
        if documents:
            fields = documents[0].get("fields", {})
            target_fields = ["DeliveryNote", "DeliveryNoteNo", "DeliveryNoteNumber", "ChallanNumber", "ChallanNo", "DeliveryChallanNumber", "DeliveryChallanNo", "DCNo", "DCNumber"]
            for field_key in target_fields:
                if field_key in fields:
                    f_val = str(fields[field_key].get("valueString") or fields[field_key].get("content") or "").strip()
                    clean_val = re.sub(r'^[.:#-]+\s*', '', f_val).strip()
                    if is_valid_challan_number(clean_val) or clean_val.startswith('/') or clean_val.startswith('-'):
                        extracted_cand = clean_val
                        break

    # If candidate found (e.g. '/26-27/116' or 'SKH/DC/26-27/116'), heal truncation using norm_content
    if extracted_cand:
        healed = fix_truncated_challan_number(extracted_cand, norm_content)
        if healed and is_valid_challan_number(healed):
            return healed

    if not norm_content:
        return None

    # 3. Token-scanning around "Delivery Note" / "Delivery Challan" / "Challan" keywords in OCR content
    # Pass 1: Prioritize candidates containing slashes '/' or hyphens '-' with letters & digits (e.g. SKH/DC/26-27/116)
    for kw in ["delivery note", "delivery challan", "challan no", "challan number", "dc no", "dc number", "challan"]:
        kw_idx = norm_content.lower().find(kw)
        if kw_idx != -1:
            sub_text = norm_content[kw_idx + len(kw): kw_idx + len(kw) + 300]
            tokens = re.split(r'[\s,\t\n\r]+', sub_text)
            for tok in tokens:
                clean_tok = tok.strip().rstrip('.,;:')
                healed_tok = fix_truncated_challan_number(clean_tok, norm_content)
                if healed_tok and ('/' in healed_tok or '-' in healed_tok) and is_valid_challan_number(healed_tok):
                    return healed_tok
                if ('/' in clean_tok or '-' in clean_tok) and is_valid_challan_number(clean_tok):
                    return clean_tok

    # Pass 2: Fallback to any valid candidate in window
    for kw in ["delivery note", "delivery challan", "challan no", "challan number", "dc no", "dc number", "challan"]:
        kw_idx = norm_content.lower().find(kw)
        if kw_idx != -1:
            sub_text = norm_content[kw_idx + len(kw): kw_idx + len(kw) + 300]
            tokens = re.split(r'[\s,\t\n\r]+', sub_text)
            for tok in tokens:
                clean_tok = tok.strip().rstrip('.,;:')
                healed_tok = fix_truncated_challan_number(clean_tok, norm_content)
                if healed_tok and is_valid_challan_number(healed_tok):
                    return healed_tok
                if is_valid_challan_number(clean_tok):
                    return clean_tok

    return None

def parse_azure_invoice_result(result, doc_type="Invoice"):
    """
    Helper function to parse Azure Analyze Result JSON and map it to our target schema.
    Supports joining item descriptions, quantities, units, and unit prices with newlines.
    """
    analyze_result = get_analyze_result(result)
    content = analyze_result.get("content", "")
    documents = analyze_result.get("documents", [])
    
    if not documents:
        raise ValueError("Azure completed successfully, but could not identify a valid document structure.")
        
    doc = documents[0]
    fields = doc.get("fields", {})
    
    def get_field_val(name, val_type="valueString"):
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
    bill_to = get_field_val("CustomerName")
    if not bill_to:
        bill_to = get_field_val("CustomerAddress")
    if not bill_to:
        bill_to = get_field_val("VendorName")
        
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

    doc_no = get_field_val("InvoiceId")
    doc_date = get_field_val("InvoiceDate", "valueDate")
    
    if doc_type == "Challan":
        invoice_no = ""
        challan_no = doc_no
    else:
        invoice_no = doc_no
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
        "mode_of_transp": get_field_val("ModeOfTransport") or "",
        "dock_code": "",
        "delivery_date": get_field_val("InvoiceDate", "valueDate"),
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
