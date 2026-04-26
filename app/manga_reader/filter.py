from urllib.parse import urlencode
from datetime import datetime


# ---------------------------
# URL Builder
# ---------------------------
class UriBuilder:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.params = []

    def add_query_parameter(self, key, value):
        self.params.append((key, value))

    def build(self):
        return f"{self.base_url}?{urlencode(self.params)}"


# ---------------------------
# Base
# ---------------------------
class UriFilter:
    def add_to_uri(self, builder: UriBuilder):
        pass


# ---------------------------
# Select (single choice)
# ---------------------------
class UriPartFilter(UriFilter):
    def __init__(self, name, param, vals, default_value=None):
        self.name = name
        self.param = param
        self.vals = vals
        self.state = 0

        for i, (_, v) in enumerate(vals):
            if v == default_value:
                self.state = i
                break

    def add_to_uri(self, builder: UriBuilder):
        builder.add_query_parameter(self.param, self.vals[self.state][1])


# ---------------------------
# Multi-select
# ---------------------------
class UriMultiSelectOption:
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.state = False


class UriMultiSelectFilter(UriFilter):
    def __init__(self, name, param, vals):
        self.name = name
        self.param = param
        self.state = [UriMultiSelectOption(n, v) for n, v in vals]

    def add_to_uri(self, builder: UriBuilder):
        for opt in self.state:
            if opt.state:
                builder.add_query_parameter(self.param, opt.value)


# ---------------------------
# Tri-state
# ---------------------------
class TriState:
    IGNORE = 0
    INCLUDE = 1
    EXCLUDE = 2


class UriTriSelectOption:
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.state = TriState.IGNORE


class UriTriSelectFilter(UriFilter):
    def __init__(self, name, param, vals):
        self.name = name
        self.param = param
        self.state = [UriTriSelectOption(n, v) for n, v in vals]

    def add_to_uri(self, builder: UriBuilder):
        for s in self.state:
            if s.state == TriState.INCLUDE:
                builder.add_query_parameter(self.param, s.value)
            elif s.state == TriState.EXCLUDE:
                builder.add_query_parameter(self.param, f"-{s.value}")


# ---------------------------
# Filters
# ---------------------------
class TypeFilter(UriMultiSelectFilter):
    def __init__(self):
        super().__init__("Type", "type", [
            ("Manga", "manga"),
            ("One-Shot", "one_shot"),
            ("Doujinshi", "doujinshi"),
            ("Novel", "novel"),
            ("Manhwa", "manhwa"),
            ("Manhua", "manhua"),
        ])


class GenreFilter(UriTriSelectFilter):
    def __init__(self):
        super().__init__("Genres", "genre[]", [
            ("Action", "1"),
            ("Adventure", "78"),
            ("Avant Garde", "3"),
            ("Boys Love", "4"),
            ("Comedy", "5"),
            ("Demons", "77"),
            ("Drama", "6"),
            ("Ecchi", "7"),
            ("Fantasy", "79"),
            ("Girls Love", "9"),
            ("Gourmet", "10"),
            ("Harem", "11"),
            ("Horror", "530"),
            ("Isekai", "13"),
            ("Iyashikei", "531"),
            ("Josei", "15"),
            ("Kids", "532"),
            ("Magic", "539"),
            ("Mahou Shoujo", "533"),
            ("Martial Arts", "534"),
            ("Mecha", "19"),
            ("Military", "535"),
            ("Music", "21"),
            ("Mystery", "22"),
            ("Parody", "23"),
            ("Psychological", "536"),
            ("Reverse Harem", "25"),
            ("Romance", "26"),
            ("School", "73"),
            ("Sci-Fi", "28"),
            ("Seinen", "537"),
            ("Shoujo", "30"),
            ("Shounen", "31"),
            ("Slice of Life", "538"),
            ("Space", "33"),
            ("Sports", "34"),
            ("Super Power", "75"),
            ("Supernatural", "76"),
            ("Suspense", "37"),
            ("Thriller", "38"),
            ("Vampire", "39"),
        ])


class GenreModeFilter(UriFilter):
    def __init__(self):
        self.state = False

    def add_to_uri(self, builder: UriBuilder):
        if self.state:
            builder.add_query_parameter("genre_mode", "and")


class StatusFilter(UriMultiSelectFilter):
    def __init__(self):
        super().__init__("Status", "status[]", [
            ("Completed", "completed"),
            ("Releasing", "releasing"),
            ("On Hiatus", "on_hiatus"),
            ("Discontinued", "discontinued"),
            ("Not Yet Published", "info"),
        ])


class YearFilter(UriMultiSelectFilter):
    def __init__(self):
        current_year = datetime.now().year

        years = []

        # last 20 years
        for y in range(current_year, current_year - 21, -1):
            years.append((str(y), str(y)))

        # decades
        for y in range(2000, 1929, -10):
            years.append((f"{y}s", f"{y}s"))

        super().__init__("Year", "year[]", years)


class MinChapterFilter(UriFilter):
    def __init__(self):
        self.state = ""

    def add_to_uri(self, builder: UriBuilder):
        if self.state:
            value = int(self.state)
            if value <= 0:
                raise ValueError("Minimum chapter must be > 0")
            builder.add_query_parameter("minchap", str(value))


class SortFilter(UriPartFilter):
    def __init__(self, default_value=None):
        super().__init__("Sort", "sort", [
            ("Most relevance", "most_relevance"),
            ("Recently updated", "recently_updated"),
            ("Recently added", "recently_added"),
            ("Release date", "release_date"),
            ("Trending", "trending"),
            ("Name A-Z", "title_az"),
            ("Scores", "scores"),
            ("MAL scores", "mal_scores"),
            ("Most viewed", "most_viewed"),
            ("Most favourited", "most_favourited"),
        ], default_value)