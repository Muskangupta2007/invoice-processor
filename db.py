import os
import sqlite3
import pandas as pd
import re
from datetime import datetime
import threading
import time
from werkzeug.security import generate_password_hash, check_password_hash

# For PostgreSQL support
try:
    import psycopg2
    import psycopg2.extras
    from psycopg2.pool import ThreadedConnectionPool
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    ThreadedConnectionPool = None

db_pool = None

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "invoices.db")

COMPANIES = ['SK Agro', 'SK Electricals', 'Triotech']

# Tracks modification times of Excel files saved by the app to prevent self-sync loops
last_written_mtime = {}

class PostgresCursorWrapper:
    def __init__(self, real_cursor):
        self.cursor = real_cursor

    def execute(self, query, params=None):
        if "INTEGER PRIMARY KEY AUTOINCREMENT" in query:
            query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        
        if "INSERT OR IGNORE INTO documents" in query:
            query = query.replace("INSERT OR IGNORE INTO documents", "INSERT INTO documents")
            query += " ON CONFLICT (company, doc_type, doc_no) DO NOTHING"
            
        if "INSERT OR IGNORE INTO settings" in query:
            query = query.replace("INSERT OR IGNORE INTO settings", "INSERT INTO settings")
            query += " ON CONFLICT (key) DO NOTHING"

        query = query.replace('?', '%s')

        if params is not None:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is not None:
            return dict(row)
        return None

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [dict(r) for r in rows]

    @property
    def rowcount(self):
        return self.cursor.rowcount

    def close(self):
        self.cursor.close()

class PostgresConnectionWrapper:
    def __init__(self, real_conn, is_from_pool=False):
        self.conn = real_conn
        self.is_from_pool = is_from_pool

    def cursor(self):
        return PostgresCursorWrapper(self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor))

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        if self.is_from_pool and db_pool:
            db_pool.putconn(self.conn)
        else:
            self.conn.close()

def get_db_connection():
    global db_pool
    db_url = os.environ.get('DATABASE_URL')
    if db_url and HAS_PSYCOPG2:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
            
        if db_pool is None and ThreadedConnectionPool:
            try:
                db_pool = ThreadedConnectionPool(1, 20, db_url)
                print("[DB Pool] Connection pool initialized successfully.")
            except Exception as e:
                print(f"[DB Pool] Error initializing pool: {e}")
                
        if db_pool:
            try:
                conn = db_pool.getconn()
                return PostgresConnectionWrapper(conn, is_from_pool=True)
            except Exception as e:
                print(f"[DB Pool] Failed to fetch connection: {e}. Falling back to single connection.")
                
        conn = psycopg2.connect(db_url)
        return PostgresConnectionWrapper(conn)
    else:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except Exception:
            pass
        conn.row_factory = sqlite3.Row
        return conn

def clean_date_string(date_str):
    if not date_str:
        return ""
    date_str = str(date_str).strip()
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    parts = date_str.split(' ')
    if len(parts) > 1 and ':' in parts[1]:
        date_str = parts[0]
        
    # Standardize YYYY-MM-DD format to DD Month YYYY
    try:
        from datetime import datetime
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d %B %Y")
    except ValueError:
        pass
        
    return date_str

def get_excel_storage_dir():
    custom_dir = get_setting("excel_storage_directory", "")
    if custom_dir:
        custom_dir = custom_dir.strip().strip('"').strip("'").strip()
        if os.path.exists(custom_dir):
            return custom_dir
    return os.path.dirname(os.path.abspath(__file__))

def get_company_excel_path(company, file_type='main'):
    directory = get_excel_storage_dir()
    safe_company = company.replace(' ', '_')
    if file_type == 'pending':
        file_name = f"{safe_company}_Pending_MRN.xlsx"
    else:
        file_name = f"{safe_company}.xlsx"
    return os.path.join(directory, file_name)

def check_excel_writable(company):
    main_excel_path = get_company_excel_path(company, 'main')
    pending_excel_path = get_company_excel_path(company, 'pending')
    for path in [main_excel_path, pending_excel_path]:
        if os.path.exists(path):
            try:
                with open(path, 'r+'):
                    pass
            except PermissionError as e:
                raise PermissionError(f"The Excel file '{os.path.basename(path)}' is currently open or locked. Please close it in Microsoft Excel and try again.") from e
            except Exception:
                pass

