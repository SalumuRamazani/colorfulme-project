# Stripe Webhook Setup Instructions

## ⚠️ IMPORTANT: You MUST set up the webhook for subscriptions to auto-renew!

Without the webhook configured, subscriptions will expire after the first billing period and won't automatically renew.

## What the Webhook Does

Your app has a webhook endpoint at `/stripe-webhook` that automatically handles:
- ✅ **Subscription renewals** - Extends access when payment succeeds
- ✅ **Subscription cancellations** - Revokes access when user cancels  
- ✅ **Payment failures** - Marks subscription as past_due
- ✅ **Status updates** - Keeps subscription status in sync with Stripe

## Quick Setup (5 minutes)

### 1. Add Webhook Secret to Replit Secrets

First, you need to get your webhook signing secret from Stripe:

1. Go to your [Stripe Dashboard](https://dashboard.stripe.com)
2. Click **Developers** → **Webhooks**
3. Click **Add endpoint** button
4. Enter your webhook URL:
   ```
   https://YOUR-REPLIT-DOMAIN/stripe-webhook
   ```
   (Replace YOUR-REPLIT-DOMAIN with your actual Replit domain)

5. Select these events to listen for:
   - ✅ `customer.subscription.updated`
   - ✅ `customer.subscription.deleted`
   - ✅ `invoice.payment_succeeded`
   - ✅ `invoice.payment_failed`

6. Click **Add endpoint**
7. Click on the webhook you just created
8. Click **Reveal** next to "Signing secret"
9. Copy the secret (starts with `whsec_...`)

### 2. Add Secret to Replit

1. In Replit, click **Secrets** (🔒 icon) in the left sidebar
2. Click **New Secret**
3. Name: `STRIPE_WEBHOOK_SECRET`
4. Value: Paste the `whsec_...` secret from Stripe
5. Click **Add secret**
6. The app will automatically restart with the new secret

### 3. Test the Webhook

#### Option A: Use Stripe CLI (Local Testing)
```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login to Stripe
stripe login

# Forward events to your local endpoint
stripe listen --forward-to localhost:5000/stripe-webhook

# Trigger test events
stripe trigger customer.subscription.updated
stripe trigger invoice.payment_succeeded
```

#### Option B: Test in Stripe Dashboard
1. Go to **Developers** → **Webhooks**
2. Click on your webhook
3. Click **Send test webhook**
4. Select an event type
5. Click **Send test webhook**

### 4. Monitor Webhook Events

Check if webhooks are working:
1. Go to **Developers** → **Webhooks** in Stripe Dashboard
2. Click on your webhook endpoint
3. View **Recent events** to see delivery status
4. Check your Replit logs for webhook processing messages

## Webhook Events Handled

| Event | What Happens |
|-------|-------------|
| `customer.subscription.updated` | Updates subscription status and expiry date when Stripe auto-renews |
| `customer.subscription.deleted` | Marks subscription as inactive when user cancels |
| `invoice.payment_succeeded` | Extends subscription access when recurring payment succeeds |
| `invoice.payment_failed` | Marks subscription as past_due when payment fails |

## Subscription Status Flow

- **active** → User has full access, watermark removed
- **past_due** → Payment failed, subscription still active but flagged
- **inactive** → Subscription canceled or expired, watermark shown

## Troubleshooting

### Webhook Not Receiving Events
- ✅ Check that `STRIPE_WEBHOOK_SECRET` is set in Replit Secrets
- ✅ Verify webhook URL in Stripe Dashboard matches your Replit domain
- ✅ Ensure webhook endpoint is `/stripe-webhook` (not `/webhook`)
- ✅ Check Replit logs for error messages

### Signature Verification Failed
- ✅ Make sure you copied the complete webhook secret (starts with `whsec_`)
- ✅ Verify there are no extra spaces or newlines in the secret
- ✅ Restart the app after adding the secret

### Subscriptions Not Renewing
- ✅ Check Stripe Dashboard → Events to see if webhooks are being sent
- ✅ View Recent deliveries in webhook settings to check for failures
- ✅ Check Replit logs for webhook processing errors

## Production Checklist

Before going live:
- ✅ Add `STRIPE_WEBHOOK_SECRET` to Replit Secrets
- ✅ Configure webhook in Stripe Dashboard with production URL
- ✅ Select all required events (listed above)
- ✅ Test with real subscription to verify auto-renewal works
- ✅ Monitor webhook delivery in Stripe Dashboard

---

**Your webhook endpoint is now active at:**
`https://YOUR-REPLIT-DOMAIN/stripe-webhook`

Once configured, subscriptions will automatically renew and update without any manual intervention! 🎉
