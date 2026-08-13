from typing import List, Dict, Any, Optional, Iterator
from functools import lru_cache
import json
import os

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

    def _search(
        self, trie: marisa_trie.Trie, prefix: str, max_entries: int = 20
    ) -> List[Dict[str, Any]]:
        # Cap how many keys we collect before sorting, so a very broad prefix
        # (e.g. a single character) stays cheap. The sort then promotes the
        # shortest matching words, and we return the first ``max_entries``.
        collect_cap = max(1000, max_entries * 10)

        matched: List[Dict[str, Any]] = []
        seen: set = set()
        for key in trie.iterkeys(prefix):
            payload = key.split(_PAYLOAD_SEP, 1)[1]
            eid = payload.rsplit(_FIELD_SEP, 1)[1]
            if eid not in seen:
                seen.add(eid)
                matched.append(self._to_entry(key))
                if len(matched) >= collect_cap:
                    break

        # Lowest word count (shortest word) first.
        matched.sort(key=lambda e: len(e["word"]))
        return matched[:max_entries]

    def search(self, prefix: str, max_entries: int = 20) -> List[Dict[str, Any]]:
        results = self._search(self.word_trie, prefix, max_entries)
        if len(results) >= max_entries:
            return results

        remaining = max_entries - len(results)
        seen = {e["id"] for e in results}
        extra: List[Dict[str, Any]] = []
        for e in self._search(self.reading_trie, prefix, remaining):
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
