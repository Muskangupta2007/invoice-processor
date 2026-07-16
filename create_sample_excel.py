import pandas as pd
import os

EXCEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "invoices.xlsx")

# Sample row from the user's screenshot
sample_data = {
    'S.No': [1],
    'Invoice No': ['TTE/26-27/1'],
    'Invoice Date': ['01 April 2026'],
    'Challan No': ['DIRECT INVOICE'],
    'Bill To': ['LARSEN & TOUBRO'],
    'PO/WO No': ['LE/LE20M065/PO/D/26/000716'],
    'Item Description': ['Paint'],
    'Invoice Amt': [185614.0],
    'Eway Bill': ['PENDING'],
    'ASN No': ['ASN/26/000797'],
    'Mode of Transp': ['Tempo'],
    'Dock Code': [''],
    'Delivery Date': ['01 April 2026'],
    'Delivery Site': ['C6-SECTION 1'],
    'MRN Status': ['DONE'],
    'MRN Date': ['05 June 2026'],
    'MRN No': ['LE/SZ000010/FP/26/INR/0383567'],
    'Remarks': ['Initial sample row imported from Excel template.']
}

df = pd.DataFrame(sample_data)

try:
    df.to_excel(EXCEL_PATH, index=False)
    print(f"Sample Excel ledger created successfully at: {EXCEL_PATH}")
except Exception as e:
    print(f"Failed to create Excel file: {e}")