def clean_challan_no(val, doc_no=None):
    if not val:
        return "DIRECT INVOICE"
    s_val = str(val).strip()
    
    # Specific known fix for SKH/26-27/224 if it had 'of' or empty
    if doc_no and 'SKH/26-27/224' in str(doc_no).upper() and s_val.lower() in ['of', 'mode/terms', '', 'direct invoice']:
        return "SKH/DC/26-27/116"

    upper_val = s_val.upper()
    if upper_val in ['OF', 'MODE/TERMS', 'PAYMENT', 'DELIVERY', 'REFERENCE', 'ORDER', 'INVOICE', 'DATE', 'DATED', 'DISPATCH', 'N/A', 'NONE', 'NULL', '-']:
        return "DIRECT INVOICE"
    if any(upper_val.startswith(w) for w in ['MODE/', 'TERMS/', 'PAYMENT/', 'DATE/', 'BUYER/', 'SUPPLIER/']):
        return "DIRECT INVOICE"
        
    if not re.search(r'\d', s_val) and upper_val != "DIRECT INVOICE":
        return "DIRECT INVOICE"
        
    return s_val

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            company TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            doc_no TEXT NOT NULL,
            doc_date TEXT,
            invoice_no TEXT,
            challan_no TEXT,
            bill_to TEXT,
            po_wo_no TEXT,
            item_description TEXT,
            amount REAL,
            eway_bill TEXT,
            eway_bill_no TEXT,
            asn_no TEXT,
            mode_of_transp TEXT,
            dock_code TEXT,
            delivery_date TEXT,
            delivery_site TEXT,
            mrn_status TEXT DEFAULT 'PENDING',
            mrn_date TEXT,
            mrn_no TEXT,
            remarks TEXT,
            deliver_qty TEXT,
            uom TEXT,
            unit_price TEXT,
            po_status TEXT,
            po_qty TEXT,
            PRIMARY KEY (company, doc_type, doc_no)
        )
    """)
    
    # Table for tracking user-deleted documents to permanently prevent background sync from resurrecting them
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deleted_documents (
            company TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            doc_no TEXT NOT NULL,
            deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (company, doc_type, doc_no)
        )
    """)
    
    # Perform schema migrations for new columns
    for col, col_type in [
        ('eway_bill_no', 'TEXT'),
        ('asn_no', 'TEXT'),
        ('mode_of_transp', 'TEXT'),
        ('dock_code', 'TEXT'),
        ('delivery_date', 'TEXT'),
        ('delivery_site', 'TEXT'),
        ('mrn_status', "TEXT DEFAULT 'PENDING'"),
        ('mrn_date', 'TEXT'),
        ('mrn_no', 'TEXT'),
        ('remarks', 'TEXT'),
        ('deliver_qty', 'TEXT'),
        ('uom', 'TEXT'),
        ('unit_price', 'TEXT'),
        ('po_status', 'TEXT'),
        ('po_qty', 'TEXT')
    ]:
        try:
            cursor.execute(f"ALTER TABLE documents ADD COLUMN {col} {col_type}")
        except Exception:
            pass
    
    # Clean up hardcoded mock ASN numbers and enforce strict E-Way Bill and Challan No status rules in database
    try:
        cursor.execute("UPDATE documents SET asn_no = '' WHERE asn_no = 'ASN/26/000797'")
        cursor.execute("UPDATE documents SET mode_of_transp = '' WHERE mode_of_transp = 'Tempo'")
        cursor.execute("UPDATE documents SET eway_bill_no = '' WHERE UPPER(TRIM(eway_bill_no)) IN ('DONE', 'PENDING', 'N/A', 'NONE', 'NULL', '-')")
        cursor.execute("UPDATE documents SET eway_bill = 'N/A' WHERE doc_type = 'Invoice' AND (eway_bill_no IS NULL OR TRIM(eway_bill_no) = '' OR UPPER(TRIM(eway_bill_no)) IN ('DONE', 'PENDING', 'N/A', 'NONE', 'NULL', '-')) AND CAST(amount AS REAL) < 50000")
        cursor.execute("UPDATE documents SET eway_bill = 'PENDING' WHERE doc_type = 'Invoice' AND (eway_bill_no IS NULL OR TRIM(eway_bill_no) = '' OR UPPER(TRIM(eway_bill_no)) IN ('DONE', 'PENDING', 'N/A', 'NONE', 'NULL', '-')) AND CAST(amount AS REAL) >= 50000")
        cursor.execute("UPDATE documents SET challan_no = 'SKH/DC/26-27/116' WHERE doc_no = 'SKH/26-27/224'")
        cursor.execute("UPDATE documents SET challan_no = 'DIRECT INVOICE' WHERE UPPER(TRIM(challan_no)) IN ('OF', 'MODE/TERMS', 'PAYMENT', 'DELIVERY', 'TERMS', 'REF', 'NO', 'NO.') OR challan_no LIKE 'of%' OR challan_no LIKE 'Mode%'")
        conn.commit()
    except Exception as clean_err:
        print(f"[DB Init] Cleanup warning: {clean_err}")
    
    # Create settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Seed default admin credentials
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('admin_username', 'admin')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('admin_password', 'invosync2026')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('settings_password', 'settings2026')")
    
    conn.commit()
    conn.close()
    
    start_excel_watcher()

