from typing import Literal, Dict, List, Any
from sqlmodel import Session

# The "Source of Truth" for allowed search sorts
SortType = Literal["recently_updated", "most_viewed", "scores", "title_az"]

# Mapping dictionaries with strict Literal keys
SORT_MAPPING: Dict[str, Dict[SortType, str]] = {
    "natsu": {
        "recently_updated": "updated",
        "most_viewed": "popular",
        "scores": "rating",
        "title_az": "title",
    },
    "mangafire": {
        "recently_updated": "recently_updated",
        "most_viewed": "most_viewed",
        "scores": "scores",
        "title_az": "title_az",
    }
}