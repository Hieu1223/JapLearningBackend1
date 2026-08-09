from typing import List, Dict, Any, Optional
from functools import lru_cache
import json
import os

import marisa_trie

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_PATH = os.path.join(_BASE_DIR, "asset", "dictionary.json")


class Dictionary:

    def __init__(self, word_list_path: str = _DEFAULT_PATH) -> None:
        self.entries_by_id: Dict[str, Dict[str, Any]] = {}
        word_keys: List[str] = []
        reading_keys: List[str] = []

        with open(word_list_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for entry in data["api_entries"]:
            eid = str(entry["id"])
            self.entries_by_id[eid] = {
                "id": eid,
                "word": entry["word"],
                "kana": entry["kana"],
                "suggest_mean": entry["suggest_mean"],
            }
            word_keys.append(f'{entry["word"]}\t{eid}')
            reading_keys.append(f'{entry["kana"]}\t{eid}')

        self.word_trie = marisa_trie.Trie(word_keys)
        self.reading_trie = marisa_trie.Trie(reading_keys)

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
            _, _, eid = key.partition("\t")
            if eid not in seen:
                seen.add(eid)
                matched.append(self.entries_by_id[eid])
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
