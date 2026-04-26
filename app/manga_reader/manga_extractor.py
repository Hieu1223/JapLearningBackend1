import os
import json
import requests
import asyncio
from bs4 import BeautifulSoup
from typing import List, Optional
from sqlmodel import select, Session

from ..database.manga_reader.queries import (
    get_cached_search_vrf_token, update_cached_search_vrf_token,
    update_mangas_info
)
from ..database.manga_reader.schema import Manga, Chapter
from .utils import extract_search_vrf_async, get_mangafire_images_url
from .schema import MangaInfo

BASE_URL = os.getenv("BASE_URL", "https://mangafire.to")

class MangafireExtractor:
    def __init__(self, session: Session):
        self.session = session
        self.client = requests.Session()
        # Ensure consistent headers for AJAX requests
        self.client.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Referer": f"{BASE_URL}/",
            "X-Requested-With": "XMLHttpRequest"
        })

    def get(self, path: str):
        url = f"{BASE_URL}{path}"
        response = self.client.get(url)
        response.raise_for_status()
        return response

    def get_raw(self, url: str): 
        response = self.client.get(url)
        response.raise_for_status()
        return response

    def crawl_search_page(self, query: str, page: int, search_vrf: str, sort: str) -> List[MangaInfo]:
        """Modified to include the sort parameter in the AJAX call."""
        # 1. Get the AJAX JSON response with sort and page
        # Mangafire uses 'sort' parameter in their AJAX search
        endpoint = f"/ajax/manga/search?keyword={query}&page={page}&sort={sort}&lang[]=ja&vrf={search_vrf}"
        res = self.get(endpoint)
        
        # 2. Extract the HTML string
        data = res.json()
        html_str = data.get("result", {}).get("html", "")
        if not html_str:
            return []
        
        # 3. Parse the extracted HTML
        soup = BeautifulSoup(html_str, "html.parser")
        
        # 4. Extract data from each 'unit'
        mangas = []
        for card in soup.find_all(class_="unit"):
            try:
                manga_url = card.get('href', "")
                img_tag = card.find('img')
                thumbnail_url = img_tag.get('src') if img_tag else ""
                title_tag = card.find('h6')
                title = title_tag.text.strip() if title_tag else ""
                
                mangas.append(MangaInfo(
                    cover_url=thumbnail_url, 
                    manga_url=manga_url, 
                    name=title
                ))
            except Exception as e:
                print(f"Error parsing card: {e}")
                continue

        return mangas
    
    async def search(self, query: str, page: int = 1, sort: str = "recently_updated") -> List[MangaInfo]:
        """
        Main search entry point. 
        Maps the shared sort keys to Mangafire internal keys.
        """
        query = query.lower()
        
        # Mapping shared keys to Mangafire specific keys if they differ
        # (Based on Mangafire's common sort params)
        sort_map = {
            "recently_updated": "recently_updated",
            "most_viewed": "most_viewed",
            "scores": "scores",
            "title_az": "title_az"
        }
        mf_sort = sort_map.get(sort, "recently_updated")

        # VRF handling
        search_vrf = get_cached_search_vrf_token(self.session, query)
        if not search_vrf:
            search_vrf = await extract_search_vrf_async(query)
            update_cached_search_vrf_token(self.session, query, search_vrf)
        
        # Fetch results
        mangas = self.crawl_search_page(query, page, search_vrf, mf_sort)
        
        # Update database cache
        cached_mangas = [
            Manga(manga_url=m.manga_url, manga_cover_url=m.cover_url) 
            for m in mangas
        ]
        update_mangas_info(self.session, cached_mangas)
        
        return mangas
    
    async def get_chapter_list(self, manga_url: str):
        # Keeps existing implementation via crawler.py helper
        from .crawler import extract_chapters
        return extract_chapters(manga_url)

    async def get_chapter_images(self, chapter_url: str) -> List[str]:
        # 1. Look for the chapter in the database
        statement = select(Chapter).where(Chapter.link == chapter_url)
        chapter = self.session.exec(statement).first()
        
        # 2. CACHE HIT
        if chapter and chapter.image_list and chapter.image_list != "[]" and chapter.image_list != "{}":
            return json.loads(chapter.image_list)

        # 3. CACHE MISS
        ajax_url = await get_mangafire_images_url(chapter_url)
        response = self.get_raw(ajax_url)
        data = response.json()
        
        # Parse the image list (Mangafire returns a list of lists: [[url, status, size], ...])
        images = [img[0] for img in data.get('result', {}).get('images', [])]
        
        if not images:
            raise Exception(f"Failed to extract images for: {chapter_url}")

        # 4. Save to DB
        if not chapter:
            chapter = Chapter(
                link=chapter_url,
                image_list=json.dumps(images)
            )
        else:
            chapter.image_list = json.dumps(images)

        self.session.add(chapter)
        self.session.commit()
        self.session.refresh(chapter)
            
        return images