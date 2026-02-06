#!/usr/bin/env python3
"""
Capture screenshots of receipt generator pages
"""
import os
import sys
from playwright.sync_api import sync_playwright

def capture_receipt(template_name, url_path, output_filename):
    """Capture screenshot of a receipt generator page"""
    
    # Get the domain from environment
    domain = os.getenv('REPLIT_DEV_DOMAIN', 'localhost:5000')
    url = f'https://{domain}{url_path}' if 'REPLIT' in os.environ else f'http://localhost:5000{url_path}'
    
    print(f"Capturing {template_name} screenshot from: {url}")
    
    with sync_playwright() as p:
        # Launch browser in headless mode
        browser = p.chromium.launch(headless=True)
        
        # Create a new page with specific viewport size
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        
        # Navigate to the page
        page.goto(url, wait_until='networkidle', timeout=30000)
        
        # Wait a bit for Alpine.js to fully render
        page.wait_for_timeout(2000)
        
        # Take screenshot of just the receipt preview area (right side)
        # Find the receipt preview element
        receipt_preview = page.locator('#receipt-preview').first
        
        # Take screenshot
        output_path = f'static/images/templates/{output_filename}'
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        receipt_preview.screenshot(path=output_path)
        
        print(f"Screenshot saved to: {output_path}")
        
        # Close browser
        browser.close()
        
        return output_path

if __name__ == '__main__':
    # Check if specific template requested
    if len(sys.argv) > 1:
        template = sys.argv[1].lower()
        if template == 'target':
            capture_receipt('Target', '/generate-target-receipt', 'target-receipt.png')
        elif template == 'starbucks':
            capture_receipt('Starbucks', '/generate-starbucks-receipt', 'starbucks-receipt.png')
        elif template == 'walmart':
            capture_receipt('Walmart', '/generate-walmart-receipt', 'walmart-receipt.png')
        else:
            print(f"Unknown template: {template}")
    else:
        # Capture all by default
        capture_receipt('Target', '/generate-target-receipt', 'target-receipt.png')
        capture_receipt('Starbucks', '/generate-starbucks-receipt', 'starbucks-receipt.png')
        capture_receipt('Walmart', '/generate-walmart-receipt', 'walmart-receipt.png')
