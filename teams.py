import requests
import json

def send_teams_notification(webhook_url, event_type, data):
    """
    Sends a formatted MessageCard to a Microsoft Teams Incoming Webhook.
    """
    if not webhook_url:
        print("MS Teams Webhook URL not configured. Skipping notification.")
        return False
        
    headers = {
        "Content-Type": "application/json"
    }
    
    # Base structure of O365 MessageCard
    card = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "7B83EB", # Sleek modern lavender/blue
        "summary": "Invoice System Notification"
    }
    
    if event_type == "new_invoice":
        card["title"] = "📄 New Invoice Processed"
        # Format currency nicely
        amt = data.get("invoice_amt", 0.0)
        formatted_amt = f"₹{amt:,.2f}" if amt else "N/A"
        
        card["sections"] = [{
            "activityTitle": f"Invoice **{data.get('invoice_no')}** has been added to the system.",
            "activitySubtitle": f"Processed at {data.get('processed_time', '')}",
            "facts": [
                {"name": "Invoice No", "value": str(data.get("invoice_no", "N/A"))},
                {"name": "Invoice Date", "value": str(data.get("invoice_date", "N/A"))},
                {"name": "Bill To", "value": str(data.get("bill_to", "N/A"))},
                {"name": "Item Description", "value": str(data.get("item_description", "N/A"))},
                {"name": "Amount", "value": formatted_amt},
                {"name": "PO/WO No", "value": str(data.get("po_wo_no", "N/A"))},
                {"name": "MRN Status", "value": str(data.get("mrn_status", "PENDING"))}
            ],
            "markdown": True
        }]
        
    elif event_type == "sequence_gap":
        card["themeColor"] = "FF8C00" # Warning Orange
        card["title"] = "⚠️ Missing Invoice Sequence Gap Detected"
        missing_list = data.get("missing_numbers", [])
        missing_str = ", ".join(missing_list) if missing_list else "None"
        
        card["sections"] = [{
            "activityTitle": "Sequence gap detected in invoice numbering.",
            "facts": [
                {"name": "Detected Pattern", "value": str(data.get("pattern", "N/A"))},
                {"name": "Missing Invoice Numbers", "value": f"**{missing_str}**"}
            ],
            "markdown": True
        }]
        
    elif event_type == "missing_mrn":
        card["themeColor"] = "E81123" # Alert Red
        card["title"] = "⏳ Pending MRN Details Alert"
        invoice_no = data.get("invoice_no", "N/A")
        
        card["sections"] = [{
            "activityTitle": f"Invoice **{invoice_no}** is missing MRN details.",
            "facts": [
                {"name": "Invoice No", "value": str(invoice_no)},
                {"name": "Bill To", "value": str(data.get("bill_to", "N/A"))},
                {"name": "MRN Status", "value": "**PENDING**"},
                {"name": "Remarks", "value": str(data.get("remarks", "None"))}
            ],
            "markdown": True
        }]
        
    elif event_type == "test":
        card["title"] = "🔔 MS Teams Integration Test"
        card["sections"] = [{
            "activityTitle": "Connection from Invoice Extractor Application is successful!",
            "text": "This is a test notification confirming that the webhook integration is configured properly.",
            "markdown": True
        }]
        
    else:
        card["title"] = "System Notification"
        card["sections"] = [{
            "activityTitle": str(data.get("message", "No description provided.")),
            "markdown": True
        }]

    try:
        response = requests.post(webhook_url, headers=headers, data=json.dumps(card), timeout=10)
        if response.status_code in [200, 201, 202]:
            return True
        else:
            print(f"Failed to send Teams notification. Status code: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        print(f"Exception while sending Teams notification: {e}")
        return False
