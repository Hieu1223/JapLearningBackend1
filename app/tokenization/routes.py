from fastapi import APIRouter, Query
from typing import Annotated, List, Optional

import ginza

from .schema import (
    WordLookupResponse,
    WordLookupEntry,
    TokenList,
    Token,
    DependencyTreeResponse,
    DependencyTree,
    DependencyLink,
)
from .tokenize import _nlp, tokenize, describe_dep
from .dictionary import get_dictionary

router = APIRouter(tags=["tokenization"])


@router.get("/tokenize", response_model=TokenList, tags=["tokenization"], description="Split Japanese input text into morphological tokens for further lookup or study")
async def tokenize_endpoint(
    text: Annotated[str, Query(..., min_length=1)],
):
    tokens = await tokenize(text)
    return TokenList(tokens=tokens)

# GiNZA uses Universal Dependencies labels; map them to descriptive text.
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


@router.get(
    "/dependency-tree",
    response_model=DependencyTreeResponse,
    tags=["tokenization"],
    description="Parse Japanese input text with GiNZA/spaCy and return the dependency tree of each sentence, including the dependency relation (dep) that links each token to its head",
)
async def dependency_tree_endpoint(
    text: Annotated[str, Query(..., min_length=1)],
):
    doc = _nlp(text)

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

    return DependencyTreeResponse(text=text, sentences=sentences)


@router.get("/dictionary/words/lookup", response_model=WordLookupResponse, tags=["tokenization"], description="Search the Japanese dictionary by word or reading and return matching entries with meanings")
def lookup_words(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
):
    dictionary = get_dictionary()
    results = dictionary.search(q, limit)
    entries = [
        WordLookupEntry(
            id=e["id"],
            word=e["word"],
            reading=e["kana"],
            meaning=e["suggest_mean"],
        )
        for e in results
    ]
    return WordLookupResponse(query=q, results=entries, total=len(entries))