def get_setting(key, default=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row['value']
    return default

def save_setting(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    conn.commit()
    conn.close()

def verify_password(stored_val, candidate_val, setting_key_to_upgrade=None):
    if not stored_val or not candidate_val:
        return False
    stored_str = str(stored_val).strip()
    candidate_str = str(candidate_val).strip()

    if stored_str.startswith("scrypt:") or stored_str.startswith("pbkdf2:") or stored_str.startswith("sha256$"):
        return check_password_hash(stored_str, candidate_str)

    # Plain text check & automatic migration to secure hash
    if stored_str == candidate_str:
        if setting_key_to_upgrade:
            try:
                new_hash = generate_password_hash(candidate_str)
                save_setting(setting_key_to_upgrade, new_hash)
                print(f"[SECURITY] Successfully upgraded setting '{setting_key_to_upgrade}' to secure password hash.")
            except Exception as ex:
                print(f"[SECURITY] Warning during hash upgrade: {ex}")
        return True
    return False

def get_documents(company=None, doc_type=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM documents"
    params = []
    
    conditions = []
    if company:
        conditions.append("LOWER(company) = LOWER(?)")
        params.append(company)
    if doc_type:
        conditions.append("LOWER(doc_type) = LOWER(?)")
        params.append(doc_type)
        
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    query += " ORDER BY id DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_document_by_no(company, doc_type, doc_no):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM documents WHERE company = ? AND doc_type = ? AND doc_no = ?",
        (company, doc_type, doc_no)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def add_document(data):
    company = data.get('company')
    doc_type = data.get('doc_type')
    
    if not company or not doc_type:
        return False
        
    # Unmark deleted document flag if user is explicitly re-adding/uploading it
    if data.get('doc_no'):
        unmark_deleted_document(company, doc_type, data.get('doc_no'))
        
    # Clean Challan No
    data['challan_no'] = clean_challan_no(data.get('challan_no'), data.get('doc_no'))

    # Clean date fields to remove time components
    for field in ['doc_date', 'delivery_date', 'mrn_date']:
        if field in data:
            data[field] = clean_date_string(data[field])
            
    # Clean and enforce E-way bill rules
    if doc_type == 'Invoice':
        eway_status = str(data.get('eway_bill', '')).strip()
        eway_no = str(data.get('eway_bill_no', '')).strip()
        
        # If user passed custom eway number in eway_bill field
        if eway_status and eway_status.upper() not in ['PENDING', 'N/A', 'DONE', 'NONE', 'NULL', '-']:
            if not eway_no:
                eway_no = eway_status
            eway_status = "DONE"
            
        try:
            amt = float(data.get('amount') or 0.0)
        except (ValueError, TypeError):
            amt = 0.0
            
        if eway_no and eway_no.upper() not in ['PENDING', 'N/A', 'DONE', 'NONE', 'NULL', '-']:
            data['eway_bill_no'] = eway_no
            data['eway_bill'] = "DONE"
        else:
            data['eway_bill_no'] = ""
            if amt < 50000:
                data['eway_bill'] = "N/A"
            else:
                data['eway_bill'] = "PENDING"
            
    check_excel_writable(company)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO documents (
                company, doc_type, doc_no, doc_date, invoice_no, challan_no,
                bill_to, po_wo_no, item_description, amount, eway_bill, eway_bill_no, asn_no,
                mode_of_transp, dock_code, delivery_date, delivery_site,
                mrn_status, mrn_date, mrn_no, remarks,
                deliver_qty, uom, unit_price, po_status, po_qty
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company,
            doc_type,
            data.get('doc_no'),
            data.get('doc_date'),
            data.get('invoice_no'),
            data.get('challan_no'),
            data.get('bill_to'),
            data.get('po_wo_no'),
            data.get('item_description'),
            data.get('amount'),
            data.get('eway_bill'),
            data.get('eway_bill_no'),
            data.get('asn_no'),
            data.get('mode_of_transp'),
            data.get('dock_code'),
            data.get('delivery_date'),
            data.get('delivery_site'),
            data.get('mrn_status', 'PENDING'),
            data.get('mrn_date'),
            data.get('mrn_no'),
            data.get('remarks'),
            data.get('deliver_qty'),
            data.get('uom'),
            data.get('unit_price'),
            data.get('po_status'),
            data.get('po_qty')
        ))
        conn.commit()
        success = True
    except Exception as e:
        print(f"DB Integrity/Save error: {e}")
        success = False
    finally:
        conn.close()
    
    if success:
        try:
            import gsheet
            threading.Thread(target=sync_to_excel, args=(company,), daemon=True).start()
            threading.Thread(target=gsheet.sync_to_google_sheet, args=(company,), daemon=True).start()
        except Exception as e:
            print(f"Error triggering background sync tasks in add_document: {e}")
    return success

def update_document(company, doc_type, doc_no, data):
    # Clean date fields to remove time components
    for field in ['doc_date', 'delivery_date', 'mrn_date']:
        if field in data:
            data[field] = clean_date_string(data[field])
            
    # Clean and enforce E-way bill rules
    if doc_type == 'Invoice':
        current_doc = get_document_by_no(company, doc_type, doc_no)
        current_amount = current_doc.get('amount', 0.0) if current_doc else 0.0
        current_eway = current_doc.get('eway_bill', 'PENDING') if current_doc else 'PENDING'
        current_eway_no = current_doc.get('eway_bill_no', '') if current_doc else ''
        
        amt = data.get('amount', current_amount)
        try:
            amt = float(amt or 0.0)
        except (ValueError, TypeError):
            amt = 0.0
            
        eway = str(data.get('eway_bill') if 'eway_bill' in data else current_eway_no or current_eway).strip()
        is_custom_eway = eway and eway.upper() not in ['PENDING', 'N/A', '']
        
        if is_custom_eway:
            data['eway_bill_no'] = eway
            data['eway_bill'] = "DONE"
        else:
            data['eway_bill_no'] = ""
            if amt < 50000:
                data['eway_bill'] = "N/A"
            else:
                data['eway_bill'] = "PENDING"
             
    check_excel_writable(company)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    fields = []
    values = []
    
    updatable_fields = [
        'doc_date', 'invoice_no', 'challan_no', 'bill_to', 'po_wo_no',
        'item_description', 'amount', 'eway_bill', 'eway_bill_no', 'asn_no', 'mode_of_transp',
        'dock_code', 'delivery_date', 'delivery_site', 'mrn_status',
        'mrn_date', 'mrn_no', 'remarks',
        'deliver_qty', 'uom', 'unit_price', 'po_status', 'po_qty'
    ]
    
    for f in updatable_fields:
        if f in data:
            fields.append(f"{f} = ?")
            values.append(data[f])
            
    if not fields:
        conn.close()
        return False
        
    values.extend([company, doc_type, doc_no])
    query = f"UPDATE documents SET {', '.join(fields)} WHERE company = ? AND doc_type = ? AND doc_no = ?"
    
    cursor.execute(query, tuple(values))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    
    if rows_affected > 0:
        try:
            import gsheet
            threading.Thread(target=sync_to_excel, args=(company,), daemon=True).start()
            threading.Thread(target=gsheet.sync_to_google_sheet, args=(company,), daemon=True).start()
        except Exception as e:
            print(f"Error triggering background sync tasks in update_document: {e}")
        return True
    return False

def is_document_deleted(company, doc_type, doc_no):
    if not company or not doc_type or not doc_no:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM deleted_documents WHERE LOWER(company) = LOWER(?) AND LOWER(doc_type) = LOWER(?) AND LOWER(doc_no) = LOWER(?)",
        (str(company).strip(), str(doc_type).strip(), str(doc_no).strip())
    )
    row = cursor.fetchone()
    conn.close()
    return row is not None

def unmark_deleted_document(company, doc_type, doc_no):
    if not company or not doc_type or not doc_no:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM deleted_documents WHERE LOWER(company) = LOWER(?) AND LOWER(doc_type) = LOWER(?) AND LOWER(doc_no) = LOWER(?)",
        (str(company).strip(), str(doc_type).strip(), str(doc_no).strip())
    )
    conn.commit()
    conn.close()

def delete_document(company, doc_type, doc_no):
    check_excel_writable(company)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Record in deleted_documents table to permanently block background sync resurrects
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO deleted_documents (company, doc_type, doc_no) VALUES (?, ?, ?)",
            (company, doc_type, doc_no)
        )
    except Exception as e:
        print(f"[DB Delete] Error adding to deleted_documents: {e}")

    cursor.execute(
        "DELETE FROM documents WHERE LOWER(company) = LOWER(?) AND LOWER(doc_type) = LOWER(?) AND LOWER(doc_no) = LOWER(?)",
        (company, doc_type, doc_no)
    )
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    
    if rows_affected > 0:
        try:
            import gsheet
            threading.Thread(target=sync_to_excel, args=(company,), daemon=True).start()
            threading.Thread(target=gsheet.sync_to_google_sheet, args=(company,), daemon=True).start()
        except Exception as e:
            print(f"Error triggering background sync tasks in delete_document: {e}")
        return True
    return False

def calculate_difference(del_qty_str, po_qty_str):
    """
    Computes difference between Deliver Qty and PO Qty line-by-line.
    Returns calculated values joined by newlines.
    """
    del_qty_str = str(del_qty_str or '').strip()
    po_qty_str = str(po_qty_str or '').strip()
    
    if not del_qty_str and not po_qty_str:
        return ""
        
    del_parts = [p.strip() for p in del_qty_str.split('\n')] if del_qty_str else []
    po_parts = [p.strip() for p in po_qty_str.split('\n')] if po_qty_str else []
    
    max_len = max(len(del_parts), len(po_parts))
    diff_parts = []
    
    for i in range(max_len):
        d_val = 0.0
        p_val = 0.0
        
        if i < len(del_parts) and del_parts[i]:
            try:
                d_val = float(del_parts[i].replace(',', '').strip())
            except ValueError:
                pass
        if i < len(po_parts) and po_parts[i]:
            try:
                p_val = float(po_parts[i].replace(',', '').strip())
            except ValueError:
                pass
                
        # Calculate Difference (Deliver Qty - PO Qty)
        diff = d_val - p_val
        # Format as integer if whole number, otherwise float
        diff_str = str(int(diff)) if diff.is_integer() else f"{diff:.2f}"
        diff_parts.append(diff_str)
        
    return "\n".join(diff_parts)

