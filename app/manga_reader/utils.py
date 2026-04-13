from camoufox.async_api import AsyncCamoufox
import os
import random
from urllib.parse import urlparse, parse_qs
import asyncio
proxy = {
    'server' : os.getenv("PROXY_SERVER"),
    'username' : os.getenv("PROXY_USERNAME"),
    'password' : os.getenv("PROXY_PASSWORD")
}

async def extract_search_vrf_async(base_url, search_query):
    
    # Use AsyncCamoufox for asynchronous operation
    async with AsyncCamoufox(headless=True,geoip=True, proxy = proxy) as browser:
        page = await browser.new_page()
        
        print(f"Navigating to {base_url}...")
        await page.goto(base_url, wait_until="domcontentloaded")
        search_input = page.locator(".search-inner input[name='keyword']")
        await search_input.click()
        await search_input.fill(search_query.strip().lower())
        async with page.expect_navigation(wait_until="domcontentloaded"):
            await page.keyboard.press("Enter")
        
        current_url = page.url 
        print(f"Current URL: {current_url}")
        parsed_url = urlparse(current_url)
        params = parse_qs(parsed_url.query)
        vrf_token = params.get('vrf', [None])[0]
        
        if vrf_token:
            print(f"Extracted VRF: {vrf_token}")
            return vrf_token
        else:
            print("VRF token not found in the final URL.")
            return None



async def get_mangafire_images_url(chapter_url):
    """
    Navigates to a MangaFire chapter and returns the full AJAX 
    endpoint URL used to fetch image data.
    """
    final_url = None

    async with AsyncCamoufox(headless=True,geoip=True,proxy = proxy) as browser:
        page = await browser.new_page()

        # Listener to catch the specific request
        async def request_handler(request):
            nonlocal final_url
            # Filter for the specific AJAX path
            if "ajax/read/chapter" in request.url:
                final_url = request.url

        page.on("request", request_handler)

        try:
            # Navigate and wait for the page to trigger its internal API calls
            await page.goto(chapter_url, wait_until="networkidle")
            
            # Brief polling loop to ensure the request was fired
            for _ in range(20): 
                if final_url:
                    break
                await asyncio.sleep(0.5)
                
        except Exception as e:
            print(f"Error during navigation: {e}")
    
    return final_url