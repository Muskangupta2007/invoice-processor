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

def extract_challan_number(result_json_or_content, raw_content=None):
    """
    Extracts Delivery Challan Number from Azure Document Intelligence result JSON
    (Key-Value pairs & document fields) or raw OCR text content.
    """
    result_json = result_json_or_content if isinstance(result_json_or_content, dict) else {}
    content = raw_content if raw_content is not None else (result_json_or_content if isinstance(result_json_or_content, str) else "")

    # 1. Inspect Azure Document Intelligence Key-Value Pairs if present
    analyze_result = result_json.get("analyzeResult", {})
    kv_pairs = analyze_result.get("keyValuePairs", [])
    for kv in kv_pairs:
        key_text = str(kv.get("key", {}).get("content", "")).lower()
        val_text = str(kv.get("value", {}).get("content", "")).strip()
        if ("challan" in key_text or "dc no" in key_text or "dc number" in key_text or "delivery challan" in key_text) and val_text:
            if val_text.upper() not in ['DIRECT INVOICE', 'N/A', 'NONE', 'NULL', '-']:
                return val_text

    # 2. Inspect Document Level Fields
    documents = analyze_result.get("documents", [])
    if documents:
        fields = documents[0].get("fields", {})
        for field_key in ["ChallanNumber", "ChallanNo", "DeliveryChallanNumber", "DeliveryChallanNo", "DCNo", "DCNumber"]:
            if field_key in fields:
                f_val = str(fields[field_key].get("valueString") or fields[field_key].get("content") or "").strip()
                if f_val and f_val.upper() not in ['DIRECT INVOICE', 'N/A', 'NONE', 'NULL', '-']:
                    return f_val

    if not content:
        return None
        
    normalized_content = " ".join(str(content).split())
    
    # 3. Regex matching Challan No patterns in OCR content
    patterns = [
        r'(?i)(?:delivery\s*challan|challan|d\.?c\.?)\s*(?:no|number|num)?\s*[\.:#-]*\s*([a-zA-Z0-9/\-_]{3,35})',
        r'(?i)(?:challan|delivery\s*challan)\s*[\.:#-]*\s*([a-zA-Z0-9/\-_]{3,35})'
    ]
    
    for pat in patterns:
        match = re.search(pat, normalized_content)
        if match:
            extracted_val = match.group(1).strip().rstrip('.,;:')
            if extracted_val and extracted_val.upper() not in ['DIRECT INVOICE', 'N/A', 'NONE', 'NULL', '-', 'DATE', 'BILL']:
                return extracted_val
                
    return None

def parse_azure_invoice_result(result, doc_type="Invoice"):
    """
    Helper function to parse Azure Analyze Result JSON and map it to our target schema.
    Supports joining item descriptions, quantities, units, and unit prices with newlines.
    """
    analyze_result = result.get("analyzeResult", {})
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
        challan_no = extracted_challan if extracted_challan else "DIRECT INVOICE"

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