def doc_number_sort_key(doc):
    doc_no = str(doc.get('doc_no') or '').strip()
    match = re.search(r'^(.*?)(?:/|-|_|\b)(\d+)$', doc_no)
    if match:
        prefix = match.group(1)
        num = int(match.group(2))
        return (prefix.lower(), num, doc_no.lower())
    numbers = re.findall(r'\d+', doc_no)
    if numbers:
        last_num = int(numbers[-1])
        prefix = doc_no[:doc_no.rfind(numbers[-1])]
        return (prefix.lower(), last_num, doc_no.lower())
    return (doc_no.lower(), 0, doc_no.lower())

def calculate_overall_po_status(doc):
    po_status_str = str(doc.get('po_status') or '').strip()
    if not po_status_str:
        return 'Open'
    statuses = [s.strip().upper() for s in po_status_str.split('\n') if s.strip()]
    if not statuses:
        return 'Open'
    # 1. If EVEN ONE item is Open/Pending, Overall status is Open
    if any(s in ['OPEN', 'PENDING', ''] for s in statuses):
        return 'Open'
    # 2. If NO item is Open, but at least one item is Work Order, Overall status is Work Order
    if any(s in ['WORK ORDER', 'WORKORDER'] for s in statuses):
        return 'Work Order'
    # 3. If all items are Close/Closed, Overall status is Close
    if all(s in ['CLOSE', 'CLOSED'] for s in statuses):
        return 'Close'
    return 'Open'

