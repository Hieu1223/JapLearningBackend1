from sudachipy import tokenizer
from sudachipy import dictionary
from .schema import TokenList
import re

tokenizer_obj = dictionary.Dictionary(dict='small').create()
mode = tokenizer.Tokenizer.SplitMode.C


def split_japanese_sentences(text):
    sentences = re.split(r'(?<=[。！？?])', text)
    return [s.strip() for s in sentences if s.strip()]


def tokenize(text) -> TokenList:
    tokens= []
    sentences = split_japanese_sentences(text)
    for sentence in sentences:
        token = tokenizer_obj.tokenize(sentence, mode)
        tokens.extend(token)
    words = []
    noun_buffer = ""
    i = 0
    while i < len(tokens):
        m = tokens[i]
        pos = m.part_of_speech()[0]
        word = m.surface()
        if pos == "名詞":
            noun_buffer += word
            i += 1
            continue
        if noun_buffer:
            words.append(noun_buffer)
            noun_buffer = ""
        if pos == "動詞":
            merged = word
            j = i + 1
            while j < len(tokens):
                next_m = tokens[j]
                next_pos = next_m.part_of_speech()[0]
                next_word = next_m.surface()
                if next_pos in ["助詞", "助動詞", "形容詞"]:
                    merged += next_word
                    j += 1
                    continue
                break
            words.append(merged)
            i = j
            continue
        words.append(word)
        i += 1


    if noun_buffer:
        words.append(noun_buffer)
    return TokenList(tokens=words)
