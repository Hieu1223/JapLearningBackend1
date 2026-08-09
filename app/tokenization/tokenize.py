from sudachipy import tokenizer
from sudachipy import dictionary as sudachi_dictionary
from typing import List, Optional
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


def merge_transcript_tokens(segments: list) -> list[list[dict]]:
    """Tokenize each segment's text with Sudachi and merge the morphemes using
    the WhisperX word-level timestamps.

    For every segment the WhisperX ``words`` (``{token, start, end}``) are
    concatenated to rebuild the segment text and a char->timestamp map. Sudachi
    (current setting: full dictionary, SplitMode.C) then tokenizes that text,
    and each Sudachi morpheme is assigned the min start / max end of the
    overlapping WhisperX words.

    Returns a list (one per segment) of merged ``TokenTimestamp`` dicts
    (``{token, start, end}``) in the same shape as the original ``words``.
    """
    merged_per_segment: list[list[dict]] = []

    for segment in segments:
        words = (
            segment.get("words", [])
            if isinstance(segment, dict)
            else getattr(segment, "words", [])
        )
        # Build the segment text and a parallel char->timestamp map from the
        # consecutive WhisperX words (each word token occupies len(token) chars).
        seg_text = ""
        char_start: list[Optional[float]] = []
        char_end: list[Optional[float]] = []
        for w in words:
            token = w.get("token") if isinstance(w, dict) else getattr(w, "token", None)
            start = w.get("start") if isinstance(w, dict) else getattr(w, "start", None)
            end = w.get("end") if isinstance(w, dict) else getattr(w, "end", None)
            seg_text += token
            char_start.extend([start] * len(token))
            char_end.extend([end] * len(token))

        seg_merged: list[dict] = []
        for t in tokenizer_obj.tokenize(seg_text, mode):
            surface = t.surface()
            b = t.begin()
            e = t.end()
            window_start = char_start[b:e]
            window_end = char_end[b:e]
            starts = [s for s in window_start if s is not None]
            ends = [s for s in window_end if s is not None]
            seg_merged.append(
                {
                    "token": surface,
                    "start": min(starts) if starts else None,
                    "end": max(ends) if ends else None,
                }
            )

        merged_per_segment.append(seg_merged)

    return merged_per_segment

