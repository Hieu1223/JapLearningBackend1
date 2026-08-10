import spacy
import ginza
from typing import List, Optional
import re

from .schema import Token

_nlp = spacy.load("ja_core_news_sm")


def split_japanese_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[。！？?])", text)
    return [s.strip() for s in sentences if s.strip()]


DEP_DESCRIPTION = {
    "ROOT": "root (main predicate / head of the sentence)",
    "nsubj": "nominal subject (the noun performing the action)",
    "nsubj:pass": "passive nominal subject",
    "obj": "object (the noun affected by the action)",
    "iobj": "indirect object",
    "csubj": "clausal subject",
    "csubj:pass": "passive clausal subject",
    "ccomp": "clausal complement",
    "xcomp": "open clausal complement",
    "obl": "oblique nominal (adverbial-like argument)",
    "obl:agent": "agent of a passive verb",
    "vocative": "vocative (direct address)",
    "expl": "expletive / pleonastic subject",
    "dislocated": "dislocated element",
    "advcl": "adverbial clause modifier",
    "advmod": "adverbial modifier",
    "amod": "adjectival modifier",
    "nummod": "numeric modifier",
    "nounmod": "noun modifier (genitive/possessive)",
    "nmod": "nominal modifier",
    "appos": "appositional modifier",
    "compound": "compound word element",
    "flat": "flat multiword expression",
    "fixed": "fixed multiword expression",
    "acl": "adjectival clause",
    "acl:relcl": "relative clause modifier",
    "det": "determiner",
    "clf": "classifier",
    "case": "case marker (particle marking a dependency)",
    "mark": "marker (subordinating/dependency-marking particle)",
    "aux": "auxiliary verb",
    "aux:pass": "passive auxiliary",
    "cop": "copula",
    "punct": "punctuation",
    "conj": "conjunct (coordinated element)",
    "cc": "coordinating conjunction",
    "list": "list element",
    "discourse": "discourse element (interjection, etc.)",
    "parataxis": "parataxis (loosely attached clause)",
    "orphan": "orphan (elided head dependency)",
    "goeswith": "goes with (unconventional token split)",
    "reparandum": "overridden disfluency",
    "dep": "unspecified dependency",
    "root": "root (main predicate / head of the sentence)",
}


def describe_dep(dep: str) -> str:
    return DEP_DESCRIPTION.get(dep, f"unspecified dependency ({dep})")


async def tokenize(text: str) -> list[Token]:
    result: list[Token] = []
    sentences = split_japanese_sentences(text)

    for sent_id, sentence in enumerate(sentences):
        doc = _nlp(sentence)
        offset = 0
        for t in doc:
            is_root = t.head == t
            end = offset + len(t.text)
            pos_parts = tuple(t.tag_.split("-")) if t.tag_ else (t.pos_,)
            result.append(
                Token(
                    sentence_id=sent_id,
                    surface=t.text,
                    normalized=t.text,
                    dictionary_form=t.lemma_,
                    reading=ginza.reading_form(t, use_orth_if_none=True),
                    pos=pos_parts,
                    word_id=hash((t.text, t.lemma_, t.pos_)) & 0x7FFFFFFF,
                    begin=offset,
                    end=end,
                    dep=t.dep_ or None,
                    dep_description=describe_dep(t.dep_) if t.dep_ else None,
                    head_index=t.head.i if not is_root else None,
                    head_surface=t.head.text if not is_root else None,
                )
            )
            offset = end

    return result


def merge_transcript_tokens(segments: list) -> list[list[dict]]:
    """Tokenize each segment's text with GiNZA/spaCy and merge the morphemes
    using the WhisperX word-level timestamps.

    For every segment the WhisperX ``words`` (``{token, start, end}``) are
    concatenated to rebuild the segment text and a char->timestamp map. GiNZA
    then tokenizes that text, and each token is assigned the min start / max end
    of the overlapping WhisperX words.

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

        doc = _nlp(seg_text)
        seg_merged: list[dict] = []
        for t in doc:
            b = t.idx
            e = t.idx + len(t.text)
            window_start = char_start[b:e]
            window_end = char_end[b:e]
            starts = [s for s in window_start if s is not None]
            ends = [s for s in window_end if s is not None]
            seg_merged.append(
                {
                    "token": t.text,
                    "start": min(starts) if starts else None,
                    "end": max(ends) if ends else None,
                }
            )

        merged_per_segment.append(seg_merged)

    return merged_per_segment
