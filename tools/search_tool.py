import os
from pydantic import BaseModel
from langchain_core.tools import BaseTool

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") or "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"

class SearchInput(BaseModel):
    query: str


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Searches the web for current information on any topic. "
        "Provide a search query and get back relevant results."
    )
    args_schema: type[BaseModel] = SearchInput

    def _run(self, query: str) -> str:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=TAVILY_API_KEY)
            response = client.search(query, max_results=4)
            results = response.get("results", [])
            if not results:
                return "No results found."
            output = []
            for r in results:
                output.append(f"Title: {r['title']}\nURL: {r['url']}\nSummary: {r['content']}\n")
            return "\n".join(output)
        except Exception as e:
            return f"Search error: {str(e)}"