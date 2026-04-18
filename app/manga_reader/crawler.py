
from bs4 import BeautifulSoup,Tag
import re


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

def extract_chapters(html):
    soup = BeautifulSoup(html)
    data = soup.find_all(name='li', class_ = 'item')
    text = soup.find('a', {'data-code' : 'JA'}).text
    match = re.search(r"\((\d+)\s*Chapters\)", text)
    number = int(match.group(1)) if match else None
    match_text = f"{number}:"
    chapter_list = [extract_data_from_chapter_card(item) for item in data]
    result = []
    for item in chapter_list:
        result.append(item)
        if match_text in item['title']:
            break
    return result