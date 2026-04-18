
from bs4 import BeautifulSoup,Tag
import re
import requests

def extract_data(card: Tag):
    try:
        read_page = card.find(class_ = 'poster').get('href')
        img_card = card.find('img')
        img = img_card.get('src')
        title = img_card.get('alt')
        content_area = card.find(class_ =  "content")
        lastest_chap = content_area.find('span').text
        
        return (read_page, img, title,lastest_chap)
    except Exception as e:
        print(e)
        return None 
def extract_from_page(html:str):
    soup = BeautifulSoup(html)
    data =  [extract_data(i) for i in soup.find_all(class_ = "inner")]
    return [i for i in data if i]

def extract_data_from_chapter_card(card):
    num = card.get('data-number')
    data = list(card.children)[1]
    title = data['title']
    link = data['href']
    return {
        'num' : num,
        'title' : title,
        'url' : link.replace('en','ja')
    }

def extract_chapters(manga_url, lang_code="ja"):
    base_url = "https://mangafire.to"
    
    manga_id = manga_url.split('.')[-1].split('/')[0].split('#')[0]
    print(manga_id)
    is_volume = "#vol" in manga_url
    request_type = "volume" if is_volume else "chapter"
    
    ajax_url = f"{base_url}/ajax/manga/{manga_id}/{request_type}/{lang_code}"
    
    headers = {
        "Referer": f"{base_url}/",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    response = requests.get(ajax_url, headers=headers)
    print(response.text)
    print(ajax_url)
    response = response.json()
    soup = BeautifulSoup(response.get("result", ""), "html.parser")
    
    selector = ".vol-list > .item" if is_volume else "li"
    data = soup.select(selector)
    
    chapter_list = []
    for item in data:
        link = item.select_one("a")
        if not link:
            continue
            
        chapter_list.append({
            "url": link.get("href"),
            "num": item.get("data-number", "-1"),
            "title": item.select_one("span").text.strip() if item.select_one("span") else ""
        })
    
    chapter_list.reverse()
    return chapter_list