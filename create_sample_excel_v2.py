import pandas as pd
import os
import openpyxl

COMPANIES = ['SK Agro', 'SK Electricals', 'Triotech']

def create_sample_files():
    directory = os.path.dirname(os.path.abspath(__file__))
    
    def calculate_difference(del_qty_str, po_qty_str):
        del_parts = str(del_qty_str).split('\n') if del_qty_str else []
        po_parts = str(po_qty_str).split('\n') if po_qty_str else []
        max_len = max(len(del_parts), len(po_parts))
        diffs = []
        for i in range(max_len):
            d = float(del_parts[i]) if i < len(del_parts) and del_parts[i] else 0.0
            p = float(po_parts[i]) if i < len(po_parts) and po_parts[i] else 0.0
            diffs.append(str(int(d - p) if (d - p).is_integer() else (d - p)))
        return "\n".join(diffs)

    # 1. SK Agro Sample Data
    agro_path = os.path.join(directory, "SK_Agro.xlsx")
    with pd.ExcelWriter(agro_path, engine='openpyxl') as writer:
        pd.DataFrame([
            {
                'S.No': 1,
                'Invoice No': 'SKA/26-27/001',
                'Invoice Date': '01 April 2026',
                'Challan No': 'DIRECT INVOICE',
                'Bill To': 'LARSEN & TOUBRO',
                'PO/WO No': 'LE/LE20M065/PO/D/26/000716',
                'Invoice Amt': 185614.0,
                'Eway Bill': 'PENDING',  # REQUIRES E-Way Bill (>50k, PENDING)
                'ASN No': 'ASN/26/000797',
                'Mode of Transp': 'Tempo',
                'Dock Code': 'D-01',
                'Delivery Date': '01 April 2026',
                'Delivery Site': 'C6-SECTION 1',
                'MRN Status': 'DONE',
                'MRN Date': '05 June 2026',
                'MRN No': 'LE/SZ000010/FP/26/INR/0383567',
                'Remarks': 'Initial sample row.'
            },
            {
                'S.No': 2,
                'Invoice No': 'SKA/26-27/003',
                'Invoice Date': '02 April 2026',
                'Challan No': 'DIRECT INVOICE',
                'Bill To': 'LARSEN & TOUBRO',
                'PO/WO No': 'LE/LE20M065/PO/D/26/000716',
                'Invoice Amt': 35000.0,
                'Eway Bill': 'PENDING',  # Does NOT require E-Way bill (<=50k)
                'ASN No': 'ASN/26/000797',
                'Mode of Transp': 'Tempo',
                'Dock Code': 'D-01',
                'Delivery Date': '02 April 2026',
                'Delivery Site': 'C6-SECTION 1',
                'MRN Status': 'PENDING',
                'MRN Date': '',
                'MRN No': '',
                'Remarks': 'Under value limit.'
            },
            {
                'S.No': 3,
                'Invoice No': 'SKA/26-27/004',
                'Invoice Date': '03 April 2026',
                'Challan No': 'DIRECT INVOICE',
                'Bill To': 'LARSEN & TOUBRO',
                'PO/WO No': 'LE/LE20M065/PO/D/26/000716',
                'Invoice Amt': 75000.0,
                'Eway Bill': 'EW-12345',  # Already generated (Not PENDING)
                'ASN No': 'ASN/26/000797',
                'Mode of Transp': 'Tempo',
                'Dock Code': 'D-01',
                'Delivery Date': '03 April 2026',
                'Delivery Site': 'C6-SECTION 1',
                'MRN Status': 'DONE',
                'MRN Date': '06 June 2026',
                'MRN No': 'LE/SZ000010/FP/26/INR/0383568',
                'Remarks': 'E-way bill exists.'
            }
        ]).to_excel(writer, sheet_name='Invoices', index=False)
        
        del_qty = "10\n20\n30"
        po_qty = "12\n18\n30"
        pd.DataFrame([{
            'S.No': 1,
            'Delivery Challan No': 'SKA-DC/26-27/001',
            'Item Description': 'Fertilizers\nSeeds\nOrganic Soil',
            'Deliver Qty': del_qty,
            'UOM': 'Bags\nBags\nBags',
            'Unit Price': '500\n1000\n200',
            'Delivery Date': '02 April 2026',
            'Delivery Location': 'C6-SECTION 2',
            'PO Status': 'OPEN',  # PENDING PO
            'PO Number': 'LE/LE20M065/PO/D/26/000716',
            'PO Qty': po_qty,
            'Difference Between Delivery & PO Qty': calculate_difference(del_qty, po_qty),
            'Invoice Number': 'SKA/26-27/002',
            'MRN Status': 'PENDING',
            'MRN Date': '',
            'MRN No': '',
            'Remarks': 'Pending MRN registration.'
        }]).to_excel(writer, sheet_name='Delivery Challans', index=False)
        
    # Generate Pending file for SK Agro
    agro_pending_path = os.path.join(directory, "SK_Agro_Pending_MRN.xlsx")
    with pd.ExcelWriter(agro_pending_path, engine='openpyxl') as writer:
        pd.DataFrame([{
            'Type': 'Delivery Challan',
            'Doc No': 'SKA-DC/26-27/001',
            'Doc Date': '02 April 2026',
            'Bill To': 'LARSEN & TOUBRO',
            'PO/WO No': 'LE/LE20M065/PO/D/26/000716',
            'Amount': 0.0,
            'MRN Status': 'PENDING',
            'MRN Date': '',
            'MRN No': '',
            'Remarks': 'Pending MRN registration.'
        }]).to_excel(writer, sheet_name='Pending MRNs', index=False)
        
    # 2. SK Electricals Sample Data
    elec_path = os.path.join(directory, "SK_Electricals.xlsx")
    with pd.ExcelWriter(elec_path, engine='openpyxl') as writer:
        pd.DataFrame([{
            'S.No': 1,
            'Invoice No': 'SKE/26-27/001',
            'Invoice Date': '10 April 2026',
            'Challan No': 'DIRECT INVOICE',
            'Bill To': 'TATA PROJECTS',
            'PO/WO No': 'TP/ELECT/2026/089',
            'Invoice Amt': 89200.0,
            'Eway Bill': 'PENDING',  # REQUIRES E-Way Bill (>50k, PENDING)
            'ASN No': 'ASN/26/000840',
            'Mode of Transp': 'Tempo',
            'Dock Code': 'E-03',
            'Delivery Date': '10 April 2026',
            'Delivery Site': 'ZONE-3',
            'MRN Status': 'PENDING',
            'MRN Date': '',
            'MRN No': '',
            'Remarks': 'Awaiting receipt.'
        }]).to_excel(writer, sheet_name='Invoices', index=False)
        
        pd.DataFrame(columns=[
            'S.No', 'Delivery Challan No', 'Item Description', 'Deliver Qty', 'UOM',
            'Unit Price', 'Delivery Date', 'Delivery Location', 'PO Status', 'PO Number',
            'PO Qty', 'Difference Between Delivery & PO Qty', 'Invoice Number',
            'MRN Status', 'MRN Date', 'MRN No', 'Remarks'
        ]).to_excel(writer, sheet_name='Delivery Challans', index=False)

    # Generate Pending file for SK Electricals
    elec_pending_path = os.path.join(directory, "SK_Electricals_Pending_MRN.xlsx")
    with pd.ExcelWriter(elec_pending_path, engine='openpyxl') as writer:
        pd.DataFrame([{
            'Type': 'Invoice',
            'Doc No': 'SKE/26-27/001',
            'Doc Date': '10 April 2026',
            'Bill To': 'TATA PROJECTS',
            'PO/WO No': 'TP/ELECT/2026/089',
            'Amount': 89200.0,
            'MRN Status': 'PENDING',
            'MRN Date': '',
            'MRN No': '',
            'Remarks': 'Awaiting receipt.'
        }]).to_excel(writer, sheet_name='Pending MRNs', index=False)

    # 3. Triotech Sample Data
    trio_path = os.path.join(directory, "Triotech.xlsx")
    with pd.ExcelWriter(trio_path, engine='openpyxl') as writer:
        pd.DataFrame([{
            'S.No': 1,
            'Invoice No': 'TT/26-27/001',
            'Invoice Date': '15 April 2026',
            'Challan No': 'DIRECT INVOICE',
            'Bill To': 'RELIANCE INDUSTRIES',
            'PO/WO No': 'RIL/TECH/26/0045',
            'Invoice Amt': 245000.0,
            'Eway Bill': 'EW-908023',  # Already generated (Not PENDING)
            'ASN No': 'ASN/26/000910',
            'Mode of Transp': 'Truck',
            'Dock Code': 'T-01',
            'Delivery Date': '16 April 2026',
            'Delivery Site': 'JAMNAGAR',
            'MRN Status': 'DONE',
            'MRN Date': '20 May 2026',
            'MRN No': 'RIL/MRN/2026-902',
            'Remarks': 'Delivered successfully.'
        }]).to_excel(writer, sheet_name='Invoices', index=False)
        
        pd.DataFrame(columns=[
            'S.No', 'Delivery Challan No', 'Item Description', 'Deliver Qty', 'UOM',
            'Unit Price', 'Delivery Date', 'Delivery Location', 'PO Status', 'PO Number',
            'PO Qty', 'Difference Between Delivery & PO Qty', 'Invoice Number',
            'MRN Status', 'MRN Date', 'MRN No', 'Remarks'
        ]).to_excel(writer, sheet_name='Delivery Challans', index=False)

    # Generate Pending file for Triotech
    trio_pending_path = os.path.join(directory, "Triotech_Pending_MRN.xlsx")
    with pd.ExcelWriter(trio_pending_path, engine='openpyxl') as writer:
        pd.DataFrame(columns=[
            'Type', 'Doc No', 'Doc Date', 'Bill To', 'PO/WO No', 'Amount',
            'MRN Status', 'MRN Date', 'MRN No', 'Remarks'
        ]).to_excel(writer, sheet_name='Pending MRNs', index=False)
        
    print("Multi-company sample workbooks with Eway testing columns generated!")

if __name__ == '__main__':
    create_sample_files()
