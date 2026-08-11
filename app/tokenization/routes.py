from fastapi import APIRouter, Query, HTTPException
from typing import Annotated, List, Optional

import ginza
import spacy

from ..container import get_db_session
from ..database.tokenization import (
    save_tokenization_history,
    get_user_tokenization_history,
    delete_tokenization_history,
)
from .schema import (
    WordLookupResponse,
    WordLookupEntry,
    TokenList,
    Token,
    DependencyTreeResponse,
    DependencyTree,
    DependencyLink,
    TokenizeDependenciesRequest,
    TokenizeDependenciesResponse,
    TokenizationHistoryItem,
    TokenizationHistoryListResponse,
)
from .tokenize import _nlp, tokenize, describe_dep, build_dependency_tree
from .dictionary import get_dictionary
from uuid import UUID

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
    sentences = build_dependency_tree(text)
    return DependencyTreeResponse(text=text, sentences=sentences)


@router.post(
    "/dependency-tree/save",
    response_model=TokenizeDependenciesResponse,
    tags=["tokenization"],
    description="Parse Japanese input text with GiNZA and build the dependency tree of each sentence, then save the analysis to the user's history (separate table) and return it",
)
async def save_dependency_tree(
    req: TokenizeDependenciesRequest,
):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")

    sentences = build_dependency_tree(req.text)

    session = get_db_session()
    history = save_tokenization_history(
        session, req.user_id, req.text, len(sentences)
    )

    return TokenizeDependenciesResponse(
        history_id=history.id,
        text=req.text,
        sentences=sentences,
    )


@router.get(
    "/dependency-tree/history",
    response_model=TokenizationHistoryListResponse,
    tags=["tokenization"],
    description="Return the current user's saved tokenization/dependency-tree history",
)
async def get_dependency_tree_history(
    user_id: Annotated[UUID, Query(..., description="User id that owns the history")],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    session = get_db_session()
    rows = get_user_tokenization_history(session, user_id, offset, limit)
    items = [
        TokenizationHistoryItem(
            history_id=r.id,
            text=r.text,
            sentences=r.sentences,
            date_created=r.date_created,
        )
        for r in rows
    ]
    return TokenizationHistoryListResponse(items=items, total=len(items))


@router.delete(
    "/dependency-tree/history/{history_id}",
    tags=["tokenization"],
    status_code=204,
    description="Delete a single entry from the current user's tokenization history",
)
async def delete_dependency_tree_history(
    history_id: UUID,
    user_id: Annotated[UUID, Query(..., description="User id that owns the history")],
):
    session = get_db_session()
    deleted = delete_tokenization_history(session, history_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="History entry not found")
    return None


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

