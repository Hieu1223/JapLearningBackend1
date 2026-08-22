from typing import List, Dict, Any, Optional, Iterator, Tuple
from functools import lru_cache
import json
import os
import heapq

import marisa_trie

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_PATH = os.path.join(_BASE_DIR, "asset", "dictionary.json")

# The trie key is "<word or kana>\t<id>\x00<payload>", where <payload> holds the
# full entry. This avoids a separate in-memory dict of entries: previously the
# code kept ``entries_by_id`` (one python dict per entry, ~90+ MB resident) on
# top of the 52 MB JSON still in memory during load, spiking to ~250 MB. With
# the data embedded in the compact trie, the resident footprint is just the
# trie itself and the large JSON is freed once loading finishes.
_INDEX_SEP = "\t"
_PAYLOAD_SEP = "\x00"
_FIELD_SEP = "\t"


def _iter_entries(path: str) -> Iterator[Dict[str, Any]]:
    """Stream entries from the JSON file without loading it all at once."""
    with open(path, "r", encoding="utf-8") as f:
        for entry in json.load(f)["api_entries"]:
            yield entry


class Dictionary:

    def __init__(self, word_list_path: str = _DEFAULT_PATH) -> None:
        word_keys: List[str] = []
        reading_keys: List[str] = []

        for entry in _iter_entries(word_list_path):
            eid = str(entry["id"])
            word = entry["word"]
            kana = entry["kana"]
            payload = (
                f"{word}{_FIELD_SEP}{kana}{_FIELD_SEP}"
                f"{entry['suggest_mean']}{_FIELD_SEP}{eid}"
            )
            word_keys.append(f"{word}{_INDEX_SEP}{eid}{_PAYLOAD_SEP}{payload}")
            reading_keys.append(f"{kana}{_INDEX_SEP}{eid}{_PAYLOAD_SEP}{payload}")

        self.word_trie = marisa_trie.Trie(word_keys)
        self.reading_trie = marisa_trie.Trie(reading_keys)

    @staticmethod
    def _to_entry(key: str) -> Dict[str, Any]:
        payload = key.split(_PAYLOAD_SEP, 1)[1]
        word, kana, meaning, eid = payload.split(_FIELD_SEP)
        return {"id": eid, "word": word, "kana": kana, "suggest_mean": meaning}

    def _iter_unique(
        self, trie: marisa_trie.Trie, prefix: str
    ) -> Iterator[Dict[str, Any]]:
        # ``iterkeys`` yields keys in DFS (lexicographic) order already, so we
        # can stream matches one at a time without materializing the whole
        # subtree. Dedup by entry id as we go.
        seen: set = set()
        for key in trie.iterkeys(prefix):
            payload = key.split(_PAYLOAD_SEP, 1)[1]
            eid = payload.rsplit(_FIELD_SEP, 1)[1]
            if eid not in seen:
                seen.add(eid)
                yield self._to_entry(key)

    def _search(
        self, trie: marisa_trie.Trie, prefix: str, max_entries: int = 20
    ) -> List[Dict[str, Any]]:
        # Keep only the ``max_entries`` shortest words seen so far in a bounded
        # min-heap keyed by word length. This bounds memory to ``max_entries``
        # entries regardless of how many keys the prefix matches.
        heap: List[Tuple[int, int, Dict[str, Any]]] = []
        for entry in self._iter_unique(trie, prefix):
            length = len(entry["word"])
            if len(heap) < max_entries:
                heapq.heappush(heap, (length, len(heap), entry))
            else:
                # Replace the longest candidate if this word is shorter.
                if length < heap[0][0]:
                    heapq.heapreplace(heap, (length, len(heap), entry))

        results = [item[2] for item in heap]
        results.sort(key=lambda e: len(e["word"]))
        return results

    def search(self, prefix: str, max_entries: int = 20) -> List[Dict[str, Any]]:
        results = self._search(self.word_trie, prefix, max_entries)
        if len(results) >= max_entries:
            return results

        remaining = max_entries - len(results)
        seen = {e["id"] for e in results}
        extra: List[Dict[str, Any]] = []
        for e in self._iter_unique(self.reading_trie, prefix):
            eid = e["id"]
            if eid not in seen:
                seen.add(eid)
                extra.append(e)
                if len(extra) >= remaining:
                    break

        # Merge word + reading results and re-rank by shortest word first.
        merged = results + extra
        merged.sort(key=lambda e: len(e["word"]))
        return merged[:max_entries]


@lru_cache(maxsize=1)
def get_dictionary() -> Dictionary:
    return Dictionary()
