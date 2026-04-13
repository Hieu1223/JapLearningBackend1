from ..database.manga_reader.queries import (
    get_cached_search_vrf_token, update_cached_search_vrf_token,
    update_mangas_info,get_cached_chapter_info
)
from ..database.manga_reader.schema import (
    Manga
)
from .utils import extract_search_vrf_async,get_mangafire_images_url
from .schema import (
    MangaInfo
)

import os
import requests
from .crawler import extract_from_page,extract_chapters
import asyncio

BASE_URL = os.getenv("BASE_URL", "https://mangafire.to")

class MangafireExtractor:
    def __init__(self,session):
        self.session = session

        self.client = requests.Session()

        self.client.headers.update({
            "Cookie": "usertype=guest; cf_clearance=GyY43a9QaRKh0K22L9Xlv24BKZpp9lBo7E6O8_.M8ig-1744350198-1.2.1.1-xQttjYiNo3PzhoZ7JWg_j_ZOv4fgNF8WSB7Cqu279eFtN1aNKp1Bpkjz7hIWZ00Fn8MGd0xOi9vVdnq2iOTbW5OzOus8eIdka.DGyXkXDOC0g0o9n2lwDAEa1JYVZPXr4yjEnC5pP4xBBZZecUNwhQ37KNwKC7ECbyu0zssn3PbarKTe4SOUCXfNMNhNJh3xbDMN9xldKgIRZE2R1m8flWYujOg.NX7ByDAblvCNHjEnkGtROfH2gOBm_djbMIU_hr0hYTLxm60Dwu9WsqVjnTzpFCubIF4vU1oo0wa9BMHNxexn1Ut5bM.c93CMOyO.WCPmlx8Y73v7oNJ_yp9Tz.Q1A2M.lDPvMSs1bt.GycI",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Referer": "https://mangafire.to/"
        })


    def get(self,path: str, **kwargs):
        url = f"{BASE_URL}{path}"
        response = self.client.get(url, **kwargs)
        response.raise_for_status()
        return response

    def get_raw(self,url): 
        response = self.client.get(url)
        response.raise_for_status()
        return response

    def crawl_search_page(self,query,page, search_vrf) -> list[MangaInfo]:
        res = self.get(f"/filter?keyword={query}&page={page}&vrf={search_vrf}")
        html =  res.text
        mangas = extract_from_page(html)
        return [MangaInfo(cover_url=thumbnail_url, manga_url=manga_url, name= title) for (manga_url, thumbnail_url, title,lastest_chapter) in mangas]

    async def search(self,query) -> list[MangaInfo]:
        query = query.lower()
        search_vrf = get_cached_search_vrf_token(self.session, query)
        if not search_vrf:
            search_vrf = await extract_search_vrf_async(BASE_URL,query)
            print(search_vrf)
            update_cached_search_vrf_token(self.session,query,search_vrf)
        mangas = self.crawl_search_page(query,0, search_vrf)
        cached_mangas = [Manga(manga_url= manga.manga_url,manga_cover_url= manga.cover_url) for manga in mangas]
        update_mangas_info(self.session, cached_mangas)
        return mangas
    

    async def get_chapter_list(self,manga_url):
        html = self.get(manga_url).text
        return extract_chapters(html)

    async def get_chapter_images(self,chapter_url):
        image_urls = get_cached_chapter_info(self.session, chapter_url)
        if not image_urls:
            image_urls = await get_mangafire_images_url(BASE_URL + chapter_url)
        data = self.get_raw(image_urls).json()
        images = data['result']['images']
        return images