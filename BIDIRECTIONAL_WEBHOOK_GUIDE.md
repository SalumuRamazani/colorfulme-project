# Bidirectional Webhook Integration Guide - ReceiptMake

## Overview

ReceiptMake now supports **bidirectional webhooks**, allowing you to:
1. **Send data TO external services** (Outgoing Webhooks) - e.g., send receipt data to outrank.so
2. **Receive data FROM external services** (Incoming Webhooks) - e.g., receive data from outrank.so

---

## 📤 OUTGOING WEBHOOKS (ReceiptMake → External Services)

### Use Case:
Send receipt data FROM ReceiptMake TO external services like outrank.so

### Setup Instructions:

1. **Get External Service Details** (from outrank.so):
   - Webhook Endpoint URL
   - API Key/Access Token (if required)

2. **In ReceiptMake**:
   - Go to Dashboard → Webhook Integrations
   - Scroll to "Outgoing Webhooks" section
   - Click "Add Webhook"
   - Fill in:
     * **Integration Name**: `Outrank Integration`
     * **Webhook Endpoint**: `https://api.outrank.so/your-endpoint-here`
     * **Access Token**: `your_outrank_api_key_here`
   - Click "Send Test" to verify connection
   - Click "Create Webhook"

3. **That's it!** Every time you generate a receipt in ReceiptMake, the data will automatically be sent to outrank.so

### Data Format Sent:
```json
{
  "user_id": "user_abc123",
  "user_email": "user@example.com",
  "timestamp": "2025-10-22T20:30:00.000Z",
  "receipt_data": {
    "businessName": "...",
    "items": [...],
    "total": 99.99,
    ...
  }
}
```

---

## 📥 INCOMING WEBHOOKS (External Services → ReceiptMake)

### Use Case:
Receive data FROM external services like outrank.so INTO ReceiptMake

### Setup Instructions:

1. **In ReceiptMake**:
   - Go to Dashboard → Webhook Integrations
   - Look at the "Incoming Webhooks" section (at the top)
   - Copy your unique **Webhook URL**
   - Copy your **API Key** (click "Regenerate" if you need a new one)

2. **In Outrank.so** (or the external service):
   - Go to their integrations/webhooks settings
   - Add a new webhook integration
   - Paste your ReceiptMake Webhook URL
   - Paste your ReceiptMake API Key

3. **That's it!** Now outrank.so can send data to ReceiptMake, and you'll see it in your webhook history

---

## 🔗 **FOR OUTRANK.SO INTEGRATION**

### What to provide to outrank.so:

When connecting outrank.so to ReceiptMake, give them these 3 pieces of information:

1. **Integration Name**: `ReceiptMake Integration` (or any name you prefer)

2. **Webhook Endpoint**: 
   ```
   [Your unique URL from ReceiptMake - looks like:]
   https://your-app.replit.app/api/incoming/webhooks/[unique-id]
   ```

3. **Access Token**:
   ```
   [Your API key from ReceiptMake - starts with random characters]
   ```

### Where to find these in ReceiptMake:
1. Login to ReceiptMake
2. Go to **Dashboard** → **Webhook Integrations**
3. Look at the **"Incoming Webhooks"** section (green arrow icon)
4. Click **"Copy"** next to "Your Webhook URL"
5. Click **"Regenerate"** to see your API key (copy it before it hides)

---

## 📊 **Viewing Incoming Webhook History**

To see data received from external services:

1. Go to Dashboard → Webhook Integrations
2. Scroll to "Incoming Webhooks" section
3. Look at "Recent Events" at the bottom
4. You'll see:
   - ✓ Success events (green)
   - ✗ Failed events (red/amber)
   - Timestamp, IP address, error messages
5. Click any event to see full details and payload

---

## 🔐 **Security**

### Outgoing Webhooks:
- Your access token is sent as `Authorization: Bearer YOUR_TOKEN`
- All data is sent over HTTPS
- You can disable webhooks anytime

### Incoming Webhooks:
- External services MUST include your API key as `Authorization: Bearer YOUR_API_KEY`
- Requests without valid API key are rejected
- All events are logged with IP address and timestamp
- You can regenerate your API key anytime (old key stops working immediately)
- You can disable incoming webhooks anytime

---

## 🧪 **Testing**

### Test Outgoing Webhooks:
1. Use webhook.site to get a test URL
2. Add webhook with that URL
3. Click "Send Test"
4. View the payload on webhook.site

### Test Incoming Webhooks:
Use curl to send a test request:

```bash
curl -X POST https://your-app.replit.app/api/incoming/webhooks/[your-unique-id] \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "test": true,
    "message": "Test from outrank.so",
    "data": {
      "some": "data"
    }
  }'
```

Successful response:
```json
{
  "success": true,
  "message": "Webhook received successfully",
  "event_id": "abc-123-xyz"
}
```

---

## ❓ **FAQ**

**Q: Can I have multiple outgoing webhooks?**
A: Yes! You can add as many as you want.

**Q: Can I have multiple incoming webhook URLs?**
A: No, each user has one unique incoming webhook URL. But you can share it with multiple services.

**Q: What happens if I regenerate my API key?**
A: The old key stops working immediately. Update it in all external services.

**Q: How long is webhook history kept?**
A: The last 50 events are displayed.

**Q: Can I filter webhook history?**
A: Not yet, but it's coming soon!

---

## 📞 **Support**

For help with webhook integrations:
- Email: angelustrio@gmail.com
- Documentation: See WEBHOOK_INTEGRATION_GUIDE.md for detailed API specs

---

## 🎯 **Quick Summary**

**To send FROM ReceiptMake TO outrank.so:**
→ Add outrank's webhook URL to "Outgoing Webhooks" section

**To receive FROM outrank.so TO ReceiptMake:**
→ Give your ReceiptMake webhook URL and API key to outrank.so (found in "Incoming Webhooks" section)

**Both directions work independently!** Set up one or both as needed.
