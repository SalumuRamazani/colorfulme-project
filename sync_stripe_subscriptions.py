#!/usr/bin/env python3
"""
Stripe Subscription Sync Script
================================
This script syncs your local database with Stripe's active subscriptions.
Run this once to fix any subscriptions that got out of sync when webhooks weren't working.

Usage: python sync_stripe_subscriptions.py
"""

import os
import sys
from datetime import datetime
import stripe
from app import app, db
from models import Subscription, User

# Initialize Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

def sync_subscriptions():
    """Sync all active Stripe subscriptions with local database"""
    
    print("=" * 60)
    print("Stripe Subscription Sync Tool")
    print("=" * 60)
    print()
    
    if not stripe.api_key:
        print("❌ ERROR: STRIPE_SECRET_KEY not found in environment variables")
        print("Please set your Stripe secret key and try again.")
        sys.exit(1)
    
    print("🔍 Fetching active subscriptions from Stripe...")
    
    try:
        # Fetch all active subscriptions from Stripe
        subscriptions = stripe.Subscription.list(
            status='active',
            limit=100,
            expand=['data.customer']
        )
        
        total_stripe_subs = len(subscriptions.data)
        print(f"✅ Found {total_stripe_subs} active subscriptions in Stripe")
        print()
        
        if total_stripe_subs == 0:
            print("ℹ️  No active subscriptions found in Stripe. Nothing to sync.")
            return
        
        # Stats
        updated_count = 0
        already_synced_count = 0
        not_found_count = 0
        errors = []
        
        with app.app_context():
            print("🔄 Processing subscriptions...")
            print()
            
            for stripe_sub in subscriptions.data:
                try:
                    stripe_sub_id = stripe_sub.id
                    stripe_customer_id = stripe_sub.customer.id if hasattr(stripe_sub.customer, 'id') else stripe_sub.customer
                    customer_email = stripe_sub.customer.email if hasattr(stripe_sub.customer, 'email') else None
                    status = stripe_sub.status
                    
                    # Safely get current_period_end
                    current_period_end = None
                    if hasattr(stripe_sub, 'current_period_end') and stripe_sub.current_period_end:
                        current_period_end = datetime.fromtimestamp(stripe_sub.current_period_end)
                    elif hasattr(stripe_sub, 'ended_at') and stripe_sub.ended_at:
                        current_period_end = datetime.fromtimestamp(stripe_sub.ended_at)
                    
                    # Skip if we can't determine expiration
                    if not current_period_end:
                        print(f"⚠️  Skipping {customer_email or stripe_sub_id}: No expiration date found")
                        continue
                    
                    # Find subscription in local database
                    local_sub = Subscription.query.filter_by(
                        stripe_subscription_id=stripe_sub_id
                    ).first()
                    
                    if not local_sub:
                        # Try to find by stripe_customer_id
                        local_sub = Subscription.query.filter_by(
                            stripe_customer_id=stripe_customer_id
                        ).first()
                
                    if local_sub:
                        # Check if update is needed
                        needs_update = (
                            local_sub.status != 'active' or
                            local_sub.expires_at != current_period_end
                        )
                        
                        if needs_update:
                            # Update subscription
                            old_status = local_sub.status
                            old_expires = local_sub.expires_at
                            
                            local_sub.status = 'active'
                            local_sub.expires_at = current_period_end
                            local_sub.stripe_subscription_id = stripe_sub_id
                            local_sub.stripe_customer_id = stripe_customer_id
                            
                            db.session.commit()
                            
                            user = User.query.get(local_sub.user_id)
                            user_email = user.email if user else "Unknown"
                            
                            print(f"✅ Updated: {user_email}")
                            print(f"   Status: {old_status} → active")
                            print(f"   Expires: {old_expires} → {current_period_end}")
                            print()
                            
                            updated_count += 1
                        else:
                            user = User.query.get(local_sub.user_id)
                            user_email = user.email if user else "Unknown"
                            
                            print(f"✓  Already synced: {user_email}")
                            already_synced_count += 1
                    else:
                        # Not found in database
                        print(f"⚠️  Not found in database: {customer_email or stripe_customer_id}")
                        print(f"   Stripe Sub ID: {stripe_sub_id}")
                        print(f"   This user may need manual investigation")
                        print()
                        
                        not_found_count += 1
                        errors.append({
                            'email': customer_email,
                            'stripe_sub_id': stripe_sub_id,
                            'stripe_customer_id': stripe_customer_id
                        })
                
                except Exception as e:
                    print(f"⚠️  Error processing subscription {stripe_sub_id}: {str(e)}")
                    continue
        
        # Summary
        print()
        print("=" * 60)
        print("Sync Complete!")
        print("=" * 60)
        print(f"Total Stripe Subscriptions: {total_stripe_subs}")
        print(f"✅ Updated in database:     {updated_count}")
        print(f"✓  Already up-to-date:      {already_synced_count}")
        print(f"⚠️  Not found (manual):      {not_found_count}")
        print()
        
        if errors:
            print("⚠️  Manual Investigation Needed:")
            print("These subscriptions are active in Stripe but not in your database:")
            print()
            for error in errors:
                print(f"  • Email: {error['email'] or 'N/A'}")
                print(f"    Stripe Sub ID: {error['stripe_sub_id']}")
                print(f"    Customer ID: {error['stripe_customer_id']}")
                print()
            print("Action: Check if these users signed up correctly or need to be added manually.")
        
        print()
        print("🎉 Sync completed successfully!")
        print("Future renewals will be caught automatically by the webhook.")
        
    except Exception as e:
        error_msg = str(e)
        if 'authentication' in error_msg.lower() or 'api key' in error_msg.lower():
            print(f"❌ Authentication Error: {error_msg}")
            print("Check that your STRIPE_SECRET_KEY is correct.")
        else:
            print(f"❌ Unexpected Error: {error_msg}")
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    print()
    response = input("This will update your database to match Stripe. Continue? (yes/no): ")
    print()
    
    if response.lower() in ['yes', 'y']:
        sync_subscriptions()
    else:
        print("Sync cancelled.")
