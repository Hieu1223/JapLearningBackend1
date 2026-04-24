from sudachipy import tokenizer
from sudachipy import dictionary
from .schema import TokenList
import re

tokenizer_obj = dictionary.Dictionary(dict='small').create()
mode = tokenizer.Tokenizer.SplitMode.C



def split_japanese_sentences(text):
    sentences = re.split(r'(?<=[。！？?])', text)
    return [s.strip() for s in sentences if s.strip()]

def tokenize(text: str):
    result = []
    sentences = split_japanese_sentences(text)

    for sent_id, sentence in enumerate(sentences):
        tokens = tokenizer_obj.tokenize(sentence, mode)

        for t in tokens:
            result.append({
                "sentence_id": sent_id,

                # core forms
                "surface": t.surface(),
                "normalized": t.normalized_form(),
                "dictionary_form": t.dictionary_form(),
                "reading": t.reading_form(),

                # POS info (full hierarchy)
                "pos": t.part_of_speech(),  # tuple of 4–5 elements

                # dictionary index (important one)
                "word_id": t.word_id(),

                # character offsets
                "begin": t.begin(),
                "end": t.end(),
            })

    return result