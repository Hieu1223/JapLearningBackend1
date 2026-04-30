from typing import List, Dict, Any
import httpx

# In your dictionary helper file
async def fetch_api_suggestions(client: httpx.AsyncClient, keyword: str) -> List[Dict[str, Any]]:
    try:
        response = await client.get("/suggest", params={
            "keyword": keyword,
            "keyword_position": "start",
            "type": "word"
        })
        return response.json().get("list", [])
    except Exception as e:
        # Log error if necessary
        return []
    