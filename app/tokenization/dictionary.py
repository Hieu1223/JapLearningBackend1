from typing import List, Dict, Any
import json


class TrieNode:
    __slots__ = ("children", "entries")

    def __init__(self):
        self.children: Dict[str, "TrieNode"] = {}
        self.entries: List[Dict[str, Any]] = []


class Dictionary:

    def __init__(self, word_list_path: str = "../asset/dictionary.json") -> None:
        self.root = TrieNode()

        with open(word_list_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for entry in data["api_entries"]:
            self._insert({
                "id": entry["id"],
                "word": entry["word"],
                "kana": entry["kana"],
                "suggest_mean": entry["suggest_mean"],
            })

    def _insert(self, entry: Dict[str, Any]) -> None:
        node = self.root

        for ch in entry["word"]:
            node = node.children.setdefault(ch, TrieNode())

        node.entries.append(entry)

    def search(self, prefix: str, max_entries: int = 20) -> List[Dict[str, Any]]:
        node = self.root

        # Traverse to the prefix node
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return []

        results: List[Dict[str, Any]] = []

        def dfs(curr: TrieNode):
            if len(results) >= max_entries:
                return

            results.extend(curr.entries)
            if len(results) >= max_entries:
                del results[max_entries:]
                return

            for child in curr.children.values():
                dfs(child)
                if len(results) >= max_entries:
                    return

        dfs(node)
        return results