from sudachipy import tokenizer
from sudachipy import dictionary
from sqlmodel import Session
from fastapi import Depends
from typing import List,Dict,Optional,Any
import re
import httpx
from .dictionary import fetch_api_suggestions
from ..database import get_session
from ..database.dictionary.schema import Word
from ..database.dictionary.queries import add_word, look_up_word_exact
from .schema import Token, WordEntry
import jaconv
import re
from sqlmodel import select

tokenizer_obj = dictionary.Dictionary(dict="full").create()
mode = tokenizer.Tokenizer.SplitMode.C
client = httpx.AsyncClient(base_url="https://api.jdict.net/api/v1")

ALLOWED_POS = {"名詞", "動詞", "形容詞", "形状詞", "副詞", "連体詞"}


def split_japanese_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[。！？?])", text)
    return [s.strip() for s in sentences if s.strip()]


def is_katakana(text: str) -> bool:
    """Kiểm tra xem chuỗi có chứa ký tự Katakana không."""
    return bool(re.search(r'[\u30a0-\u30ff]', text))

async def get_or_fetch_words(session: Session, reading: str,dict_form:str) -> List[Word]:
    """
    Nếu là Katakana thì đổi sang Hiragana, sau đó tra cứu DB/API.
    """
    if len(dict_form) == 1:
        search_query = dict_form
    # 1. Logic kiểm tra và chuyển đổi
    else:
        search_query = jaconv.kata2hira(reading) if is_katakana(reading) else reading
    
    # 2. Kiểm tra DB Cache
    statement = select(Word).where(Word.reading == search_query)
    existing_words = session.exec(statement).all()
    
    if existing_words:
        return existing_words

    # 3. Gọi API nếu DB chưa có
    api_results = await fetch_api_suggestions(client, search_query)
    if not api_results:
        return []

    new_words = []
    for item in api_results:
        # Tránh trùng lặp word + reading
        existing = session.exec(
            select(Word).where(
                Word.word == item["word"], 
                Word.reading == item["kana"]
            )
        ).first()
        
        if existing:
            new_words.append(existing)
        else:
            word_entry = add_word(
                session,
                word=item["word"],
                reading=item["kana"],
                meaning=item["suggest_mean"]
            )
            new_words.append(word_entry)
            
    return new_words

async def tokenize(session: Session, text: str) -> list[Token]:
    result: list[Token] = []
    sentences = split_japanese_sentences(text)

    for sent_id, sentence in enumerate(sentences):
        for t in tokenizer_obj.tokenize(sentence, mode):
            pos_main = t.part_of_speech()[0]
            dict_form = t.dictionary_form()
            reading_raw = t.reading_form() # Thường là Katakana từ Sudachi
            
            entry = None

            if pos_main in ALLOWED_POS:
                # Chỉ lấy danh sách từ nếu thuộc loại từ cần tra
                potential_words = await get_or_fetch_words(session, reading_raw,dict_form)
                
                if potential_words:
                    # Tìm từ khớp với dictionary_form (ưu tiên Kanji)
                    match = next(
                        (w for w in potential_words if w.word == dict_form), 
                        potential_words[0]
                    )
                    
                    entry = WordEntry(
                        id=match.id,
                        word=match.word,
                        reading=match.reading,
                        meaning=match.meaning
                    )

            result.append(Token(
                sentence_id=sent_id,
                surface=t.surface(),
                normalized=t.normalized_form(),
                dictionary_form=dict_form,
                reading=reading_raw,
                pos=t.part_of_speech(),
                word_id=t.word_id(),
                begin=t.begin(),
                end=t.end(),
                entry=entry,
            ))
            
    return result