
from bs4 import BeautifulSoup,Tag

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
        'url' : link
    }

def extract_chapters(html):
    soup = BeautifulSoup(html)
    data = soup.find_all(name='li', class_ = 'item')
    return [extract_data_from_chapter_card(item) for item in data]