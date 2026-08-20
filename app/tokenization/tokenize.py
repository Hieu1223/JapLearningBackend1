import spacy
import ginza
from typing import List, Optional
import re

from .schema import Token

_nlp = None


def load_nlp():
    """Load the GiNZA/spaCy Japanese model exactly once (eagerly at startup).

    The single shared instance is created during the FastAPI startup event so
    it never blocks app import or unrelated routes such as the Swagger UI.
    """
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("ja_core_news_sm")
    return _nlp


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


from .schema import DependencyTree, DependencyLink


def build_dependency_tree(text: str) -> list[DependencyTree]:
    """Parse Japanese text with GiNZA/spaCy and return the dependency tree of
    each sentence. Each token is linked to its head via the Universal
    Dependencies relation (dep) label.
    """
    doc = load_nlp()(text)

    sentences: list[DependencyTree] = []
    for sent_id, sent in enumerate(doc.sents):
        links: list[DependencyLink] = []
        for t in sent:
            is_root = t.head == t
            links.append(
                DependencyLink(
                    token_index=t.i,
                    surface=t.text,
                    reading=ginza.reading_form(t, use_orth_if_none=True),
                    lemma=t.lemma_,
                    pos=tuple(t.tag_.split("-")) if t.tag_ else (t.pos_,),
                    dep=t.dep_,
                    dep_description=describe_dep(t.dep_),
                    head_index=t.head.i if not is_root else None,
                    head_surface=t.head.text if not is_root else None,
                    is_root=is_root,
                )
            )
        sentences.append(
            DependencyTree(
                sentence_id=sent_id,
                text=sent.text,
                tokens=links,
            )
        )

    return sentences


async def tokenize(text: str) -> tuple[list[Token], list["DependencyTree"]]:
    return _tokenize_impl(text)


def _tokenize_impl(text: str) -> tuple[list[Token], list["DependencyTree"]]:
    """Tokenize ``text`` into morphological ``Token``s and build the GiNZA
    dependency tree of each sentence.

    GiNZA/spaCy is run for both the token list and the dependency tree so the
    two analyses stay aligned (same parser, same sentence splits). Returns a
    ``(tokens, trees)`` tuple so a single call can persist both to history or
    attach them to a transcript segment.
    """
    tokens: list[Token] = []
    sentences = split_japanese_sentences(text)

    for sent_id, sentence in enumerate(sentences):
        doc = load_nlp()(sentence)
        offset = 0
        for t in doc:
            is_root = t.head == t
            end = offset + len(t.text)
            pos_parts = tuple(t.tag_.split("-")) if t.tag_ else (t.pos_,)
            tokens.append(
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

    trees = build_dependency_tree(text)

    return tokens, trees
