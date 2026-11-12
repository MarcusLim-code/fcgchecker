"""Stage 1 checker explicitly does not evaluate compliance."""

from fcgc.schemas.checking import FrozenCheckingTask, GenerationSettings
from fcgc.schemas.models import CheckerRequest, CheckerResult, CheckerStatus


class PlaceholderChecker:
    def __init__(self, settings: GenerationSettings | None = None):
        self.settings = settings

    def check(self, request: CheckerRequest | FrozenCheckingTask) -> CheckerResult:
        if not isinstance(request, CheckerRequest):
            from fcgc.integrations.mock_checker import MockChecker

            return MockChecker(self.settings).check(request)
        return CheckerResult(
            status=CheckerStatus.NOT_EVALUATED,
            reason="Placeholder checker is configured; compliance was not evaluated.",
            retrieval=request.retrieval,
        )
