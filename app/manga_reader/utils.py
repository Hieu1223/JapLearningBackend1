from urllib.parse import urlparse, parse_qs
import asyncio
import modal

client = modal.Cls.from_name("mangafire-crawler", "MangafireTokenExtractor")()


async def extract_search_vrf_async(search_query):
    return await client.get_vrf_token.remote.aio(search_query)



async def get_mangafire_images_url(chapter_url):
    return await client.get_chapter_ajax_url.remote.aio('https://mangafire.to/read/test-flight-girlss.k28w/en/chapter-1')