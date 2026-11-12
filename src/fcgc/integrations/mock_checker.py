"""Offline contract checker. Never emits a compliance prediction."""

from fcgc.checking.compliance_checker import CanonicalChecker, unresolved


class MockChecker(CanonicalChecker):
    provider = "mock"
    model = "mock-contract-v1"

    def predict(self, task, prompt):
        return unresolved(task, "Mock checker exercises contracts only."), None, None, None
