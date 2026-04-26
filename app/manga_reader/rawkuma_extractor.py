import os
import json
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from sqlmodel import Session
from app.manga_reader.schema import MangaInfo
from app.database.manga_reader.schema import Chapter
import re
class NatsuExtractor:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.base_url = os.getenv("BASE_URL", "https://rawkuma.net").rstrip("/")
        self.client = requests.Session()
        self.client.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/110.0.0.0 Safari/537.36",
            "Referer": f"{self.base_url}/",
        })

    def get_manga_id(self, manga_url: str) -> str:
        """
        Scrapes the manga page to find the internal WordPress Post ID.
        This ID is required for the chapter list AJAX call.
        """
        try:
            res = self.client.get(manga_url)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")

            # Method 1: Check hx-get attribute (Common in NatsuId themes)
            # Example: hx-get=".../admin-ajax.php?action=chapter_list&manga_id=123"
            ajax_trigger = soup.select_one("#gallery-list, .load-chapters")
            if ajax_trigger:
                attr = ajax_trigger.get("hx-get") or ajax_trigger.get("data-id")
                if attr:
                    match = re.search(r'manga_id=(\d+)', attr)
                    if match:
                        return match.group(1)
                    if attr.isdigit():
                        return attr

            # Method 2: Check for the shortlink (Standard WordPress)
            # Example: <link rel='shortlink' href='https://site.com/?p=123' />
            shortlink = soup.select_one("link[rel='shortlink']")
            if shortlink and "p=" in shortlink["href"]:
                return shortlink["href"].split("p=")[-1]

            # Method 3: Body classes
            # Example: <body class="manga-template-default postid-123 ...">
            body = soup.find("body")
            if body and body.has_attr("class"):
                for cls in body["class"]:
                    if cls.startswith("postid-"):
                        return cls.replace("postid-", "")

            raise ValueError(f"Could not extract manga ID from {manga_url}")
        except Exception as e:
            print(f"Error getting manga ID: {e}")
            return ""

    def get_chapter_list(self, manga_url: str) -> List[dict]:
        """
        Uses the manga_id to fetch the actual chapter list via AJAX.
        """
        manga_id = self.get_manga_id(manga_url)
        if not manga_id:
            return []

        params = {
            "action": "chapter_list",
            "manga_id": manga_id
        }
        
        # AJAX call mimicking the Kotlin source
        res = self.client.get(f"{self.base_url}/wp-admin/admin-ajax.php", params=params)
        soup = BeautifulSoup(res.text, "html.parser")
        
        chapters = []
        for i, row in enumerate(soup.select("div a:has(time)")):
            chapters.append({
                'num': f'{i}',
                "title": row.select_one("span").text.strip() if row.select_one("span") else "Chapter",
                "url": row["href"],
            })
        return chapters

    def get_chapter_images(self, chapter_url: str) -> List[str]:
        """Logic from Kotlin: pageListParse()"""
        res = self.client.get(chapter_url)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Selector: "main .relative section > img" + common fallback "#readerarea img"
        images = []
        for img in soup.select("main .relative section img, #readerarea img"):
            # Kotlin logic handles absUrl; Python requests/bs4 requires manual check
            url = img.get("src") or img.get("data-src")
            if url:
                if not url.startswith("http"):
                    url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
                images.append(url)

        # Remove duplicates while preserving order
        images = list(dict.fromkeys(images))

        # DB Creation (The only persistence logic retained)
        if False:
            new_chapter = Chapter(
                link=chapter_url,
                image_list=json.dumps(images)
            )
            self.db.add(new_chapter)
            self.db.commit()
            self.db.refresh(new_chapter)
            
        return images
    def search(self, query: str, page: int = 1) -> List[MangaInfo]:
        """Performs a POST search using the NatsuId multipart strategy."""
        api_url = f"{self.base_url}/wp-admin/admin-ajax.php?action=advanced_search"
        
        # Constructing the form data payload mimicking the Kotlin MultipartBody
        payload = {
            "nonce": self._get_nonce(),
            "page": str(page),
            "query": query,
            "order": "desc",
            "orderby": "latest",
            "inclusion": "OR",
            "exclusion": "OR"
        }

        try:
            response = self.client.post(api_url, data=payload)
            response.raise_for_status()
            
            # The theme returns HTML fragments inside the response
            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            # Selector based on: "div > a[href*=/manga/]:has(> img)"
            for item in soup.select("div:has(> a[href*='/manga/'] img)"):
                link_tag = item.select_one("a[href*='/manga/']")
                img_tag = item.select_one("img")
                
                if link_tag and img_tag:
                    results.append(MangaInfo(
                        name=img_tag.get("alt", "Unknown"),
                        manga_url=link_tag["href"],
                        cover_url=img_tag.get("src") or img_tag.get("data-src")
                    ))
            return results
        except Exception as e:
            print(f"Search failed: {e}")
            return []
        
    def _get_nonce(self) -> str:
        """Fetches the WordPress AJAX nonce required for search/list actions."""
        url = f"{self.base_url}/wp-admin/admin-ajax.php?type=search_form&action=get_nonce"
        try:
            res = self.client.get(url, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            nonce = soup.select_one("input[name=search_nonce]")
            if not nonce:
                raise ValueError("Nonce field not found in response")
            return nonce["value"]
        except Exception as e:
            print(f"Nonce Retrieval Error: {e}")
            return ""
