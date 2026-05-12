import json
import os
from typing import List, Optional, Union

import requests
from qwen_agent.tools.base import BaseTool, register_tool
from tavily import TavilyClient


SERPER_KEY = (
    os.environ.get("SERPER_API_KEY")
    or os.environ.get("SERPER_KEY_ID")
    or "YOUR_SERPER_API_KEY"
)
SERPER_BASE_URL = (os.environ.get("SERPER_BASE_URL") or "https://google.serper.dev").rstrip("/")
SEARCH_PROVIDER = os.environ.get("SEARCH_PROVIDER", "serper").strip().lower()
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")


@register_tool("search", allow_overwrite=True)
class Search(BaseTool):
    name = "search"
    description = "Performs batched web searches: supply an array 'query'; the tool retrieves the top 10 results for each query in one call."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "Array of query strings. Include multiple complementary search queries in a single call."
            },
        },
        "required": ["query"],
    }

    def __init__(self, cfg: Optional[dict] = None):
        super().__init__(cfg)
        cfg = cfg or {}
        self.filter_huggingface = bool(cfg.get("filter_huggingface", False))
        self.search_provider = str(cfg.get("search_provider") or SEARCH_PROVIDER or "serper").strip().lower()

    def google_search_with_serp(self, query: str):
        def contains_chinese_basic(text: str) -> bool:
            return any('\u4E00' <= char <= '\u9FFF' for char in text)
        if contains_chinese_basic(query):
            payload = json.dumps({
                "q": query,
                "location": "China",
                "gl": "cn",
                "hl": "zh-cn"
            })
            
        else:
            payload = json.dumps({
                "q": query,
                "location": "United States",
                "gl": "us",
                "hl": "en"
            })
        headers = {
                'X-API-KEY': SERPER_KEY,
                'Content-Type': 'application/json'
            }

        for i in range(5):
            try:
                response = requests.post(
                    f"{SERPER_BASE_URL}/search",
                    data=payload,
                    headers=headers,
                    timeout=30,
                )
                break
            except Exception as e:
                print(e)
                if i == 4:
                    return f"Google search Timeout, return None, Please try again later."
                continue

        try:
            results = response.json()
        except Exception:
            results = {"message": response.text}
        if response.status_code >= 400:
            message = results.get("message") or results.get("error") or str(results)
            return f"[Search] Serper API error {response.status_code}: {message}"

        try:
            if "organic" not in results:
                raise Exception(f"No results found for query: '{query}'. Use a less specific query.")

            web_snippets = list()
            idx = 0
            if "organic" in results:
                for page in results["organic"]:
                    link = str(page.get("link", ""))
                    if self.filter_huggingface and ("huggingface" in link.lower()):
                        continue

                    idx += 1
                    date_published = ""
                    if "date" in page:
                        date_published = "\nDate published: " + page["date"]

                    source = ""
                    if "source" in page:
                        source = "\nSource: " + page["source"]

                    snippet = ""
                    if "snippet" in page:
                        snippet = "\n" + page["snippet"]

                    redacted_version = f"{idx}. [{page['title']}]({page['link']}){date_published}{source}\n{snippet}"
                    redacted_version = redacted_version.replace("Your browser can't play this video.", "")
                    web_snippets.append(redacted_version)

            content = f"### A Google search for '{query}' found {len(web_snippets)} results:\n\n" + "\n\n".join(web_snippets)
            return content
        except:
            return f"No results found for '{query}'. Try with a more general query."


    
    def search_with_tavily(self, query: str):
        try:
            tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
            response = tavily_client.search(query=query, max_results=10)
        except Exception as e:
            print(e)
            return f"Tavily search failed for '{query}'. Please try again later."

        try:
            results = response.get("results", [])
            if not results:
                return f"No results found for '{query}'. Try with a more general query."

            web_snippets = []
            for idx, result in enumerate(results, start=1):
                url = str(result.get("url", ""))
                if self.filter_huggingface and ("huggingface" in url.lower()):
                    continue

                title = result.get("title", "")
                content = result.get("content", "")
                date_published = ""
                if result.get("published_date"):
                    date_published = "\nDate published: " + result["published_date"]

                redacted_version = f"{len(web_snippets) + 1}. [{title}]({url}){date_published}\n{content}"
                web_snippets.append(redacted_version)

            if not web_snippets:
                return f"No results found for '{query}'. Try with a more general query."

            content = f"### A Tavily search for '{query}' found {len(web_snippets)} results:\n\n" + "\n\n".join(web_snippets)
            return content
        except Exception:
            return f"No results found for '{query}'. Try with a more general query."

    def search_with_serp(self, query: str):
        result = self.google_search_with_serp(query)
        return result

    def _dispatch_search(self, query: str):
        if self.search_provider == "tavily":
            return self.search_with_tavily(query)
        return self.search_with_serp(query)

    def call(self, params: Union[str, dict], **kwargs) -> str:
        try:
            query = params["query"]
        except:
            return "[Search] Invalid request format: Input must be a JSON object containing 'query' field"
        
        if isinstance(query, str):
            response = self._dispatch_search(query)
        else:
            assert isinstance(query, List)
            responses = []
            for q in query:
                responses.append(self._dispatch_search(q))
            response = "\n---\n".join(responses)
            
        return response

if __name__ == "__main__":
    print(Search().call({"query": ['Shanghai Jiao Tong University']}))
