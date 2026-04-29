import os
import re
import threading
import requests
from bs4 import BeautifulSoup
from typing import List
from sqlmodel import Session
from app.manga_reader.schema import MangaInfo
from app.database.manga_reader.schema import Chapter
from app.database.manga_reader.queries import get_or_create_chapter, get_or_create_manga,update_chapter_pages
import json
from sqlmodel import select
class NatsuExtractor:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.base_url = os.getenv("BASE_URL", "https://rawkuma.net").rstrip("/")
        self.client = requests.Session()
        proxy_url = os.getenv("HTTP_PROXY")
        self.client.proxies = {
            "http": proxy_url,
            "https": proxy_url,
        }
        self.client.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "Chrome/110.0.0.0 Safari/537.36"
            ),
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

            # Method 1: hx-get / data-id attribute
            ajax_trigger = soup.select_one("#gallery-list, .load-chapters")
            if ajax_trigger:
                attr = ajax_trigger.get("hx-get") or ajax_trigger.get("data-id")
                if attr:
                    match = re.search(r"manga_id=(\d+)", attr)
                    if match:
                        return match.group(1)
                    if attr.isdigit():
                        return attr

            # Method 2: WordPress shortlink
            shortlink = soup.select_one("link[rel='shortlink']")
            if shortlink and "p=" in shortlink["href"]:
                return shortlink["href"].split("p=")[-1]

            # Method 3: body class postid-{id}
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

        params = {"action": "chapter_list", "manga_id": manga_id}
        res = self.client.get(
            f"{self.base_url}/wp-admin/admin-ajax.php", params=params
        )
        soup = BeautifulSoup(res.text, "html.parser")

        chapters = []
        for i, row in enumerate(reversed(soup.select("div a:has(time)"))):
            chapter_url = row["href"]
            title_tag = row.select_one("span")
            title = title_tag.text.strip() if title_tag else "Chapter"
            num = str(i)

            # Persist to DB so history resolution can find chapters by URL
            get_or_create_chapter(
                self.db,
                chapter_url=chapter_url,
                title=title,
                num=num,
            )

            chapters.append({"num": num, "title": title, "url": chapter_url})

        return chapters

    def get_page_images(self, chapter_url: str) -> List[str]:
        """Logic from Kotlin: pageListParse()"""


        chapter = self.db.exec(
            select(Chapter).where(Chapter.link == chapter_url)
        ).first()

        if chapter and chapter.image_list and chapter.image_list not in ("{}", "[]", ""):
            try:
                return json.loads(chapter.image_list)
            except Exception as e:
                print(e)


        res = self.client.get(chapter_url)
        soup = BeautifulSoup(res.text, "html.parser")
        images = []
        for img in soup.select("main .relative section img, #readerarea img"):
            url = img.get("src") or img.get("data-src")
            if url:
                if not url.startswith("http"):
                    url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
                images.append(url)

        # Remove duplicates while preserving order
        images = list(dict.fromkeys(images))

        # Save to DB in background so the response is returned immediately
        def _save():
            try:
                print(images)
                update_chapter_pages(self.db, chapter_url, images)
            except Exception as e:
                print(f"Background save failed for {chapter_url}: {e}")

        threading.Thread(target=_save, daemon=True).start()
        #_save()
        return images

    def search(self, query: str, page: int = 1, sort: str = "") -> List[MangaInfo]:
        api_url = f"{self.base_url}/wp-admin/admin-ajax.php?action=advanced_search"

        sort_map = {
            "recently_updated": "updated",
            "most_viewed": "popular",
            "scores": "rating",
            "title_az": "title",
        }

        payload = {
            "nonce": self._get_nonce(),
            "page": str(page),
            "query": query,
            "order": "desc",
            "orderby": sort_map.get(sort, "updated"),
            "inclusion": "OR",
            "exclusion": "OR",
        }

        try:
            response = self.client.post(api_url, data=payload)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            for item in soup.select("div:has(> a[href*='/manga/'] img)")[::2]:
                link_tag = item.select_one("a[href*='/manga/']")
                img_tag = item.select_one("img")

                if link_tag and img_tag:
                    results.append(
                        MangaInfo(
                            name=img_tag.get("alt", "Unknown"),
                            manga_url=link_tag["href"],
                            cover_url=img_tag.get("src") or img_tag.get("data-src", ""),
                        )
                    )

            # 🔥 background save
            import threading

            def save():
                for manga in results:
                    get_or_create_manga(
                        self.db,
                        manga_url=manga.manga_url,
                        cover_url=manga.cover_url,
                        name=manga.name,
                    )

            threading.Thread(target=save, daemon=True).start()

            return results

        except Exception as e:
            print(f"Search failed: {e}")
            return []

    def _get_nonce(self) -> str:
        """Fetches the WordPress AJAX nonce required for search/list actions."""
        url = (
            f"{self.base_url}/wp-admin/admin-ajax.php"
            "?type=search_form&action=get_nonce"
        )
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