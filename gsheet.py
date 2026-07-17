import os
import json
import hashlib
import requests
import db
import teams
from datetime import datetime

def compute_data_hash(invoices, challans):
    """
    Computes a deterministic MD5 hash of the invoice and challan records.
    """
    normalized_inv = []
    for inv in invoices:
        normalized_inv.append({
            "doc_no": str(inv.get("doc_no", "")).strip(),
            "doc_date": str(inv.get("doc_date", "")).strip(),
            "challan_no": str(inv.get("challan_no", "")).strip(),
            "bill_to": str(inv.get("bill_to", "")).strip(),
            "po_wo_no": str(inv.get("po_wo_no", "")).strip(),
            "item_description": str(inv.get("item_description", "")).strip(),
            "amount": float(inv.get("amount") or 0.0),
            "eway_bill": str(inv.get("eway_bill", "")).strip(),
            "asn_no": str(inv.get("asn_no", "")).strip(),
            "mode_of_transp": str(inv.get("mode_of_transp", "")).strip(),
            "dock_code": str(inv.get("dock_code", "")).strip(),
            "delivery_date": str(inv.get("delivery_date", "")).strip(),
            "delivery_site": str(inv.get("delivery_site", "")).strip(),
            "mrn_status": str(inv.get("mrn_status", "PENDING")).strip(),
            "mrn_date": str(inv.get("mrn_date", "")).strip(),
            "mrn_no": str(inv.get("mrn_no", "")).strip(),
            "remarks": str(inv.get("remarks", "")).strip()
        })
        
    normalized_chal = []
    for chal in challans:
        normalized_chal.append({
            "doc_no": str(chal.get("doc_no", "")).strip(),
            "doc_date": str(chal.get("doc_date", "")).strip(),
            "invoice_no": str(chal.get("invoice_no", "")).strip(),
            "challan_no": str(chal.get("challan_no", "")).strip(),
            "bill_to": str(chal.get("bill_to", "")).strip(),
            "po_wo_no": str(chal.get("po_wo_no", "")).strip(),
            "delivery_site": str(chal.get("delivery_site", "")).strip(),
            "po_status": str(chal.get("po_status", "")).strip(),
            "item_description": str(chal.get("item_description", "")).strip(),
            "deliver_qty": str(chal.get("deliver_qty", "")).strip(),
            "uom": str(chal.get("uom", "")).strip(),
            "unit_price": str(chal.get("unit_price", "")).strip(),
            "po_qty": str(chal.get("po_qty", "")).strip(),
            "mrn_status": str(chal.get("mrn_status", "PENDING")).strip(),
            "mrn_date": str(chal.get("mrn_date", "")).strip(),
            "mrn_no": str(chal.get("mrn_no", "")).strip(),
            "remarks": str(chal.get("remarks", "")).strip()
        })
        
    # Sort to ensure deterministic hashing
    normalized_inv.sort(key=lambda x: x["doc_no"])
    normalized_chal.sort(key=lambda x: (x["doc_no"], x["item_description"]))
    
    data_dict = {
        "invoices": normalized_inv,
        "challans": normalized_chal
    }
    
    data_str = json.dumps(data_dict, sort_keys=True)
    return hashlib.md5(data_str.encode('utf-8')).hexdigest()