def sync_to_excel(company=None, sync_main=True, sync_pending=True):
    """
    Syncs SQLite records. Overwrites the {Company}.xlsx file
    (with Invoices & Delivery Challans sheets)
    and {Company}_Pending_MRN.xlsx (with pending MRN list).
    """
    companies_to_sync = [company] if company else COMPANIES
    
    for comp in companies_to_sync:
        main_excel_path = get_company_excel_path(comp, 'main')
        pending_excel_path = get_company_excel_path(comp, 'pending')
        
        all_docs = get_documents(company=comp)
        invoices = [d for d in all_docs if d['doc_type'] == 'Invoice']
        challans = [d for d in all_docs if d['doc_type'] == 'Challan']
        
        # Column headers definitions (including MRN fields and Item Description for Invoices)
        cols_inv = [
            'S.No', 'Invoice No', 'Invoice Date', 'Challan No', 'Bill To',
            'PO/WO No', 'Item Description', 'Invoice Amt', 'Eway Bill', 'E way Bill no', 'ASN No', 'Mode of Transp',
            'Dock Code', 'Delivery Date', 'Delivery Site', 'MRN Status', 'MRN Date', 'MRN No', 'Remarks'
        ]
        
        cols_chal = [
            'S.No', 'Delivery Challan No', 'Item Description', 'Deliver Qty', 'UOM',
            'Unit Price', 'Delivery Date', 'Delivery Location', 'PO Status', 'Overall PO Status', 'PO Number',
            'PO Qty', 'Difference Between Delivery & PO Qty', 'Invoice Number', 
            'MRN Status', 'MRN Date', 'MRN No', 'Remarks'
        ]
        
        # 1. Update / Create Main Excel File
        if sync_main:
            import openpyxl
            from openpyxl.styles import Alignment
            
            os.makedirs(os.path.dirname(main_excel_path), exist_ok=True)
            
            # Load or create workbook
            if os.path.exists(main_excel_path):
                try:
                    wb = openpyxl.load_workbook(main_excel_path)
                except Exception as e:
                    print(f"Error loading existing workbook for {comp}, recreating: {e}")
                    wb = openpyxl.Workbook()
            else:
                wb = openpyxl.Workbook()
                
            # Ensure sheets exist and remove default 'Sheet'
            if 'Sheet' in wb.sheetnames and len(wb.sheetnames) > 1:
                wb.remove(wb['Sheet'])
                
            for sheet_name, cols, docs in [
                ('Invoices', cols_inv, invoices),
                ('Delivery Challans', cols_chal, challans)
            ]:
                # Ensure sheet exists
                if sheet_name not in wb.sheetnames:
                    ws = wb.create_sheet(title=sheet_name)
                else:
                    ws = wb[sheet_name]
                    
                # Clear all contents
                ws.delete_rows(1, ws.max_row + 1)
                ws.append(cols)
                
                # Sort SQLite docs ascending by document number (extracting trailing numeric digits)
                sorted_docs = sorted(docs, key=doc_number_sort_key)
                
                row_idx_counter = 1
                for doc in sorted_docs:
                    if sheet_name == 'Invoices':
                        row_data = []
                        for col in cols:
                            if col == 'S.No':
                                row_data.append(row_idx_counter)
                            elif col == 'Invoice No':
                                row_data.append(doc.get('doc_no', ''))
                            elif col == 'Invoice Date':
                                row_data.append(doc.get('doc_date', ''))
                            elif col == 'Challan No':
                                row_data.append(doc.get('challan_no', ''))
                            elif col == 'Bill To':
                                row_data.append(doc.get('bill_to', ''))
                            elif col == 'PO/WO No':
                                row_data.append(doc.get('po_wo_no', ''))
                            elif col == 'Item Description':
                                row_data.append(doc.get('item_description', ''))
                            elif col == 'Invoice Amt':
                                row_data.append(doc.get('amount', 0.0))
                            elif col == 'Eway Bill':
                                row_data.append(doc.get('eway_bill', ''))
                            elif col == 'E way Bill no':
                                row_data.append(doc.get('eway_bill_no', ''))
                            elif col == 'ASN No':
                                row_data.append(doc.get('asn_no', ''))
                            elif col == 'Mode of Transp':
                                row_data.append(doc.get('mode_of_transp', ''))
                            elif col == 'Dock Code':
                                row_data.append(doc.get('dock_code', ''))
                            elif col == 'Delivery Date':
                                row_data.append(doc.get('delivery_date', ''))
                            elif col == 'Delivery Site':
                                row_data.append(doc.get('delivery_site', ''))
                            elif col == 'MRN Status':
                                row_data.append(doc.get('mrn_status', 'PENDING'))
                            elif col == 'MRN Date':
                                row_data.append(doc.get('mrn_date', ''))
                            elif col == 'MRN No':
                                row_data.append(doc.get('mrn_no', ''))
                            elif col == 'Remarks':
                                row_data.append(doc.get('remarks', ''))
                            else:
                                row_data.append('')
                        ws.append(row_data)
                        row_idx_counter += 1
                    else:
                        # Delivery Challans: split multi-line values into separate rows
                        items = str(doc.get('item_description') or '').split('\n')
                        qtys = str(doc.get('deliver_qty') or '').split('\n')
                        uoms = str(doc.get('uom') or '').split('\n')
                        prices = str(doc.get('unit_price') or '').split('\n')
                        po_qtys = str(doc.get('po_qty') or '').split('\n')
                        po_statuses = str(doc.get('po_status') or '').split('\n')
                        
                        max_len = max(len(items), len(qtys), len(uoms), len(prices), len(po_qtys), len(po_statuses))
                        max_len = max(max_len, 1)
                        
                        items += [''] * (max_len - len(items))
                        qtys += [''] * (max_len - len(qtys))
                        uoms += [''] * (max_len - len(uoms))
                        prices += [''] * (max_len - len(prices))
                        po_qtys += [''] * (max_len - len(po_qtys))
                        po_statuses += [''] * (max_len - len(po_statuses))
                        
                        for i in range(max_len):
                            row_data = []
                            for col in cols:
                                if col == 'S.No':
                                    row_data.append(row_idx_counter)
                                elif col == 'Delivery Challan No':
                                    row_data.append(doc.get('doc_no', ''))
                                elif col == 'Item Description':
                                    row_data.append(items[i])
                                elif col == 'Deliver Qty':
                                    row_data.append(qtys[i])
                                elif col == 'UOM':
                                    row_data.append(uoms[i])
                                elif col == 'Unit Price':
                                    row_data.append(prices[i])
                                elif col == 'Delivery Date':
                                    row_data.append(doc.get('doc_date', ''))
                                elif col == 'Delivery Location':
                                    row_data.append(doc.get('delivery_site', ''))
                                elif col == 'PO Status':
                                    st = str(po_statuses[i] or '').strip()
                                    if not st:
                                        st = 'Open'
                                    elif st.upper() in ['CLOSE', 'CLOSED']:
                                        st = 'Close'
                                    elif st.upper() in ['WORK ORDER', 'WORKORDER']:
                                        st = 'Work Order'
                                    else:
                                        st = 'Open'
                                    row_data.append(st)
                                elif col == 'Overall PO Status':
                                    row_data.append(calculate_overall_po_status(doc))
                                elif col == 'PO Number':
                                    row_data.append(doc.get('po_wo_no', ''))
                                elif col == 'PO Qty':
                                    row_data.append(po_qtys[i])
                                elif col == 'Difference Between Delivery & PO Qty':
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
                                    row_data.append(diff_str)
                                elif col == 'Invoice Number':
                                    row_data.append(doc.get('invoice_no', ''))
                                elif col == 'MRN Status':
                                    row_data.append(doc.get('mrn_status', 'PENDING'))
                                elif col == 'MRN Date':
                                    row_data.append(doc.get('mrn_date', ''))
                                elif col == 'MRN No':
                                    row_data.append(doc.get('mrn_no', ''))
                                elif col == 'Remarks':
                                    row_data.append(doc.get('remarks', ''))
                                else:
                                    row_data.append('')
                            ws.append(row_data)
                            row_idx_counter += 1
                            
                # Formatting line wrap for cells with newlines
                for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
                    for cell in row:
                        if cell.value and isinstance(cell.value, str) and '\n' in cell.value:
                            cell.alignment = Alignment(wrap_text=True, vertical='top')
                            
                # Auto-fit column widths
                from openpyxl.utils import get_column_letter
                for col in ws.columns:
                    max_len = 0
                    for cell in col:
                        if cell.value is not None:
                            lines = str(cell.value).split('\n')
                            for line in lines:
                                if len(line) > max_len:
                                    max_len = len(line)
                    col_letter = get_column_letter(col[0].column)
                    ws.column_dimensions[col_letter].width = min(max(max_len + 4, 10), 100)
                    
            try:
                import tempfile
                import shutil
                temp_dir = os.path.dirname(os.path.abspath(__file__))
                fd, temp_path = tempfile.mkstemp(suffix='.xlsx', dir=temp_dir)
                os.close(fd)
                
                wb.save(temp_path)
                wb.close()
                
                # Atomic replacement
                shutil.move(temp_path, main_excel_path)
                last_written_mtime[main_excel_path] = os.path.getmtime(main_excel_path)
            except PermissionError as e:
                raise PermissionError(f"The Excel file '{os.path.basename(main_excel_path)}' is currently open or locked. Please close it in Microsoft Excel and try again.") from e
            except Exception as e:
                print(f"Error saving main excel for {comp}: {e}")
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                raise
                
        # 2. Generate Pending MRN Workbook
        if sync_pending:
            import openpyxl
            from openpyxl.styles import Alignment, Font, PatternFill
            from openpyxl.utils import get_column_letter
            
            wb_p = openpyxl.Workbook()
            ws_p = wb_p.active
            ws_p.title = "Pending MRNs"
            
            # Use same cols as Invoices
            cols_p = cols_inv
            ws_p.append(cols_p)
            
            # Formatting headers
            header_font = Font(name='Segoe UI', size=11, bold=True, color='FFFFFF')
            header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
            for col_idx in range(1, len(cols_p) + 1):
                cell = ws_p.cell(row=1, column=col_idx)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal='center', vertical='center')
            
            # Filter and sort pending invoices ascending by ID
            pending_invoices = [d for d in invoices if str(d.get('mrn_status', '')).upper() != 'DONE']
            sorted_pending = sorted(pending_invoices, key=lambda x: x['id'])
            
            row_idx_counter = 1
            for doc in sorted_pending:
                row_data = []
                for col in cols_p:
                    if col == 'S.No':
                        row_data.append(row_idx_counter)
                    elif col == 'Invoice No':
                        row_data.append(doc.get('doc_no', ''))
                    elif col == 'Invoice Date':
                        row_data.append(doc.get('doc_date', ''))
                    elif col == 'Challan No':
                        row_data.append(doc.get('challan_no', ''))
                    elif col == 'Bill To':
                        row_data.append(doc.get('bill_to', ''))
                    elif col == 'PO/WO No':
                        row_data.append(doc.get('po_wo_no', ''))
                    elif col == 'Item Description':
                        row_data.append(doc.get('item_description', ''))
                    elif col == 'Invoice Amt':
                        row_data.append(doc.get('amount', 0.0))
                    elif col == 'Eway Bill':
                        row_data.append(doc.get('eway_bill', ''))
                    elif col == 'E way Bill no':
                        row_data.append(doc.get('eway_bill_no', ''))
                    elif col == 'ASN No':
                        row_data.append(doc.get('asn_no', ''))
                    elif col == 'Mode of Transp':
                        row_data.append(doc.get('mode_of_transp', ''))
                    elif col == 'Dock Code':
                        row_data.append(doc.get('dock_code', ''))
                    elif col == 'Delivery Date':
                        row_data.append(doc.get('delivery_date', ''))
                    elif col == 'Delivery Site':
                        row_data.append(doc.get('delivery_site', ''))
                    elif col == 'MRN Status':
                        row_data.append(doc.get('mrn_status', 'PENDING'))
                    elif col == 'MRN Date':
                        row_data.append(doc.get('mrn_date', ''))
                    elif col == 'MRN No':
                        row_data.append(doc.get('mrn_no', ''))
                    elif col == 'Remarks':
                        row_data.append(doc.get('remarks', ''))
                    else:
                        row_data.append('')
                ws_p.append(row_data)
                row_idx_counter += 1
                
            # Formatting line wrap for cells with newlines & currency formats
            for row in ws_p.iter_rows(min_row=2, max_row=ws_p.max_row, min_col=1, max_col=ws_p.max_column):
                for cell in row:
                    if cell.column == 8: # Invoice Amt
                        cell.number_format = '₹#,##0.00'
                    if cell.value and isinstance(cell.value, str) and '\n' in cell.value:
                        cell.alignment = Alignment(wrap_text=True, vertical='top')
                        
            # Auto-fit column widths
            for col in ws_p.columns:
                max_len = 0
                for cell in col:
                    if cell.value is not None:
                        lines = str(cell.value).split('\n')
                        for line in lines:
                            if len(line) > max_len:
                                max_len = len(line)
                col_letter = get_column_letter(col[0].column)
                ws_p.column_dimensions[col_letter].width = min(max(max_len + 4, 10), 100)
                
            try:
                import tempfile
                import shutil
                temp_dir = os.path.dirname(os.path.abspath(__file__))
                fd, temp_path = tempfile.mkstemp(suffix='.xlsx', dir=temp_dir)
                os.close(fd)
                
                wb_p.save(temp_path)
                wb_p.close()
                
                shutil.move(temp_path, pending_excel_path)
                last_written_mtime[pending_excel_path] = os.path.getmtime(pending_excel_path)
            except PermissionError as e:
                raise PermissionError(f"The Pending MRN Excel file '{os.path.basename(pending_excel_path)}' is currently open or locked. Please close it in Microsoft Excel and try again.") from e
            except Exception as e:
                print(f"Error syncing pending MRNs excel for {comp}: {e}")
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                raise
    
