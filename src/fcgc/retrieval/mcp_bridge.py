"""Suspend at an unavailable agent tool boundary; reuse the unchanged core strategies."""

from fcgc.retrieval.query_planner import FCGQueryPlanner
from fcgc.schemas.agent import AgentAction, AgentSession, RetrievalQuery
from fcgc.schemas.models import FetchedDocument, SearchResults


class AgentRetrievalRequired(BaseException):
    """Control-flow suspension, deliberately outside core provider-error catch blocks."""

    def __init__(self, action: AgentAction):
        self.action = action


class AgentMCPRetriever:
    """No network calls. Consume validated host receipts or yield an exact typed action."""

    def __init__(self, session: AgentSession):
        self.session = session
        self.position = 0
        self.searched = 0
        self.fetched = 0
        self.known_sources = {}

    def _call(self, operation, query=None, top_k=None, source_id=None):
        self.searched += operation == "search"
        self.fetched += operation == "fetch"
        if (
            self.searched > self.session.max_search_calls
            or self.fetched > self.session.max_fetch_calls
        ):
            raise RuntimeError("Agent physical call budget exhausted")
        if self.position < len(self.session.calls):
            call = self.session.calls[self.position]
            action = call.action
            if (operation, query, top_k, source_id) != (
                action.operation,
                action.query.text if action.query else None,
                action.query.document_top_k if action.query else None,
                action.source.source_id if action.source else None,
            ):
                raise ValueError("Core requests diverged from the captured agent call sequence")
            self.position += 1
            result = call.result
            if result.error:
                error = {
                    "permission": PermissionError,
                    "authentication": PermissionError,
                    "timeout": TimeoutError,
                    "unavailable": OSError,
                    "invalid_response": ValueError,
                }[result.error.code]
                raise error(result.error.message)
            if operation == "search":
                response = SearchResults.model_validate(result.search)
                self.known_sources.update((hit.source_id, hit) for hit in response.hits)
                return response
            return FetchedDocument.model_validate(result.document)
        host = self.session.host
        version = (
            "b0-generic-v1"
            if self.session.strategy == "b0"
            else self.session.lock.config.fallback.template_version
            if self.searched > 1
            else FCGQueryPlanner().template.version
        )
        action = AgentAction(
            action_id=f"{self.session.session_id}-{self.position + 1:03}",
            session_id=self.session.session_id,
            context_hash=self.session.host_hash,
            operation=operation,
            tool_name=host.search_tool if operation == "search" else host.fetch_tool,
            query=RetrievalQuery(
                query_id=f"q{self.searched}",
                text=query,
                document_top_k=top_k,
                template_version=version,
                search_number=self.searched,
            )
            if operation == "search"
            else None,
            source=self.known_sources.get(source_id) if operation == "fetch" else None,
        )
        if operation == "fetch" and action.source is None:
            raise ValueError("Fetch was not authorized by a captured search reference")
        raise AgentRetrievalRequired(action)

    def search(self, query: str, top_k: int) -> SearchResults:
        return self._call("search", query=query, top_k=top_k)

    def fetch(self, source_id: str) -> FetchedDocument:
        return self._call("fetch", source_id=source_id)
