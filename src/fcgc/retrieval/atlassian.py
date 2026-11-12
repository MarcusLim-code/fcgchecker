"""Future Atlassian MCP retrieval adapter contract."""

from fcgc.schemas.models import FetchedDocument, SearchResults


class AtlassianMCPRetriever:
    def search(self, query: str, top_k: int) -> SearchResults:
        raise NotImplementedError(
            "Atlassian MCP retrieval is not implemented; enterprise access required"
        )

    def fetch(self, source_id: str) -> FetchedDocument:
        raise NotImplementedError(
            "Atlassian MCP retrieval is not implemented; enterprise access required"
        )
