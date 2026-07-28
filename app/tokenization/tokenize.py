from sudachipy import tokenizer
from sudachipy import dictionary as sudachi_dictionary
from typing import List
import re

from .schema import Token

tokenizer_obj = sudachi_dictionary.Dictionary(dict="full").create()
mode = tokenizer.Tokenizer.SplitMode.C


def split_japanese_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[。！？?])", text)
    return [s.strip() for s in sentences if s.strip()]

async def tokenize(text: str) -> list[Token]:
    result: list[Token] = []
    sentences = split_japanese_sentences(text)

    for sent_id, sentence in enumerate(sentences):
        for t in tokenizer_obj.tokenize(sentence, mode):
            result.append(
                Token(
                    sentence_id=sent_id,
                    surface=t.surface(),
                    normalized=t.normalized_form(),
                    dictionary_form=t.dictionary_form(),
                    reading=t.reading_form(),
                    pos=t.part_of_speech(),
                    word_id=t.word_id(),
                    begin=t.begin(),
                    end=t.end(),
                )
            )

    return result