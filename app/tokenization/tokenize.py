from sudachipy import tokenizer
from sudachipy import dictionary
from sqlmodel import Session
from fastapi import Depends
import re

from ..database import get_session
from ..database.dictionary.queries import look_up_word_exact
from .schema import Token, WordEntry

tokenizer_obj = dictionary.Dictionary(dict="full").create()
mode = tokenizer.Tokenizer.SplitMode.C


def split_japanese_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[。！？?])", text)
    return [s.strip() for s in sentences if s.strip()]


def tokenize(text: str, session: Session = Depends(get_session)) -> list[Token]:
    result: list[Token] = []
    sentences = split_japanese_sentences(text)

    for sent_id, sentence in enumerate(sentences):
        for t in tokenizer_obj.tokenize(sentence, mode):
            word_row = (
                look_up_word_exact(session, t.dictionary_form())
                or look_up_word_exact(session, t.surface())
            )

            entry = (
                WordEntry(
                    id=word_row.id,
                    word=word_row.word,
                    reading=word_row.reading,
                    meaning=word_row.meaning,
                )
                if word_row is not None
                else None
            )

            result.append(Token(
                sentence_id=sent_id,
                surface=t.surface(),
                normalized=t.normalized_form(),
                dictionary_form=t.dictionary_form(),
                reading=t.reading_form(),
                pos=t.part_of_speech(),
                word_id=t.word_id(),
                begin=t.begin(),
                end=t.end(),
                entry=entry,
            ))

    return result


