import yt_dlp
import os

def download_from_url(path, url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'outtmpl': f'{path}.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

        # Get original downloaded filename
        original_file = ydl.prepare_filename(info)

        # Replace extension with processed one (wav)
        final_file = os.path.splitext(original_file)[0] + ".wav"
    return final_file


def get_video_id(url):
    proxy = (
        os.getenv("HTTPS_PROXY")
        or os.getenv("HTTP_PROXY")
        or os.getenv("ALL_PROXY")
    )
    ydl_opts = {
        'quiet': True,  # Suppress console output
        'no_warnings': True,
        'force_generic_extractor': True, # Ensures extraction works for various URLs
    }
    ydl_opts["proxy"] = proxy
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Extract info without downloading
        info_dict = ydl.extract_info(url, download=False)

        # The 'id' field contains the video ID
        video_id = info_dict.get("id", None)
        return video_id
    

def yt_search(query, max_results=5):
    """
    Search YouTube using yt-dlp with proxy from environment variables.

    Env variables supported:
    - HTTP_PROXY / HTTPS_PROXY
    - ALL_PROXY (fallback)

    Returns: list of dicts (title, url, duration, uploader)
    """

    proxy = (
        os.getenv("HTTPS_PROXY")
        or os.getenv("HTTP_PROXY")
        or os.getenv("ALL_PROXY")
    )

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,   # faster, no deep extraction
    }

    if proxy:
        ydl_opts["proxy"] = proxy

    results_data = []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        search_query = f"ytsearch{max_results}:{query}"
        info = ydl.extract_info(search_query, download=False)

        for entry in info.get("entries", []):
            results_data.append({
                "title": entry.get("title"),
                "url": entry.get("url") or entry.get("webpage_url"),
                "duration": entry.get("duration"),
                "uploader": entry.get("uploader"),
            })

    return results_data