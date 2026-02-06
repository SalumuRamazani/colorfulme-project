"""
Script to capture clean preview images of all receipt templates
Ensures only the receipt element is captured, no navigation or UI chrome
"""
import asyncio
from playwright.async_api import async_playwright
import os

# List of all template slugs based on TEMPLATE_JSON_MAP
TEMPLATES = [
    'walmart', 'target', 'starbucks', 'cvs-pharmacy', 'best-buy',
    'costco-wholesale', 'mcdonalds', 'albertsons', 'lowes', 'kroger',
    'subway', 'shell', 'chevron', 'bp', 'walgreens', 'safeway',
    'popeyes', 'uber', 'gucci', 'rolex', 'dior', 'chanel', 'cartier',
    'burberry', 'stockx', 'goat', 'parking', 'taxi', 'hilton-hotel',
    'motel6', 'neimanmarcus', 'pawnshop', 'tire-shop', 'oil-change',
    't-mobile', 'dollar-tree', 'restaurant-bill', 'hotel', 'gas',
    'generic-pos'
]

async def capture_template_preview(page, template_slug, output_dir):
    """Capture a single template preview - ONLY the receipt element"""
    url = f"http://127.0.0.1:5000/generate-{template_slug}-receipt"
    output_path = os.path.join(output_dir, f"{template_slug}-preview.png")
    
    try:
        print(f"Capturing {template_slug}...", flush=True)
        
        # Navigate to the template page
        await page.goto(url, wait_until='networkidle', timeout=20000)
        
        # Wait for Alpine.js to fully hydrate the receipt
        # The #receipt-preview element itself has the receipt-paper class
        await page.wait_for_selector('#receipt-preview.receipt-paper', state='visible', timeout=15000)
        
        # Give Alpine.js extra time to finish rendering all sections
        await asyncio.sleep(1.5)
        
        # Get the receipt element
        receipt_locator = page.locator('#receipt-preview').first
        
        # Verify the element is actually visible
        is_visible = await receipt_locator.is_visible()
        if not is_visible:
            print(f"✗ Receipt element not visible for {template_slug}")
            return False
        
        # Scroll element into view
        await receipt_locator.scroll_into_view_if_needed()
        await asyncio.sleep(0.3)
        
        # Take screenshot of ONLY the receipt element
        await receipt_locator.screenshot(path=output_path)
        print(f"✓ Saved {output_path}", flush=True)
        return True
            
    except asyncio.TimeoutError:
        print(f"✗ Timeout waiting for receipt to render: {template_slug}")
        return False
    except Exception as e:
        print(f"✗ Error capturing {template_slug}: {str(e)}")
        return False

async def main():
    """Main function to capture all templates"""
    output_dir = "static/images/template-previews"
    
    # Clear existing previews (keep symlinks for now)
    if os.path.exists(output_dir):
        for file in os.listdir(output_dir):
            file_path = os.path.join(output_dir, file)
            # Only remove regular files, not symlinks
            if os.path.isfile(file_path) and not os.path.islink(file_path):
                os.remove(file_path)
                print(f"Removed old preview: {file}")
    
    os.makedirs(output_dir, exist_ok=True)
    
    async with async_playwright() as p:
        # Launch browser with larger viewport to capture full receipt
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1200, 'height': 1600})
        
        # Capture each template
        success_count = 0
        failed = []
        
        for template_slug in TEMPLATES:
            if await capture_template_preview(page, template_slug, output_dir):
                success_count += 1
            else:
                failed.append(template_slug)
            
            # Small delay between captures
            await asyncio.sleep(0.5)
        
        await browser.close()
        
        print(f"\n{'='*60}")
        print(f"Completed: {success_count}/{len(TEMPLATES)} templates captured")
        
        if failed:
            print(f"\nFailed templates ({len(failed)}):")
            for slug in failed:
                print(f"  - {slug}")
        else:
            print("\n✓ All templates captured successfully!")
        print(f"{'='*60}\n")

if __name__ == "__main__":
    asyncio.run(main())
