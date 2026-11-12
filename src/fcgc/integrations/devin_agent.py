"""Validate a host agent judgment; this adapter makes no Devin API call."""

import hashlib
import json

from fcgc.checking.compliance_checker import CanonicalChecker
from fcgc.schemas.agent import AgentJudgment


class DevinAgentChecker(CanonicalChecker):
    provider = "devin_agent"

    def __init__(self, judgment: AgentJudgment, *, simulated=False, settings=None):
        super().__init__(settings)
        self.judgment = judgment
        self.model = judgment.model_identifier or "unreported"
        if simulated:
            self.provider = "simulated_devin_agent"

    def predict(self, task, prompt):
        reply = self.judgment
        if reply.evidence_hash != task.evidence_hash() or (
            reply.prompt_hash != hashlib.sha256(prompt.encode()).hexdigest()
        ):
            raise ValueError("Devin judgment does not match the canonical frozen task/prompt")
        details = json.dumps(
            {
                "model_details": reply.model_details,
                "reported_settings": reply.reported_settings.model_dump()
                if reply.reported_settings
                else None,
                "configured_settings_are_requests_only": True,
                "transport": "agent-mediated JSON; no direct Devin API",
            }
        )
        return reply.findings, details, reply.input_tokens, reply.output_tokens
