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
from ..database.manga_reader.schema import Chapter
from sqlmodel import select

import os
import requests
from .crawler import extract_from_page,extract_chapters
import asyncio
import json
from bs4 import BeautifulSoup
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
        #
        #self.client.proxies.update({
        #    "http": os.getenv("HTTP_PROXY")
        #})


    def get(self,path: str):
        url = f"{BASE_URL}{path}"
        response = self.client.get(url)
        response.raise_for_status()
        return response

    def get_raw(self,url): 
        response = self.client.get(url)
        response.raise_for_status()
        return response

    def crawl_search_page(self, query, page, search_vrf) -> list[MangaInfo]:
        # 1. Get the AJAX JSON response
        res = self.get(f"/ajax/manga/search?keyword={query}&page={page}&vrf={search_vrf}")
        
        # 2. Extract the HTML string from the JSON wrapper
        data = res.json()
        html_str = data.get("result").get("html", "")
        
        # 3. Parse the extracted HTML
        soup = BeautifulSoup(html_str, "html.parser")
        
        # 4. Extract data from each 'unit' (replaces your extract_from_page logic)
        mangas = []
        for card in soup.find_all(class_="unit"):
            try:
                manga_url = card.get('href')
                # Ensure absolute URL
                    
                img_tag = card.find('img')
                thumbnail_url = img_tag.get('src') if img_tag else ""
                
                # Title is in the h6 tag in this HTML version
                title_tag = card.find('h6')
                title = title_tag.text.strip() if title_tag else ""
                
                # Latest chapter is in the spans inside the info div
                info_div = card.find(class_="info").find('div')
                spans = info_div.find_all('span')
                lastest_chapter = spans[-1].text.strip() if spans else ""
                
                mangas.append((manga_url, thumbnail_url, title, lastest_chapter))
            except Exception as e:
                print(e)
                continue

        # 5. Return using your exact original interface
        return [MangaInfo(cover_url=thumbnail_url, manga_url=manga_url, name=title) 
            for (manga_url, thumbnail_url, title, lastest_chapter) in mangas]
    
    async def search(self,query) -> list[MangaInfo]:
        query = query.lower()
        search_vrf = get_cached_search_vrf_token(self.session, query)
        if not search_vrf:
            search_vrf = await extract_search_vrf_async(query)
            print(search_vrf)
            update_cached_search_vrf_token(self.session,query,search_vrf)
        mangas = self.crawl_search_page(query,0, search_vrf)
        cached_mangas = [Manga(manga_url= manga.manga_url,manga_cover_url= manga.cover_url) for manga in mangas]
        update_mangas_info(self.session, cached_mangas)
        return mangas
    

    async def get_chapter_list(self,manga_url):
        return extract_chapters(manga_url)



    async def get_chapter_images(self, chapter_url: str):
        # 1. Look for the chapter in your new CachedChapter table
        statement = select(Chapter).where(Chapter.link == chapter_url)
        chapter = self.session.exec(statement).first()
        
        # 2. CACHE HIT: If exists and has images, return them immediately
        if chapter and chapter.image_list and chapter.image_list != "{}":
            print(f"Cache Hit for images: {chapter_url}")
            return json.loads(chapter.image_list)

        # 3. CACHE MISS: We need to fetch from the source
        print(f"Cache Miss for images: {chapter_url}. Fetching...")
        
        # Get the AJAX URL from your remote extractor
        ajax_url = await get_mangafire_images_url(chapter_url)
        response = self.get_raw(ajax_url)
        data = response.json()
        
        # Parse the image list
        images = [img[0] for img in data['result']['images']]
        
        if not images:
            raise Exception(f"Failed to extract images for: {chapter_url}")

        # 4. CREATE OR UPDATE: If chapter didn't exist, initialize it.
        if not chapter:
            chapter = Chapter(
                link=chapter_url,
                image_list=json.dumps(images)
            )
            print(f"Created new CachedChapter record for: {chapter_url}")
        else:
            # If record existed but image_list was empty
            chapter.image_list = json.dumps(images)
            print(f"Updated existing CachedChapter record for: {chapter_url}")

        # 5. Persist to DB
        self.session.add(chapter)
        self.session.commit()
        self.session.refresh(chapter)
            
        return images