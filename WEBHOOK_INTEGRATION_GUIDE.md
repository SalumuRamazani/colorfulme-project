# Webhook Integration Guide - ReceiptMake

## Overview

ReceiptMake's webhook integration allows you to automatically receive receipt data in real-time when receipts are generated. This enables you to:

- Store receipt data in your own systems
- Trigger automated workflows
- Send notifications
- Integrate with third-party services
- Build custom analytics

## Setting Up a Webhook

### 1. Navigate to Webhook Integrations

From your dashboard, click on "Webhook Integrations" to access the webhook management page.

### 2. Add a New Webhook

Click "Add Webhook" and provide:

- **Integration Name** (required): A friendly name to identify this webhook
- **Webhook Endpoint** (required): The URL where receipt data should be sent
- **Access Token** (optional): Bearer token for authentication

### 3. Configure Your Endpoint

Your webhook endpoint must:
- Accept POST requests
- Accept JSON payloads
- Return a 2xx status code on success
- Respond within 10 seconds

## Webhook Payload Format

When a receipt is generated, ReceiptMake will send a POST request to your configured endpoint with the following JSON structure:

```json
{
  "user_id": "user_abc123",
  "user_email": "user@example.com",
  "timestamp": "2025-10-22T20:30:00.000Z",
  "receipt_data": {
    "businessName": "My Business",
    "businessAddress": "123 Main St",
    "phoneNumber": "(555) 123-4567",
    "dateTime": "10/22/2025, 8:30:00 PM",
    "logoUrl": "data:image/png;base64,...",
    "logoSize": 100,
    "currencyFormat": "$X",
    "font": "Font 1",
    "textColor": "#000000",
    "showReceiptBg": true,
    "items": [
      {
        "quantity": 2,
        "name": "Product Name",
        "price": 19.99
      }
    ],
    "taxRate": 8.5,
    "subtotal": 39.98,
    "tax": 3.40,
    "total": 43.38,
    "customFields": [
      {
        "label": "Server",
        "value": "John",
        "column": 1
      },
      {
        "label": "Table",
        "value": "12",
        "column": 1
      }
    ],
    "paymentFields": [
      {
        "label": "Cash",
        "value": "$50.00"
      },
      {
        "label": "Change",
        "value": "$6.62"
      }
    ],
    "customMessage": "Thank you for your business!",
    "barcodeEnabled": true
  }
}
```

## Authentication

If you provide an Access Token when creating your webhook, it will be included in the request headers as:

```
Authorization: Bearer YOUR_ACCESS_TOKEN
```

Verify this token on your endpoint to ensure requests are coming from ReceiptMake.

## Example Webhook Endpoint Implementations

### Node.js (Express)

```javascript
const express = require('express');
const app = express();

app.use(express.json());

app.post('/webhook', (req, res) => {
  // Verify authorization token
  const authHeader = req.headers.authorization;
  if (authHeader !== 'Bearer YOUR_SECRET_TOKEN') {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  // Extract receipt data
  const { user_id, user_email, receipt_data, timestamp } = req.body;

  // Process the receipt data
  console.log(`Received receipt from ${user_email}`);
  console.log(`Total: ${receipt_data.total}`);
  console.log(`Items: ${receipt_data.items.length}`);

  // Store in database, send notification, etc.
  // ... your custom logic here ...

  // Return success response
  res.status(200).json({ success: true });
});

app.listen(3000, () => {
  console.log('Webhook server running on port 3000');
});
```

### Python (Flask)

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    # Verify authorization token
    auth_header = request.headers.get('Authorization')
    if auth_header != 'Bearer YOUR_SECRET_TOKEN':
        return jsonify({'error': 'Unauthorized'}), 401

    # Extract receipt data
    data = request.get_json()
    user_email = data.get('user_email')
    receipt_data = data.get('receipt_data')
    
    # Process the receipt data
    print(f"Received receipt from {user_email}")
    print(f"Total: {receipt_data['total']}")
    print(f"Items: {len(receipt_data['items'])}")
    
    # Store in database, send notification, etc.
    # ... your custom logic here ...
    
    # Return success response
    return jsonify({'success': True}), 200

if __name__ == '__main__':
    app.run(port=3000)
```

### Testing Your Webhook

You can use services like:
- **webhook.site** - Generate a temporary webhook URL for testing
- **ngrok** - Expose your local server to the internet
- **RequestBin** - Capture and inspect HTTP requests

Example using webhook.site:
1. Go to https://webhook.site
2. Copy the unique URL provided
3. Add it as your webhook endpoint in ReceiptMake
4. Generate a test receipt
5. View the incoming request on webhook.site

## Webhook Management

### Enable/Disable Webhooks

Click the toggle button on any webhook to temporarily enable or disable it without deleting the configuration.

### Delete Webhooks

Click the trash icon to permanently remove a webhook integration.

### View Webhook History

Each webhook displays:
- Creation date
- Last triggered timestamp
- Current status (Active/Inactive)

## Troubleshooting

### Webhook Not Firing

1. Ensure the webhook is marked as "Active"
2. Verify the endpoint URL is correct and accessible
3. Check that your server is responding within 10 seconds
4. Ensure your server is returning a 2xx status code

### Authentication Errors

1. Verify the Access Token matches on both sides
2. Check that the Authorization header is being sent correctly
3. Ensure your endpoint is checking for `Bearer YOUR_TOKEN` format

### Timeout Issues

If your webhook processing takes longer than 10 seconds:
1. Implement async processing
2. Return 200 immediately and process in background
3. Use a queue system for heavy operations

## Best Practices

1. **Always validate incoming data** - Don't trust the payload blindly
2. **Use HTTPS endpoints** - Encrypt data in transit
3. **Implement retry logic** - Handle temporary failures gracefully
4. **Log webhook events** - Keep audit trails for debugging
5. **Monitor webhook health** - Set up alerts for failures
6. **Use authentication** - Always set an Access Token
7. **Process asynchronously** - Return 200 quickly, process in background
8. **Handle duplicates** - Use timestamps or IDs to detect duplicate events

## Security Considerations

1. **Access Tokens**: Store securely, never commit to version control
2. **IP Whitelisting**: Consider restricting webhook access to ReceiptMake IPs
3. **Rate Limiting**: Implement rate limiting on your webhook endpoint
4. **Data Validation**: Validate all incoming fields before processing
5. **HTTPS Only**: Never use HTTP endpoints in production

## Rate Limits

- Maximum 100 webhook triggers per minute per user
- Maximum 10 active webhooks per user
- 10-second timeout per webhook request

## Support

For questions or issues with webhook integrations:
- Email: angelustrio@gmail.com
- Visit: https://receiptmaker.com/webhooks

## Example Use Cases

### 1. Automated Email Receipts
Trigger an email to the customer when a receipt is generated

### 2. Accounting Software Integration
Automatically sync receipts with QuickBooks, Xero, or FreshBooks

### 3. Analytics Dashboard
Build custom analytics and reporting on receipt data

### 4. Inventory Management
Update inventory levels based on receipt items

### 5. CRM Integration
Add transaction records to your CRM system

### 6. Notification System
Send SMS or push notifications for new receipts

### 7. Data Backup
Store receipt data in your own database for compliance

## Changelog

**Version 1.0** (October 2025)
- Initial webhook integration release
- Support for receipt data webhooks
- Bearer token authentication
- Webhook management UI
