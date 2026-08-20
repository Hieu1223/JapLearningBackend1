import spacy
import ginza
from typing import List, Optional
from ...tokenization.schema import Token


_nlp = None


def load_nlp():
    """Load the GiNZA/spaCy Japanese model exactly once (eagerly at startup)."""
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("ja_core_news_sm")
    return _nlp


def _ginza_tokens_with_timestamps(
    seg_text: str,
    char_start: list[Optional[float]],
    char_end: list[Optional[float]],
    sentence_id: int,
) -> list[Token]:
    """Run GiNZA on ``seg_text`` and annotate each morpheme ``Token`` with the
    WhisperX word-level timestamps taken from the overlapping characters.
    """
    doc = load_nlp()(seg_text)
    tokens: list[Token] = []
    offset = 0
    for t in doc:
        b = t.idx
        e = t.idx + len(t.text)
        window_start = char_start[b:e]
        window_end = char_end[b:e]
        starts = [s for s in window_start if s is not None]
        ends = [s for s in window_end if s is not None]
        is_root = t.head == t
        pos_parts = tuple(t.tag_.split("-")) if t.tag_ else (t.pos_,)
        tokens.append(
            Token(
                sentence_id=sentence_id,
                surface=t.text,
                normalized=t.text,
                dictionary_form=t.lemma_,
                reading=ginza.reading_form(t, use_orth_if_none=True),
                pos=pos_parts,
                word_id=hash((t.text, t.lemma_, t.pos_)) & 0x7FFFFFFF,
                begin=offset,
                end=offset + len(t.text),
                start=min(starts) if starts else None,
                stop=max(ends) if ends else None,
                dep=t.dep_ or None,
                dep_description=describe_dep(t.dep_) if t.dep_ else None,
                head_index=t.head.i if not is_root else None,
                head_surface=t.head.text if not is_root else None,
            )
        )
        offset += len(t.text)
    return tokens


def merge_transcript_tokens(segments: list) -> list[list[Token]]:
    """Tokenize each segment's text with GiNZA/spaCy and merge the morphemes
    using the WhisperX word-level timestamps.

    For every segment the WhisperX ``words`` (``{token, start, end}``) are
    concatenated to rebuild the segment text and a char->timestamp map. GiNZA
    then tokenizes that text, and each ``Token`` is assigned the min start /
    max end of the overlapping WhisperX words.

    Returns ``list[list[Token]]`` (one list of annotated Tokens per segment).
    """
    merged_per_segment: list[list[Token]] = []

    for seg_id, segment in enumerate(segments):
        words = (
            segment.get("words", [])
            if isinstance(segment, dict)
            else getattr(segment, "words", [])
        )
        seg_text = (
            segment.get("text", "")
            if isinstance(segment, dict)
            else getattr(segment, "text", "")
        )
        # Build the segment text and a parallel char->timestamp map from the
        # consecutive WhisperX words (each word token occupies len(token) chars).
        # Fall back to the segment's plain text when no word-level timestamps
        # are present, so the segment is still tokenized (timestamps just empty).
        char_start: list[Optional[float]] = []
        char_end: list[Optional[float]] = []
        for w in words:
            token = w.get("token") if isinstance(w, dict) else getattr(w, "token", None)
            start = w.get("start") if isinstance(w, dict) else getattr(w, "start", None)
            end = w.get("end") if isinstance(w, dict) else getattr(w, "end", None)
            if token is None:
                continue
            seg_text += token
            char_start.extend([start] * len(token))
            char_end.extend([end] * len(token))

        # When words are absent, tokenize the raw segment text with no timestamps.
        if not words and seg_text:
            doc = load_nlp()(seg_text)
            tokens = [
                Token(
                    sentence_id=seg_id,
                    surface=t.text,
                    normalized=t.text,
                    dictionary_form=t.lemma_,
                    reading=ginza.reading_form(t, use_orth_if_none=True),
                    pos=tuple(t.tag_.split("-")) if t.tag_ else (t.pos_,),
                    word_id=hash((t.text, t.lemma_, t.pos_)) & 0x7FFFFFFF,
                    begin=0,
                    end=0,
                    start=None,
                    stop=None,
                    dep=t.dep_ or None,
                    dep_description=describe_dep(t.dep_) if t.dep_ else None,
                    head_index=t.head.i if t.head != t else None,
                    head_surface=t.head.text if t.head != t else None,
                )
                for t in doc
            ]
            merged_per_segment.append(tokens)
            continue

        merged_per_segment.append(
            _ginza_tokens_with_timestamps(seg_text, char_start, char_end, seg_id)
        )

    return merged_per_segment


def describe_dep(dep: str) -> str:
    return DEP_DESCRIPTION.get(dep, f"unspecified dependency ({dep})")


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
