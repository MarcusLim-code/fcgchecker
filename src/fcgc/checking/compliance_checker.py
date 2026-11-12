"""Canonical instruction rendering and provider-independent checker execution."""

import hashlib
import json
import re
import sysconfig
from pathlib import Path
from string import Template
from time import perf_counter

from fcgc.checking.rule_extractor import extract_documents
from fcgc.schemas.checking import (
    CheckerExecution,
    CheckingResult,
    FrozenCheckingTask,
    GenerationSettings,
    ModelFindings,
    ProviderJudgment,
    RuleFinding,
    validate_findings,
)
from fcgc.schemas.models import CheckerRequest


def instruction_assets():
    checkout = Path(__file__).resolve().parents[3] / "skills/fcg_checking"
    directory = (
        checkout
        if checkout.is_dir()
        else Path(sysconfig.get_path("data")) / ("share/fcgc/skills/fcg_checking")
    )
    skill = (directory / "SKILL.md").read_text(encoding="utf-8")
    template = (directory / "prompt.txt").read_text(encoding="utf-8")
    version = re.search(r'version:\s*"([^"]+)"', skill).group(1)
    return skill, template, version


def render_checking_prompt(task: FrozenCheckingTask) -> str:
    skill, template, _ = instruction_assets()
    return Template(template).substitute(
        skill=skill,
        schema=json.dumps(ModelFindings.model_json_schema()),
        task=task.model_input_json(),
    )


def freeze_documents(firmware, documents, context_status="complete", warnings=None):
    extractions = extract_documents(documents)
    rules = [rule for extraction in extractions for rule in extraction.rules]
    warnings = list(warnings or [])
    if any(extraction.review_sections for extraction in extractions):
        context_status = "incomplete_context"
        warnings.append("Unsegmented source sections need review.")
    ids = {rule.explicit_rule_id for rule in rules}
    for rule in rules:
        for reference in rule.dependencies:
            target = reference.target
            missing = (
                (target.startswith("SFCG-") and target not in ids)
                or (
                    target.endswith(".md")
                    and not any(doc.source_ref.endswith("/" + target) for doc in documents)
                )
                or (target.lower().startswith("section") and not rule.supporting_definitions)
            )
            if missing:
                warnings.append(f"Missing dependency: {target}")
                context_status = "incomplete_context"
    return FrozenCheckingTask(
        firmware=firmware,
        documents=documents,
        rules=rules,
        context_status=context_status,
        warnings=warnings,
    )


def unresolved(task, reason):
    return ModelFindings(
        findings=[
            RuleFinding(
                evidence_id=rule.evidence_id,
                applicability="unresolved",
                decision="unresolved",
                explanation=reason,
                uncertainty=[reason],
            )
            for rule in task.rules
        ]
    )


class CheckerUnavailable(RuntimeError):
    pass


class CanonicalChecker:
    provider = "base"
    model = "none"

    def __init__(self, settings: GenerationSettings | None = None):
        self.settings = settings or GenerationSettings()

    def predict(self, task, prompt):
        raise NotImplementedError

    def check(self, request: CheckerRequest | FrozenCheckingTask) -> CheckingResult:
        start = perf_counter()
        legacy = request if isinstance(request, CheckerRequest) else None
        task = (
            freeze_documents(request.firmware, request.retrieval.documents) if legacy else request
        )
        # Validate a fresh immutable snapshot before any provider receives data.
        task = FrozenCheckingTask.model_validate_json(task.model_dump_json())
        skill, template, version = instruction_assets()
        findings = []
        details = None
        input_tokens = output_tokens = None
        error = None
        status = "not_evaluated"
        reason = "No supported compliance judgment was produced."
        try:
            if not task.rules or task.context_status != "complete":
                prediction = unresolved(task, "No evidence or incomplete evidence context.")
            else:
                prediction, metadata, reported_input, reported_output = self.predict(
                    task, render_checking_prompt(task)
                )
                validated = ProviderJudgment(
                    prediction=prediction,
                    details=metadata,
                    input_tokens=reported_input,
                    output_tokens=reported_output,
                )
                prediction = validated.prediction
                details, input_tokens, output_tokens = (
                    validated.details,
                    validated.input_tokens,
                    validated.output_tokens,
                )
                if self.provider not in {"mock", "devin"}:
                    status = "evaluated"
            prediction = validate_findings(task, prediction)
            findings = prediction.findings
            if not any(f.decision != "unresolved" for f in findings):
                status = "not_evaluated"
            else:
                reason = (
                    "Per-rule results apply only to the supplied evidence and supported behavior."
                )
        except CheckerUnavailable as exc:
            status, reason, error = "unavailable", "Checker provider unavailable.", str(exc)
            findings = unresolved(task, reason).findings
        except (ValueError, TypeError, KeyError, NotImplementedError) as exc:
            status, reason, error = "error", "Checker response rejected.", str(exc)
            findings = unresolved(task, reason).findings
        return CheckingResult(
            status=status,
            reason=reason,
            retrieval=legacy.retrieval if legacy else None,
            findings=findings,
            execution=CheckerExecution(
                provider=self.provider,
                model=self.model,
                model_details=details,
                settings=self.settings,
                skill_version=version,
                prompt_template_version=template.splitlines()[0],
                instruction_hash=hashlib.sha256((skill + template).encode()).hexdigest(),
                prompt_hash=hashlib.sha256(render_checking_prompt(task).encode()).hexdigest(),
                input_evidence_hash=task.evidence_hash(),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=(perf_counter() - start) * 1000,
                error=error,
            ),
        )


def compare_checkers(task: FrozenCheckingTask, checkers):
    """Revalidate the same frozen bytes for each independently configured checker."""
    frozen = task.model_dump_json()
    return [checker.check(FrozenCheckingTask.model_validate_json(frozen)) for checker in checkers]


def freeze_packed_audit(payload: str) -> FrozenCheckingTask:
    from fcgc.schemas.stage6 import P2Run
    from fcgc.schemas.stage7 import P3Run

    raw = json.loads(payload)
    run = P3Run.model_validate(raw) if raw.get("strategy") == "p3" else P2Run.model_validate(raw)
    request = run.checker_request
    if request is None:
        raise ValueError("Budget-exceeded context cannot become a checking task")
    documents = run.documents if isinstance(run, P3Run) else run.p1.retrieval.documents
    return FrozenCheckingTask(
        firmware=request.firmware,
        documents=documents,
        rules=[item.rule for item in request.evidence],
        context_status=request.status,
        warnings=request.warnings,
    )
