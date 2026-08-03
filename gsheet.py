import os
import json
import hashlib
import requests
import time
import db
import teams
from datetime import datetime

last_push_timestamps = {}

def compute_data_hash(invoices, challans):
    """
    Computes a deterministic MD5 hash of the invoice and challan records.
    """
    normalized_inv = []
    for inv in invoices:
        try:
            amt = round(float(str(inv.get("amount") or 0).replace(",", "").strip()), 2)
        except (ValueError, TypeError):
            amt = 0.0
            
        normalized_inv.append({
            "doc_no": str(inv.get("doc_no", "") or "").strip(),
            "doc_date": db.clean_date_string(inv.get("doc_date", "")),
            "challan_no": str(inv.get("challan_no", "") or "").strip(),
            "bill_to": str(inv.get("bill_to", "") or "").strip(),
            "po_wo_no": str(inv.get("po_wo_no", "") or "").strip(),
            "item_description": str(inv.get("item_description", "") or "").strip(),
            "amount": amt,
            "eway_bill": str(inv.get("eway_bill", "") or "").strip().upper(),
            "asn_no": str(inv.get("asn_no", "") or "").strip(),
            "mode_of_transp": str(inv.get("mode_of_transp", "") or "").strip(),
            "dock_code": str(inv.get("dock_code", "") or "").strip(),
            "delivery_date": db.clean_date_string(inv.get("delivery_date", "")),
            "delivery_site": str(inv.get("delivery_site", "") or "").strip(),
            "mrn_status": str(inv.get("mrn_status", "PENDING") or "PENDING").strip().upper(),
            "mrn_date": db.clean_date_string(inv.get("mrn_date", "")),
            "mrn_no": str(inv.get("mrn_no", "") or "").strip(),
            "remarks": str(inv.get("remarks", "") or "").strip()
        })
        
    normalized_chal = []
    for chal in challans:
        normalized_chal.append({
            "doc_no": str(chal.get("doc_no", "") or "").strip(),
            "doc_date": db.clean_date_string(chal.get("doc_date", "")),
            "invoice_no": str(chal.get("invoice_no", "") or "").strip(),
            "challan_no": str(chal.get("challan_no", "") or "").strip(),
            "bill_to": str(chal.get("bill_to", "") or "").strip(),
            "po_wo_no": str(chal.get("po_wo_no", "") or "").strip(),
            "delivery_site": str(chal.get("delivery_site", "") or "").strip(),
            "po_status": str(chal.get("po_status", "") or "").strip(),
            "item_description": str(chal.get("item_description", "") or "").strip(),
            "deliver_qty": str(chal.get("deliver_qty", "") or "").strip(),
            "uom": str(chal.get("uom", "") or "").strip(),
            "unit_price": str(chal.get("unit_price", "") or "").strip(),
            "po_qty": str(chal.get("po_qty", "") or "").strip(),
            "mrn_status": str(chal.get("mrn_status", "PENDING") or "PENDING").strip().upper(),
            "mrn_date": db.clean_date_string(chal.get("mrn_date", "")),
            "mrn_no": str(chal.get("mrn_no", "") or "").strip(),
            "remarks": str(chal.get("remarks", "") or "").strip()
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
    
    # Process-safe check to prevent concurrent overlapping pushes
    if db.get_setting(f"push_in_flight_{comp_key}") == "true":
        print(f"[Google Sheets] Skipping push for {company} because a push is already in-flight.")
        return True

    sync_url = db.get_setting(f"gsheet_sync_url_{comp_key}")
    if not sync_url:
        return False
        
    all_docs = db.get_documents(company=company)
    invoices = [d for d in all_docs if d['doc_type'] == 'Invoice']
    challans = [d for d in all_docs if d['doc_type'] == 'Challan']
    
    # Save hash immediately to prevent race conditions during background POST
    data_hash = compute_data_hash(invoices, challans)
    last_hash = db.get_setting(f"gsheet_hash_{comp_key}", "")
    if data_hash == last_hash:
        print(f"[Google Sheets] Data for {company} is already in sync with Google Sheets (hash: {data_hash}). Skipping push.")
        return True

    # Lock this push in-flight using database settings (shared across Gunicorn processes)
    db.save_setting(f"push_in_flight_{comp_key}", "true")
    db.save_setting(f"last_push_{comp_key}", str(time.time()))
    
    # 1. Format Invoices
    formatted_invoices = []
    for idx, doc in enumerate(sorted(invoices, key=db.doc_number_sort_key), 1):
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
            'E way Bill no': doc.get('eway_bill_no', ''),
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
    for doc in sorted(challans, key=db.doc_number_sort_key):
        items = str(doc.get('item_description') or '').split('\n')
        qtys = str(doc.get('deliver_qty') or '').split('\n')
        uoms = str(doc.get('uom') or '').split('\n')
        prices = str(doc.get('unit_price') or '').split('\n')
        po_qtys = doc.get('po_qty') or ''
        if isinstance(po_qtys, str):
            po_qtys = po_qtys.split('\n')
        else:
            po_qtys = [str(po_qtys)]
            
        po_statuses = doc.get('po_status') or ''
        if isinstance(po_statuses, str):
            po_statuses = po_statuses.split('\n')
        else:
            po_statuses = [str(po_statuses)]
            
        max_len = max(len(items), len(qtys), len(uoms), len(prices), len(po_qtys), len(po_statuses))
        max_len = max(max_len, 1)
        
        # Pad lists
        items += [''] * (max_len - len(items))
        qtys += [''] * (max_len - len(qtys))
        uoms += [''] * (max_len - len(uoms))
        prices += [''] * (max_len - len(prices))
        po_qtys += [''] * (max_len - len(po_qtys))
        po_statuses += [''] * (max_len - len(po_statuses))
        
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
            
            st_item = str(po_statuses[i] or '').strip()
            if not st_item:
                st_item = 'Open'
            elif st_item.upper() in ['CLOSE', 'CLOSED']:
                st_item = 'Close'
            elif st_item.upper() in ['WORK ORDER', 'WORKORDER']:
                st_item = 'Work Order'
            else:
                st_item = 'Open'

            formatted_challans.append({
                'S.No': row_idx_counter,
                'Delivery Challan No': doc.get('doc_no', ''),
                'Item Description': items[i],
                'Deliver Qty': qtys[i],
                'UOM': uoms[i],
                'Unit Price': prices[i],
                'Delivery Date': doc.get('doc_date', ''),
                'Delivery Location': doc.get('delivery_site', ''),
                'PO Status': st_item,
                'Overall PO Status': db.calculate_overall_po_status(doc),
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
            
    # 3. Format Pending MRNs (Invoices pending MRNs, matching Invoices format)
    formatted_pending = []
    pending_idx = 1
    for inv in sorted(invoices, key=db.doc_number_sort_key):
        status = str(inv.get('mrn_status', '')).upper()
        if status != 'DONE':
            formatted_pending.append({
                'S.No': pending_idx,
                'Invoice No': inv.get('doc_no', ''),
                'Invoice Date': inv.get('doc_date', ''),
                'Challan No': inv.get('challan_no', ''),
                'Bill To': inv.get('bill_to', ''),
                'PO/WO No': inv.get('po_wo_no', ''),
                'Item Description': inv.get('item_description', ''),
                'Invoice Amt': inv.get('amount', 0.0),
                'Eway Bill': inv.get('eway_bill', ''),
                'E way Bill no': inv.get('eway_bill_no', ''),
                'ASN No': inv.get('asn_no', ''),
                'Mode of Transp': inv.get('mode_of_transp', ''),
                'Dock Code': inv.get('dock_code', ''),
                'Delivery Date': inv.get('delivery_date', ''),
                'Delivery Site': inv.get('delivery_site', ''),
                'MRN Status': inv.get('mrn_status', 'PENDING'),
                'MRN Date': inv.get('mrn_date', ''),
                'MRN No': inv.get('mrn_no', ''),
                'Remarks': inv.get('remarks', '')
            })
            pending_idx += 1
            
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
            try:
                res_data = resp.json()
            except Exception as json_err:
                print(f"[Google Sheets] JSON Decode Error. Response text was:\n{resp.text[:2000]}")
                raise json_err
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
    finally:
        db.save_setting(f"push_in_flight_{comp_key}", "false")
        
    return False

def sync_from_google_sheet(company):
    """
    Fetches the ledger sheets from Google Sheets, checks for updates, and syncs them back to the local database.
    """
    comp_key = company.lower().replace(' ', '_')
    
    # Batch retrieve settings to save connection overheads
    settings = db.get_settings_dict([
        f"push_in_flight_{comp_key}",
        f"last_push_{comp_key}",
        f"gsheet_sync_url_{comp_key}"
    ])
    
    # 1. Skip pull if a push is currently in-flight
    if settings.get(f"push_in_flight_{comp_key}") == "true":
        print(f"[Google Sheets] Skipping pull sync for {company} because a push is currently in-flight.")
        return True
        
    # 2. Skip pull if the last push was very recent to allow Google Sheets to settle and avoid stale reads
    try:
        last_push = float(settings.get(f"last_push_{comp_key}", "0"))
    except ValueError:
        last_push = 0.0
        
    if time.time() - last_push < 5.0:
        print(f"[Google Sheets] Skipping pull sync for {company} because a push happened recently ({time.time() - last_push:.1f}s ago).")
        return True

    sync_url = settings.get(f"gsheet_sync_url_{comp_key}")
    if not sync_url:
        return False
        
    try:
        # Load all deleted documents set to avoid looping select queries
        deleted_docs = db.get_deleted_documents_set(company)
        print(f"[Google Sheets] Pulling data from Google Sheet for {company}...")
        resp = requests.get(f"{sync_url}?action=read", timeout=5)
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
            'E way Bill no': 'eway_bill_no',
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
            if not doc_no or (('invoice', doc_no.lower()) in deleted_docs):
                continue
                
            inv_db = {}
            for col_name, db_name in excel_to_db_inv.items():
                val = inv_row.get(col_name)
                if db_name in ['doc_date', 'delivery_date', 'mrn_date']:
                    val = db.clean_date_string(val)
                inv_db[db_name] = None if val == "" else val
                
            inv_db['company'] = company
            inv_db['doc_type'] = 'Invoice'
            inv_db['challan_no'] = db.clean_challan_no(inv_db.get('challan_no'), doc_no)
            
            # Clean fields
            if inv_db.get('amount') is not None:
                try:
                    inv_db['amount'] = float(str(inv_db['amount']).replace(',', '').strip())
                except ValueError:
                    inv_db['amount'] = 0.0
            else:
                inv_db['amount'] = 0.0
                
            # Clean and enforce E-way bill rules
            eway_status = str(inv_db.get('eway_bill', '')).strip()
            eway_no = str(inv_db.get('eway_bill_no', '')).strip()
            
            if eway_status and eway_status.upper() not in ['PENDING', 'N/A', 'DONE', 'NONE', 'NULL', '-']:
                if not eway_no:
                    eway_no = eway_status
                eway_status = "DONE"
                
            try:
                amt = float(inv_db.get('amount') or 0.0)
            except (ValueError, TypeError):
                amt = 0.0
                
            if eway_no and eway_no.upper() not in ['PENDING', 'N/A', 'DONE', 'NONE', 'NULL', '-']:
                inv_db['eway_bill_no'] = eway_no
                inv_db['eway_bill'] = "DONE"
            else:
                inv_db['eway_bill_no'] = ""
                if amt < 50000:
                    inv_db['eway_bill'] = "N/A"
                else:
                    inv_db['eway_bill'] = "PENDING"
                
            parsed_invoices.append(inv_db)
            
        # 2. Group & Parse Delivery Challans
        grouped_challans = {}
        
        for chal_row in challans_list:
            doc_no = str(chal_row.get('Delivery Challan No') or '').strip()
            if not doc_no or (('challan', doc_no.lower()) in deleted_docs):
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
                    'mrn_status': chal_row.get('MRN Status') or 'PENDING',
                    'mrn_date': db.clean_date_string(chal_row.get('MRN Date')),
                    'mrn_no': chal_row.get('MRN No'),
                    'remarks': chal_row.get('Remarks'),
                    
                    '_items': [],
                    '_qtys': [],
                    '_uoms': [],
                    '_prices': [],
                    '_po_qtys': [],
                    '_po_statuses': []
                }
                
            gd = grouped_challans[doc_no]
            gd['_items'].append(str(chal_row.get('Item Description') or '').strip())
            gd['_qtys'].append(str(chal_row.get('Deliver Qty') or '').strip())
            gd['_uoms'].append(str(chal_row.get('UOM') or '').strip())
            gd['_prices'].append(str(chal_row.get('Unit Price') or '').strip())
            gd['_po_qtys'].append(str(chal_row.get('PO Qty') or '').strip())
            gd['_po_statuses'].append(str(chal_row.get('PO Status') or '').strip())
            
        parsed_challans = []
        for doc_no, gd in grouped_challans.items():
            gd['item_description'] = "\n".join(gd['_items'])
            gd['deliver_qty'] = "\n".join(gd['_qtys'])
            gd['uom'] = "\n".join(gd['_uoms'])
            gd['unit_price'] = "\n".join(gd['_prices'])
            gd['po_qty'] = "\n".join(gd['_po_qtys'])
            gd['po_status'] = "\n".join(gd['_po_statuses'])
            
            for k in ['_items', '_qtys', '_uoms', '_prices', '_po_qtys', '_po_statuses']:
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
        
        cursor.execute("SELECT doc_no, mrn_status, mrn_no, mrn_date FROM documents WHERE company = ?", (company,))
        existing_status_map = {
            row['doc_no']: {
                'mrn_status': str(row['mrn_status'] or '').strip().upper(),
                'mrn_no': row['mrn_no'],
                'mrn_date': row['mrn_date']
            }
            for row in cursor.fetchall()
        }

        # 5. Non-locking Upsert company documents inside database transaction
        try:
            non_pk_fields = [
                'doc_date', 'invoice_no', 'challan_no', 'bill_to', 'po_wo_no',
                'item_description', 'amount', 'eway_bill', 'eway_bill_no', 'asn_no',
                'mode_of_transp', 'dock_code', 'delivery_date', 'delivery_site',
                'mrn_status', 'mrn_date', 'mrn_no', 'remarks', 'deliver_qty',
                'uom', 'unit_price', 'po_status', 'po_qty'
            ]
            update_assignments = ", ".join([f"{f} = excluded.{f}" for f in non_pk_fields])
            
            # Upsert Invoices & Challans
            for item in (parsed_invoices + parsed_challans):
                item_to_save = {k: v for k, v in item.items() if k != 'S.No'}
                columns = ", ".join(item_to_save.keys())
                placeholders = ", ".join(["?"] * len(item_to_save))
                values = tuple(item_to_save.values())
                
                query = (
                    f"INSERT INTO documents ({columns}) VALUES ({placeholders}) "
                    f"ON CONFLICT (company, doc_type, doc_no) DO UPDATE SET {update_assignments}"
                )
                cursor.execute(query, values)
                
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
                
                old_info = existing_status_map.get(doc_no, {'mrn_status': 'PENDING', 'mrn_no': None})
                old_status = old_info.get('mrn_status', 'PENDING')
                old_mrn = old_info.get('mrn_no')
                
                # Check for updates or transitions
                if old_status != new_status or (new_status == 'DONE' and new_mrn_no != old_mrn):
                    doc_type_label = "Invoice" if doc.get("doc_type") == "Invoice" else "Delivery Challan"
                    card_data = {
                        "message": f"MRN details updated via **Google Sheets** for {doc_type_label} **{doc_no}** ({company}):\n\n* **MRN Status**: {new_status}\n* **MRN No**: {new_mrn_no}\n* **MRN Date**: {doc.get('mrn_date')}\n* **Remarks**: {doc.get('remarks')}"
                    }
                    import threading
                    threading.Thread(target=teams.send_teams_notification, args=(webhook_url, "update", card_data), daemon=True).start()
                    
        print(f"[Google Sheets] Google Sheets sync to database completed for {company}.")
        return True
    except Exception as e:
        print(f"[Google Sheets] Error in sync_from_google_sheet for {company}: {e}")
        
    return False