def sync_to_google_sheet(company):
    """
    Sends the database ledger records for a company to their Google Sheet.
    """
    comp_key = company.lower().replace(' ', '_')
    sync_url = db.get_setting(f"gsheet_sync_url_{comp_key}")
    if not sync_url:
        return False
        
    all_docs = db.get_documents(company=company)
    invoices = [d for d in all_docs if d['doc_type'] == 'Invoice']
    challans = [d for d in all_docs if d['doc_type'] == 'Challan']
    
    # 1. Format Invoices
    formatted_invoices = []
    for idx, doc in enumerate(sorted(invoices, key=lambda x: x['id']), 1):
        formatted_invoices.append({
            'S.No': idx,
            'Invoice No': doc.get('doc_no', ''),
            'Invoice Date': doc.get('doc_date', ''),
            'Challan No': doc.get('challan_no', ''),
            'Bill To': doc.get('bill_to', ''),
            'PO/WO No': doc.get('po_wo_no', ''),
            'Item Description': doc.get('item_description', ''),
            'Invoice Amt': doc.get('amount', 0.0),
            'Eway Bill': doc.get('eway_bill', ''),
            'ASN No': doc.get('asn_no', ''),
            'Mode of Transp': doc.get('mode_of_transp', ''),
            'Dock Code': doc.get('dock_code', ''),
            'Delivery Date': doc.get('delivery_date', ''),
            'Delivery Site': doc.get('delivery_site', ''),
            'MRN Status': doc.get('mrn_status', 'PENDING'),
            'MRN Date': doc.get('mrn_date', ''),
            'MRN No': doc.get('mrn_no', ''),
            'Remarks': doc.get('remarks', '')
        })
        
    # 2. Format Delivery Challans (expanded to individual item rows)
    formatted_challans = []
    row_idx_counter = 1
    for doc in sorted(challans, key=lambda x: x['id']):
        items = str(doc.get('item_description') or '').split('\n')
        qtys = str(doc.get('deliver_qty') or '').split('\n')
        uoms = str(doc.get('uom') or '').split('\n')
        prices = str(doc.get('unit_price') or '').split('\n')
        po_qtys = str(doc.get('po_qty') or '').split('\n')
        
        max_len = max(len(items), len(qtys), len(uoms), len(prices), len(po_qtys))
        max_len = max(max_len, 1)
        
        # Pad lists
        items += [''] * (max_len - len(items))
        qtys += [''] * (max_len - len(qtys))
        uoms += [''] * (max_len - len(uoms))
        prices += [''] * (max_len - len(prices))
        po_qtys += [''] * (max_len - len(po_qtys))
        
        for i in range(max_len):
            # Calculate difference for this specific line
            d_val = 0.0
            p_val = 0.0
            try:
                if qtys[i]:
                    d_val = float(qtys[i].replace(',', '').strip())
            except ValueError:
                pass
            try:
                if po_qtys[i]:
                    p_val = float(po_qtys[i].replace(',', '').strip())
            except ValueError:
                pass
            diff = d_val - p_val
            diff_str = str(int(diff)) if diff.is_integer() else f"{diff:.2f}"
            
            formatted_challans.append({
                'S.No': row_idx_counter,
                'Delivery Challan No': doc.get('doc_no', ''),
                'Item Description': items[i],
                'Deliver Qty': qtys[i],
                'UOM': uoms[i],
                'Unit Price': prices[i],
                'Delivery Date': doc.get('doc_date', ''),
                'Delivery Location': doc.get('delivery_site', ''),
                'PO Status': doc.get('po_status', ''),
                'PO Number': doc.get('po_wo_no', ''),
                'PO Qty': po_qtys[i],
                'Difference Between Delivery & PO Qty': diff_str,
                'Invoice Number': doc.get('invoice_no', ''),
                'MRN Status': doc.get('mrn_status', 'PENDING'),
                'MRN Date': doc.get('mrn_date', ''),
                'MRN No': doc.get('mrn_no', ''),
                'Remarks': doc.get('remarks', '')
            })
            row_idx_counter += 1
            
    # 3. Format Pending MRNs
    formatted_pending = []
    # Invoices pending
    for inv in invoices:
        status = str(inv.get('mrn_status', '')).upper()
        mrn_no = inv.get('mrn_no')
        if status != 'DONE' or not mrn_no or str(mrn_no).strip() == '':
            formatted_pending.append({
                'Type': 'Invoice',
                'Doc No': inv.get('doc_no', ''),
                'Doc Date': inv.get('doc_date', ''),
                'Bill To': inv.get('bill_to', ''),
                'PO/WO No': inv.get('po_wo_no', ''),
                'Amount': inv.get('amount', 0.0),
                'Remarks': inv.get('remarks', '')
            })
    # Challans pending
    for chal in challans:
        status = str(chal.get('mrn_status', '')).upper()
        mrn_no = chal.get('mrn_no')
        if status != 'DONE' or not mrn_no or str(mrn_no).strip() == '':
            formatted_pending.append({
                'Type': 'Delivery Challan',
                'Doc No': chal.get('doc_no', ''),
                'Doc Date': chal.get('doc_date', ''),
                'Bill To': chal.get('bill_to', ''),
                'PO/WO No': chal.get('po_wo_no', ''),
                'Amount': chal.get('amount', 0.0),
                'Remarks': chal.get('remarks', '')
            })
            
    # POST payload to Apps Script Web App
    payload = {
        "action": "write",
        "invoices": formatted_invoices,
        "challans": formatted_challans,
        "pending": formatted_pending
    }
    
    try:
        print(f"[Google Sheets] Pushing update to Google Sheet for {company}...")
        resp = requests.post(sync_url, json=payload, timeout=15)
        if resp.status_code == 200:
            res_data = resp.json()
            if res_data.get("status") == "success":
                # Compute and save the hash to prevent self-sync loop
                data_hash = compute_data_hash(invoices, challans)
                db.save_setting(f"gsheet_hash_{comp_key}", data_hash)
                print(f"[Google Sheets] Push sync successful for {company}. Hash saved: {data_hash}")
                return True
            else:
                print(f"[Google Sheets] Error from Web App for {company}: {res_data.get('message')}")
        else:
            print(f"[Google Sheets] HTTP Error pushing to {company}: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"[Google Sheets] Exception during push sync for {company}: {e}")
        
    return False

def sync_from_google_sheet(company):
    """
    Fetches the ledger sheets from Google Sheets, checks for updates, and syncs them back to the local database.
    """
    comp_key = company.lower().replace(' ', '_')
    sync_url = db.get_setting(f"gsheet_sync_url_{comp_key}")
    if not sync_url:
        return False
        
    try:
        print(f"[Google Sheets] Pulling data from Google Sheet for {company}...")
        resp = requests.get(f"{sync_url}?action=read", timeout=15)
        if resp.status_code != 200:
            print(f"[Google Sheets] HTTP Error pulling from {company}: {resp.status_code}")
            return False
            
        sheet_data = resp.json()
        invoices_list = sheet_data.get("invoices", [])
        challans_list = sheet_data.get("challans", [])
        
        # 1. Parse Invoices
        parsed_invoices = []
        excel_to_db_inv = {
            'Invoice No': 'doc_no',
            'Invoice Date': 'doc_date',
            'Challan No': 'challan_no',
            'Bill To': 'bill_to',
            'PO/WO No': 'po_wo_no',
            'Item Description': 'item_description',
            'Invoice Amt': 'amount',
            'Eway Bill': 'eway_bill',
            'ASN No': 'asn_no',
            'Mode of Transp': 'mode_of_transp',
            'Dock Code': 'dock_code',
            'Delivery Date': 'delivery_date',
            'Delivery Site': 'delivery_site',
            'MRN Status': 'mrn_status',
            'MRN Date': 'mrn_date',
            'MRN No': 'mrn_no',
            'Remarks': 'remarks'
        }
        
        for inv_row in invoices_list:
            doc_no = str(inv_row.get('Invoice No') or '').strip()
            if not doc_no:
                continue
                
            inv_db = {}
            for col_name, db_name in excel_to_db_inv.items():
                val = inv_row.get(col_name)
                if db_name in ['doc_date', 'delivery_date', 'mrn_date']:
                    val = db.clean_date_string(val)
                inv_db[db_name] = None if val == "" else val
                
            inv_db['company'] = company
            inv_db['doc_type'] = 'Invoice'
            
            # Clean fields
            if inv_db.get('amount') is not None:
                try:
                    inv_db['amount'] = float(str(inv_db['amount']).replace(',', '').strip())
                except ValueError:
                    inv_db['amount'] = 0.0
            else:
                inv_db['amount'] = 0.0
                
            parsed_invoices.append(inv_db)
            
        # 2. Group & Parse Delivery Challans
        grouped_challans = {}
        
        for chal_row in challans_list:
            doc_no = str(chal_row.get('Delivery Challan No') or '').strip()
            if not doc_no:
                continue
                
            if doc_no not in grouped_challans:
                grouped_challans[doc_no] = {
                    'doc_no': doc_no,
                    'doc_date': db.clean_date_string(chal_row.get('Delivery Date')),
                    'invoice_no': chal_row.get('Invoice Number'),
                    'challan_no': doc_no,
                    'bill_to': chal_row.get('Bill To') or 'LARSEN & TOUBRO',
                    'po_wo_no': chal_row.get('PO Number'),
                    'delivery_site': chal_row.get('Delivery Location'),
                    'po_status': chal_row.get('PO Status'),
                    'mrn_status': chal_row.get('MRN Status') or 'PENDING',
                    'mrn_date': db.clean_date_string(chal_row.get('MRN Date')),
                    'mrn_no': chal_row.get('MRN No'),
                    'remarks': chal_row.get('Remarks'),
                    
                    '_items': [],
                    '_qtys': [],
                    '_uoms': [],
                    '_prices': [],
                    '_po_qtys': []
                }
                
            gd = grouped_challans[doc_no]
            gd['_items'].append(str(chal_row.get('Item Description') or '').strip())
            gd['_qtys'].append(str(chal_row.get('Deliver Qty') or '').strip())
            gd['_uoms'].append(str(chal_row.get('UOM') or '').strip())
            gd['_prices'].append(str(chal_row.get('Unit Price') or '').strip())
            gd['_po_qtys'].append(str(chal_row.get('PO Qty') or '').strip())
            
        parsed_challans = []
        for doc_no, gd in grouped_challans.items():
            gd['item_description'] = "\n".join(gd['_items'])
            gd['deliver_qty'] = "\n".join(gd['_qtys'])
            gd['uom'] = "\n".join(gd['_uoms'])
            gd['unit_price'] = "\n".join(gd['_prices'])
            gd['po_qty'] = "\n".join(gd['_po_qtys'])
            
            for k in ['_items', '_qtys', '_uoms', '_prices', '_po_qtys']:
                del gd[k]
                
            gd['company'] = company
            gd['doc_type'] = 'Challan'
            gd['amount'] = 0.0
            
            # Clean fields
            for f in ['deliver_qty', 'uom', 'unit_price', 'po_qty']:
                if f in gd and gd[f] is not None:
                    gd[f] = str(gd[f])
                    
            parsed_challans.append(gd)
            
        # 3. Check Hash of New Data against last synced hash
        incoming_hash = compute_data_hash(parsed_invoices, parsed_challans)
        last_hash = db.get_setting(f"gsheet_hash_{comp_key}", "")
        
        if incoming_hash == last_hash:
            # Data is already in sync, skip DB update
            return True
            
        print(f"[Google Sheets] Modifications detected in Google Sheets for {company}! Hash: {incoming_hash} (prev: {last_hash}). Updating database...")
        
        # 4. Fetch existing records to check for MRN status transitions
        conn = db.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT doc_no, mrn_status, mrn_no FROM documents WHERE company = ?", (company,))
        existing_status_map = {row['doc_no']: (row['mrn_status'], row['mrn_no']) for row in cursor.fetchall()}
        
        # 5. Overwrite company documents inside database transaction
        try:
            cursor.execute("DELETE FROM documents WHERE company = ?", (company,))
            
            # Insert Invoices
            for inv in parsed_invoices:
                # Remove S.No if exists
                inv_to_save = {k: v for k, v in inv.items() if k != 'S.No'}
                columns = ", ".join(inv_to_save.keys())
                placeholders = ", ".join(["?"] * len(inv_to_save))
                values = tuple(inv_to_save.values())
                cursor.execute(f"INSERT INTO documents ({columns}) VALUES ({placeholders})", values)
                
            # Insert Challans
            for chal in parsed_challans:
                chal_to_save = {k: v for k, v in chal.items() if k != 'S.No'}
                columns = ", ".join(chal_to_save.keys())
                placeholders = ", ".join(["?"] * len(chal_to_save))
                values = tuple(chal_to_save.values())
                cursor.execute(f"INSERT INTO documents ({columns}) VALUES ({placeholders})", values)
                
            conn.commit()
        except Exception as db_err:
            conn.rollback()
            print(f"[Google Sheets] Database transaction failed during Google Sheets pull for {company}: {db_err}")
            return False
        finally:
            conn.close()
            
        # Save the new hash to settings to prevent loop back
        db.save_setting(f"gsheet_hash_{comp_key}", incoming_hash)
        
        # 6. Regenerate local Excel sheets to stay in sync
        try:
            db.sync_to_excel(company, sync_main=True, sync_pending=True)
        except Exception as xl_err:
            print(f"[Google Sheets] Error syncing local Excel on Google Sheet update: {xl_err}")
            
        # 7. Check for MRN Status changes and trigger Teams notifications
        webhook_url = db.get_setting("teams_webhook_url")
        if webhook_url:
            all_parsed = parsed_invoices + parsed_challans
            for doc in all_parsed:
                doc_no = doc.get("doc_no")
                new_status = doc.get("mrn_status")
                new_mrn_no = doc.get("mrn_no")
                
                old_status, old_mrn = existing_status_map.get(doc_no, ("PENDING", None))
                
                # Check for updates or transitions
                if old_status != new_status or (new_status == 'DONE' and new_mrn_no != old_mrn):
                    doc_type_label = "Invoice" if doc.get("doc_type") == "Invoice" else "Delivery Challan"
                    card_data = {
                        "message": f"MRN details updated via **Google Sheets** for {doc_type_label} **{doc_no}** ({company}):\n\n* **MRN Status**: {new_status}\n* **MRN No**: {new_mrn_no}\n* **MRN Date**: {doc.get('mrn_date')}\n* **Remarks**: {doc.get('remarks')}"
                    }
                    teams.send_teams_notification(webhook_url, "update", card_data)
                    
        print(f"[Google Sheets] Google Sheets sync to database completed for {company}.")
        return True
    except Exception as e:
        print(f"[Google Sheets] Error in sync_from_google_sheet for {company}: {e}")
        
    return False