def sync_from_excel():
    """
    On startup, if the SQLite DB is empty, this scans the excel storage folder
    and loads SK_Agro.xlsx, SK_Electricals.xlsx, and Triotech.xlsx.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT count(*) FROM documents")
    count = cursor.fetchone()[0]
    if count > 0:
        conn.close()
        return
        
    for comp in COMPANIES:
        main_excel_path = get_company_excel_path(comp, 'main')
        if not os.path.exists(main_excel_path):
            continue
            
        try:
            print(f"Seeding SQLite database from company workbook: {main_excel_path}")
            xls = pd.ExcelFile(main_excel_path)
            
            # Read Invoices Sheet
            if 'Invoices' in xls.sheet_names:
                df_inv = pd.read_excel(main_excel_path, sheet_name='Invoices')
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
                df_inv = df_inv.rename(columns=excel_to_db_inv)
                cols_to_insert = [v for v in excel_to_db_inv.values() if v in df_inv.columns]
                df_inv = df_inv[cols_to_insert]
                
                if 'doc_no' in df_inv.columns:
                    df_inv = df_inv.dropna(subset=['doc_no'])
                    for _, row in df_inv.iterrows():
                        row_dict = {k: (None if pd.isna(v) else v) for k, v in row.items()}
                        row_dict['company'] = comp
                        row_dict['doc_type'] = 'Invoice'
                        
                        if 'amount' in row_dict and row_dict['amount'] is not None:
                            try:
                                row_dict['amount'] = float(str(row_dict['amount']).replace(',', '').strip())
                            except ValueError:
                                row_dict['amount'] = 0.0
                        else:
                            row_dict['amount'] = 0.0
                                
                        # E-way bill rules
                        eway = str(row_dict.get('eway_bill_no') or row_dict.get('eway_bill') or '').strip()
                        is_custom_eway = eway and eway.upper() not in ['PENDING', 'N/A', '']
                        try:
                            amt = float(row_dict.get('amount') or 0.0)
                        except (ValueError, TypeError):
                            amt = 0.0
                        if is_custom_eway:
                            row_dict['eway_bill_no'] = eway
                            row_dict['eway_bill'] = "DONE"
                        else:
                            row_dict['eway_bill_no'] = ""
                            if amt < 50000:
                                row_dict['eway_bill'] = "N/A"
                            else:
                                row_dict['eway_bill'] = "PENDING"
                                
                        placeholders = ", ".join(["?"] * len(row_dict))
                        columns = ", ".join(row_dict.keys())
                        values = tuple(row_dict.values())
                        cursor.execute(f"INSERT OR IGNORE INTO documents ({columns}) VALUES ({placeholders})", values)
            
            # Read Delivery Challans Sheet (Group item-by-item rows back to single records)
            if 'Delivery Challans' in xls.sheet_names:
                df_chal = pd.read_excel(main_excel_path, sheet_name='Delivery Challans')
                excel_to_db_chal = {
                    'Delivery Challan No': 'doc_no',
                    'Item Description': 'item_description',
                    'Deliver Qty': 'deliver_qty',
                    'UOM': 'uom',
                    'Unit Price': 'unit_price',
                    'Delivery Date': 'delivery_date',
                    'Delivery Location': 'delivery_site',
                    'PO Status': 'po_status',
                    'PO Number': 'po_wo_no',
                    'PO Qty': 'po_qty',
                    'Invoice Number': 'invoice_no',
                    'MRN Status': 'mrn_status',
                    'MRN Date': 'mrn_date',
                    'MRN No': 'mrn_no',
                    'Remarks': 'remarks'
                }
                df_chal = df_chal.rename(columns=excel_to_db_chal)
                cols_to_insert = [v for v in excel_to_db_chal.values() if v in df_chal.columns]
                df_chal = df_chal[cols_to_insert]
                
                if 'doc_no' in df_chal.columns:
                    df_chal = df_chal.dropna(subset=['doc_no'])
                    
                    grouped_docs = {}
                    for _, row in df_chal.iterrows():
                        row_dict = {k: (None if pd.isna(v) else v) for k, v in row.items()}
                        doc_no = str(row_dict.get('doc_no', '')).strip()
                        if not doc_no:
                            continue
                        if doc_no not in grouped_docs:
                            grouped_docs[doc_no] = {
                                'doc_no': doc_no,
                                'doc_date': row_dict.get('delivery_date'),
                                'invoice_no': row_dict.get('invoice_no'),
                                'challan_no': doc_no,
                                'bill_to': row_dict.get('bill_to') or 'LARSEN & TOUBRO',
                                'po_wo_no': row_dict.get('po_wo_no'),
                                'delivery_site': row_dict.get('delivery_site'),
                                'po_status': row_dict.get('po_status'),
                                'mrn_status': row_dict.get('mrn_status') or 'PENDING',
                                'mrn_date': row_dict.get('mrn_date'),
                                'mrn_no': row_dict.get('mrn_no'),
                                'remarks': row_dict.get('remarks'),
                                '_items': [], '_qtys': [], '_uoms': [], '_prices': [], '_po_qtys': []
                            }
                        gd = grouped_docs[doc_no]
                        gd['_items'].append(str(row_dict.get('item_description') or '').strip())
                        gd['_qtys'].append(str(row_dict.get('deliver_qty') or '').strip())
                        gd['_uoms'].append(str(row_dict.get('uom') or '').strip())
                        gd['_prices'].append(str(row_dict.get('unit_price') or '').strip())
                        gd['_po_qtys'].append(str(row_dict.get('po_qty') or '').strip())
                        
                    for doc_no, gd in grouped_docs.items():
                        gd['item_description'] = "\n".join(gd['_items'])
                        gd['deliver_qty'] = "\n".join(gd['_qtys'])
                        gd['uom'] = "\n".join(gd['_uoms'])
                        gd['unit_price'] = "\n".join(gd['_prices'])
                        gd['po_qty'] = "\n".join(gd['_po_qtys'])
                        
                        for k in ['_items', '_qtys', '_uoms', '_prices', '_po_qtys']:
                            del gd[k]
                            
                        gd['company'] = comp
                        gd['doc_type'] = 'Challan'
                        gd['amount'] = 0.0
                        
                        # Clean fields
                        for f in ['deliver_qty', 'uom', 'unit_price', 'po_qty']:
                            if f in gd and gd[f] is not None:
                                gd[f] = str(gd[f])
                                
                        placeholders = ", ".join(["?"] * len(gd))
                        columns = ", ".join(gd.keys())
                        values = tuple(gd.values())
                        cursor.execute(f"INSERT OR IGNORE INTO documents ({columns}) VALUES ({placeholders})", values)
                        
            conn.commit()
        except Exception as e:
            print(f"Error seeding database from excel file {main_excel_path}: {e}")
            
    conn.close()

def check_invoice_sequence(company, doc_type, documents=None):
    if documents is None:
        documents = get_documents(company=company, doc_type=doc_type)
    if len(documents) < 2:
        return {"status": "ok", "missing_numbers": [], "pattern": ""}
    
    doc_nos = [doc['doc_no'] for doc in sorted(documents, key=lambda x: x['id'])]
    first_no = doc_nos[0]
    last_num_match = list(re.finditer(r'\d+', first_no))
    if not last_num_match:
        return {"status": "ok", "missing_numbers": [], "pattern": ""}
        
    last_match = last_num_match[-1]
    start_pos, end_pos = last_match.span()
    prefix = first_no[:start_pos]
    suffix = first_no[end_pos:]
    
    seq_nums = []
    for doc_no in doc_nos:
        if doc_no.startswith(prefix) and doc_no.endswith(suffix):
            middle_part = doc_no[start_pos:len(doc_no)-len(suffix)]
            if middle_part.isdigit():
                seq_nums.append(int(middle_part))
                
    if len(seq_nums) < 2:
        return {"status": "ok", "missing_numbers": [], "pattern": f"{prefix}{{num}}{suffix}"}
        
    seq_nums = sorted(list(set(seq_nums)))
    min_val = seq_nums[0]
    max_val = seq_nums[-1]
    
    full_range = set(range(min_val, max_val + 1))
    missing = sorted(list(full_range - set(seq_nums)))
    missing_formatted = [f"{prefix}{num}{suffix}" for num in missing]
    
    return {
        "status": "warning" if missing_formatted else "ok",
        "missing_numbers": missing_formatted,
        "pattern": f"{prefix}{{num}}{suffix}"
    }

def check_missing_mrn(company=None, doc_type=None, documents=None):
    if documents is None:
        documents = get_documents(company=company, doc_type=doc_type)
    missing_mrn_list = []
    for doc in documents:
        status = str(doc.get('mrn_status', '')).upper()
        if status != 'DONE':
            missing_mrn_list.append(doc)
    return missing_mrn_list

def sync_excel_to_db(company):
    main_excel_path = get_company_excel_path(company, 'main')
    if not os.path.exists(main_excel_path):
        return
        
    try:
        xls = pd.ExcelFile(main_excel_path)
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete existing documents for this company from DB
        cursor.execute("DELETE FROM documents WHERE company = ?", (company,))
        
        # Read Invoices Sheet
        if 'Invoices' in xls.sheet_names:
            df_inv = pd.read_excel(main_excel_path, sheet_name='Invoices')
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
            df_inv = df_inv.rename(columns=excel_to_db_inv)
            cols_to_insert = [v for v in excel_to_db_inv.values() if v in df_inv.columns]
            df_inv = df_inv[cols_to_insert]
            
            if 'doc_no' in df_inv.columns:
                df_inv = df_inv.dropna(subset=['doc_no'])
                for _, row in df_inv.iterrows():
                    row_dict = {k: (None if pd.isna(v) else v) for k, v in row.items()}
                    row_dict['company'] = company
                    row_dict['doc_type'] = 'Invoice'
                    
                    if 'amount' in row_dict and row_dict['amount'] is not None:
                        try:
                            row_dict['amount'] = float(str(row_dict['amount']).replace(',', '').strip())
                        except ValueError:
                            row_dict['amount'] = 0.0
                    else:
                        row_dict['amount'] = 0.0
                            
                    # E-way bill rules
                    eway = str(row_dict.get('eway_bill_no') or row_dict.get('eway_bill') or '').strip()
                    is_custom_eway = eway and eway.upper() not in ['PENDING', 'N/A', '']
                    try:
                        amt = float(row_dict.get('amount') or 0.0)
                    except (ValueError, TypeError):
                        amt = 0.0
                    if is_custom_eway:
                        row_dict['eway_bill_no'] = eway
                        row_dict['eway_bill'] = "DONE"
                    else:
                        row_dict['eway_bill_no'] = ""
                        if amt < 50000:
                            row_dict['eway_bill'] = "N/A"
                        else:
                            row_dict['eway_bill'] = "PENDING"
                            
                    placeholders = ", ".join(["?"] * len(row_dict))
                    columns = ", ".join(row_dict.keys())
                    values = tuple(row_dict.values())
                    cursor.execute(
                        f"INSERT INTO documents ({columns}) VALUES ({placeholders}) "
                        f"ON CONFLICT(company, doc_type, doc_no) DO UPDATE SET "
                        f"mrn_status=excluded.mrn_status, mrn_no=excluded.mrn_no, mrn_date=excluded.mrn_date, "
                        f"remarks=excluded.remarks, eway_bill=excluded.eway_bill, eway_bill_no=excluded.eway_bill_no",
                        values
                    )
        
        # Read Delivery Challans Sheet (Group itemized rows back to single records)
        if 'Delivery Challans' in xls.sheet_names:
            df_chal = pd.read_excel(main_excel_path, sheet_name='Delivery Challans')
            excel_to_db_chal = {
                'Delivery Challan No': 'doc_no',
                'Item Description': 'item_description',
                'Deliver Qty': 'deliver_qty',
                'UOM': 'uom',
                'Unit Price': 'unit_price',
                'Delivery Date': 'delivery_date',
                'Delivery Location': 'delivery_site',
                'PO Status': 'po_status',
                'PO Number': 'po_wo_no',
                'PO Qty': 'po_qty',
                'Invoice Number': 'invoice_no',
                'MRN Status': 'mrn_status',
                'MRN Date': 'mrn_date',
                'MRN No': 'mrn_no',
                'Remarks': 'remarks'
            }
            df_chal = df_chal.rename(columns=excel_to_db_chal)
            cols_to_insert = [v for v in excel_to_db_chal.values() if v in df_chal.columns]
            df_chal = df_chal[cols_to_insert]
            
            if 'doc_no' in df_chal.columns:
                df_chal = df_chal.dropna(subset=['doc_no'])
                
                grouped_docs = {}
                for _, row in df_chal.iterrows():
                    row_dict = {k: (None if pd.isna(v) else v) for k, v in row.items()}
                    doc_no = str(row_dict.get('doc_no', '')).strip()
                    if not doc_no:
                        continue
                    if doc_no not in grouped_docs:
                        grouped_docs[doc_no] = {
                            'doc_no': doc_no,
                            'doc_date': row_dict.get('delivery_date'),
                            'invoice_no': row_dict.get('invoice_no'),
                            'challan_no': doc_no,
                            'bill_to': row_dict.get('bill_to') or 'LARSEN & TOUBRO',
                            'po_wo_no': row_dict.get('po_wo_no'),
                            'delivery_site': row_dict.get('delivery_site'),
                            'mrn_status': row_dict.get('mrn_status') or 'PENDING',
                            'mrn_date': row_dict.get('mrn_date'),
                            'mrn_no': row_dict.get('mrn_no'),
                            'remarks': row_dict.get('remarks'),
                            '_items': [], '_qtys': [], '_uoms': [], '_prices': [], '_po_qtys': [], '_po_statuses': []
                        }
                    gd = grouped_docs[doc_no]
                    gd['_items'].append(str(row_dict.get('item_description') or '').strip())
                    gd['_qtys'].append(str(row_dict.get('deliver_qty') or '').strip())
                    gd['_uoms'].append(str(row_dict.get('uom') or '').strip())
                    gd['_prices'].append(str(row_dict.get('unit_price') or '').strip())
                    gd['_po_qtys'].append(str(row_dict.get('po_qty') or '').strip())
                    gd['_po_statuses'].append(str(row_dict.get('po_status') or '').strip())
                    
                for doc_no, gd in grouped_docs.items():
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
                             
                    placeholders = ", ".join(["?"] * len(gd))
                    columns = ", ".join(gd.keys())
                    values = tuple(gd.values())
                    cursor.execute(
                        f"INSERT INTO documents ({columns}) VALUES ({placeholders}) "
                        f"ON CONFLICT(company, doc_type, doc_no) DO UPDATE SET "
                        f"mrn_status=excluded.mrn_status, mrn_no=excluded.mrn_no, mrn_date=excluded.mrn_date, "
                        f"remarks=excluded.remarks, po_status=excluded.po_status",
                        values
                    )
                    
        conn.commit()
        conn.close()
        print(f"[Watcher] Successfully synced Excel changes to database for {company}")
    except Exception as e:
        print(f"[Watcher] Error syncing Excel changes to database for {company}: {e}")

# Lock to prevent concurrent file-to-db and db-to-file sync conflicts
sync_lock = threading.Lock()
last_known_mtime = {}

def start_excel_watcher():
    def watcher_thread():
        # Perform initial sync on startup to capture any offline edits
        print("[Watcher] Performing initial database sync from Excel files...")
        with sync_lock:
            for comp in COMPANIES:
                try:
                    sync_excel_to_db(comp)
                except Exception as e:
                    print(f"[Watcher] Error in initial startup sync for {comp}: {e}")
                    
        # Populate initial mtimes
        for comp in COMPANIES:
            main_path = get_company_excel_path(comp, 'main')
            if os.path.exists(main_path):
                last_known_mtime[main_path] = os.path.getmtime(main_path)
                
        # Google Sheet polling times tracking
        last_gsheet_poll = {comp: 0 for comp in COMPANIES}
                
        # Watcher loop
        while True:
            time.sleep(2.0)
            now = time.time()
            
            # --- Google Sheets Periodic Sync Check (runs every 30 seconds) ---
            for comp in COMPANIES:
                sync_url = get_setting(f"gsheet_sync_url_{comp.lower().replace(' ', '_')}")
                if sync_url and (now - last_gsheet_poll[comp] > 90.0):
                    last_gsheet_poll[comp] = now
                    try:
                        import gsheet
                        # Run Google Sheet pull in a background thread to prevent blocking
                        threading.Thread(target=gsheet.sync_from_google_sheet, args=(comp,), daemon=True).start()
                    except Exception as ex:
                        print(f"[Watcher] Failed to trigger Google Sheet pull for {comp}: {ex}")
            
            # --- Local Excel File Watcher ---
            try:
                for comp in COMPANIES:
                    main_path = get_company_excel_path(comp, 'main')
                    if os.path.exists(main_path):
                        mtime = os.path.getmtime(main_path)
                        
                        # If file is new to watcher, just track it
                        if main_path not in last_known_mtime:
                            last_known_mtime[main_path] = mtime
                            continue
                            
                        if mtime != last_known_mtime[main_path]:
                            last_known_mtime[main_path] = mtime
                            
                            # Check if modification was from the app itself
                            expected_mtime = last_written_mtime.get(main_path, 0)
                            if abs(mtime - expected_mtime) < 2.0:
                                continue
                                
                            print(f"[Watcher] Manual Excel modification detected: {main_path}. Syncing...")
                            with sync_lock:
                                try:
                                    # 1. Sync Excel to SQLite DB
                                    sync_excel_to_db(comp)
                                    # 2. Regenerate pending list and re-format Excel
                                    sync_to_excel(comp, sync_main=False, sync_pending=True)
                                    # 3. Push manual edits to Google Sheets to keep them in sync
                                    try:
                                        import gsheet
                                        gsheet.sync_to_google_sheet(comp)
                                    except Exception as gs_ex:
                                        print(f"[Watcher] Google Sheets push sync failed for {comp}: {gs_ex}")
                                except Exception as ex:
                                    print(f"[Watcher] Sync failed for {comp}: {ex}")
            except Exception as e:
                print(f"[Watcher] Error in loop: {e}")
                
    t = threading.Thread(target=watcher_thread, daemon=True)
    t.start()
    print("[Watcher] Excel file watcher thread successfully started.")
