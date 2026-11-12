"""Persist bounded agent handoffs and resume the existing strategy/checking executor."""

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fcgc import __version__
from fcgc.agent.skills import orchestration_hash
from fcgc.checking.compliance_checker import instruction_assets, render_checking_prompt
from fcgc.checking.context_packer import estimate_tokens
from fcgc.checking.context_reducer import load_reduction_config
from fcgc.checking.feature_extractor import extract_features
from fcgc.checking.function_scope import function_location
from fcgc.config import Settings, make_retriever
from fcgc.experiments.runner import code_hash, execute_checkers, perform_run
from fcgc.experiments.snapshots import RecordingRetriever, RetrievalSnapshot, digest
from fcgc.integrations.devin_agent import DevinAgentChecker
from fcgc.integrations.mock_checker import MockChecker
from fcgc.retrieval.adaptive_retrieval import load_fallback_config
from fcgc.retrieval.baseline import load_firmware
from fcgc.retrieval.mcp_bridge import AgentMCPRetriever, AgentRetrievalRequired
from fcgc.schemas.agent import (
    AgentAction,
    AgentJudgment,
    AgentSession,
    AgentToolResult,
    CompletedCall,
    FunctionTarget,
    HostContext,
    validate_source_uri,
)
from fcgc.schemas.checking import validate_findings
from fcgc.schemas.stage9 import ArtifactLock, PipelineConfig

HANDOFF_LIMIT = 2_000_000
SESSION_LIMIT = 128_000_000


def read_json(path: Path, limit=HANDOFF_LIMIT):
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Agent handoff exceeds the configured byte limit")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key in agent handoff")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=pairs)


def private_write(path: Path, value, *, as_text=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Refusing to write through an audit-file symlink")
    payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    temp = path.with_name(path.name + ".tmp")
    # O_EXCL rejects symlinks/stale temporary writers instead of following them.
    descriptor = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            if as_text:
                stream.write(value)
            else:
                json.dump(payload, stream, indent=2, allow_nan=False, ensure_ascii=False)
            stream.write("\n")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _focus(session, task):
    if not session.target:
        return task
    target = session.target
    return task.model_copy(
        update={
            "target_function": target.name,
            "target_start_line": target.start_line,
            "target_end_line": target.end_line,
            "warnings": [
                *task.warnings,
                f"Check function {target.name} at original lines "
                f"{target.start_line}-{target.end_line}. Other code is supporting context. "
                "Feature extraction remains conservative over the whole file.",
            ],
        }
    )


def start_session(
    source: Path,
    output: Path,
    *,
    mode="local",
    strategy="p3",
    intent="check",
    settings: Settings | None = None,
    function=None,
    host: HostContext | None = None,
    allow_synthetic_handoff=False,
    top_k=None,
    token_budget=12000,
    elapsed_seconds=600,
):
    if output.exists():
        raise ValueError("Agent output must be a fresh directory")
    source, output = source.resolve(), output.resolve()
    firmware = load_firmware(source, source.stem)
    if len(firmware.content.encode()) > 1_000_000:
        raise ValueError("Agent artifact exceeds 1 MB; use the core CLI for larger artifacts")
    settings = settings or Settings(
        retriever="agent_mcp" if mode == "wd" else "benchmark",
        checker="devin" if mode == "wd" else "mock",
    )
    if mode == "wd":
        if settings.checker == "ollama" and settings.allow_remote:
            raise ValueError(
                "WD evidence export to remote checkers requires a future approved export adapter"
            )
        if settings.retriever != "agent_mcp":
            raise ValueError(
                "WD mode requires agent_mcp; synthetic/direct-provider substitution is forbidden"
            )
        if host is None or host.connection_status != "connected_but_unverified":
            raise ValueError(
                "WD handoff not configured: discover existing authorized tools in this host first"
            )
        if host.origin == "synthetic_contract_test" and not allow_synthetic_handoff:
            raise ValueError(
                "Synthetic handoffs require explicit test opt-in; they are never live verification"
            )
        if host.origin == "host_observed" and host.runtime == "other":
            raise ValueError("WD orchestration requires an identified Devin host")
        approved = host.approved_workspace.resolve()
        host = host.model_copy(update={"approved_workspace": approved})
        if not source.is_relative_to(approved) or not output.is_relative_to(approved):
            raise ValueError("WD source and audit output must stay in the approved host workspace")
    elif host is not None or settings.retriever not in {"local", "benchmark", "replay"}:
        raise ValueError("Local mode requires a fixture/replay provider and no WD host handoff")
    if settings.checker == "devin" and mode != "wd":
        raise ValueError("An active Devin checker handoff requires WD mode")
    skill, template, version = instruction_assets()
    fallback = load_fallback_config()
    config = PipelineConfig(
        retrieval=settings,
        checkers=[settings],
        document_top_k=top_k if top_k is not None else settings.top_k,
        context_token_budget=token_budget,
        expected_skill_version=version,
        expected_prompt_version=template.splitlines()[0],
        reduction=load_reduction_config(),
        fallback=(
            fallback.model_copy(update={"max_elapsed_seconds": elapsed_seconds})
            if mode == "wd"
            else fallback
        ),
    )
    if elapsed_seconds <= 0 or elapsed_seconds > 3600:
        raise ValueError("Agent workflow deadline must be in (0, 3600] seconds")
    if config.document_top_k > fallback.max_fetch_calls or config.document_top_k > 100:
        raise ValueError("Document K exceeds the bounded agent fetch budget")
    target = None
    if function:
        first, last = function_location(firmware, function)
        target = FunctionTarget(name=function, start_line=first, end_line=last)
    started = datetime.now(UTC)
    session = AgentSession(
        session_id=str(uuid4()),
        source_path=source,
        source_hash=firmware.sha256,
        features=extract_features(firmware),
        feature_role="diagnostic_only" if strategy == "b0" else "runtime_equivalent",
        mode=mode,
        intent=intent,
        strategy=strategy,
        started_at=started,
        deadline=started + timedelta(seconds=elapsed_seconds),
        host=host,
        host_hash=digest(host.model_dump(mode="json")) if host else "local",
        orchestration_sha256=orchestration_hash(),
        lock=ArtifactLock(
            config=config,
            code_version=__version__,
            code_hash=code_hash(),
            instruction_hash=hashlib.sha256((skill + template).encode()).hexdigest(),
        ),
        target=target,
        max_search_calls=fallback.max_search_calls if strategy == "p3" else 1,
        max_fetch_calls=fallback.max_fetch_calls if strategy == "p3" else config.document_top_k,
        max_candidate_sources=fallback.max_candidate_sources
        if strategy == "p3"
        else config.document_top_k,
        status="retrieval_required",
    )
    output.mkdir(parents=True, mode=0o700)
    private_write(output / "lock.json", session.lock)
    return advance(session, output)


def load_session(directory: Path):
    session = AgentSession.model_validate(read_json(directory / "session.json", SESSION_LIMIT))
    if session.host and not directory.resolve().is_relative_to(session.host.approved_workspace):
        raise ValueError("WD audit storage moved outside the approved host workspace")
    if session.orchestration_sha256 != orchestration_hash():
        raise ValueError("Agent orchestration skills changed; start a fresh session")
    skill, template, _ = instruction_assets()
    if (
        session.lock.code_hash != code_hash()
        or session.lock.instruction_hash != hashlib.sha256((skill + template).encode()).hexdigest()
    ):
        raise ValueError("Agent code/instructions changed; start a fresh session")
    if json.loads((directory / "lock.json").read_text()) != session.lock.model_dump(mode="json"):
        raise ValueError("Agent configuration lock changed")
    if session.host and session.host_hash != digest(session.host.model_dump(mode="json")):
        raise ValueError("Agent host context changed")
    for index, call in enumerate(session.calls, 1):
        persisted = AgentToolResult.model_validate(
            read_json(directory / "handoffs" / f"{index:03}.json", SESSION_LIMIT)
        )
        if persisted != call.result:
            raise ValueError("Agent handoff receipt differs from the persisted session")
    if load_firmware(session.source_path, session.source_path.stem).sha256 != session.source_hash:
        raise ValueError("Firmware changed during the read-only agent workflow")
    return session


def advance(session: AgentSession, output: Path):
    start = perf_counter()
    if datetime.now(UTC) >= session.deadline:
        session.status, session.pending = "error", None
        session.warnings.append("Agent wall-time budget exhausted; evidence/checking incomplete")
        return save_session(session, output)
    if (
        session.mode == "wd"
        and session.calls
        and session.calls[-1].result.error
        and (session.calls[-1].result.error.code in {"authentication", "permission"})
    ):
        session.status, session.pending = "error", None
        session.warnings.append(
            "Existing MCP access denied; no authentication recreation or synthetic fallback"
        )
        return save_session(session, output)
    recorder = RecordingRetriever(
        AgentMCPRetriever(session)
        if session.mode == "wd"
        else make_retriever(session.lock.config.retrieval)
    )
    firmware = load_firmware(session.source_path, session.source_path.stem)
    try:
        trace = perform_run(
            session.lock,
            firmware,
            session.strategy,
            1,
            session.session_id,
            recorder,
            checkers_enabled=False,
            task_transform=lambda task: _focus(session, task),
        )
    except AgentRetrievalRequired as suspended:
        session.pending, session.status = suspended.action, "retrieval_required"
        session.backend_processing_ms += (perf_counter() - start) * 1000
        return save_session(session, output)
    session.trace, session.pending = trace, None
    trace.traffic_kind = (
        "synthetic_contract_test"
        if session.host and session.host.origin == "synthetic_contract_test"
        else "agent_mediated_mcp_unverified"
        if session.mode == "wd"
        else "local_fixture"
    )
    if trace.task and any(not call.result.complete or call.result.error for call in session.calls):
        trace.task = trace.task.model_copy(
            update={
                "context_status": "incomplete_context",
                "warnings": [
                    *trace.task.warnings,
                    "Agent retrieval included incomplete/error responses",
                ],
            }
        )
        trace.incomplete_stages.append("agent_retrieval")
        trace.packed_checker_input = render_checking_prompt(trace.task)
        trace.checker_input_estimated_tokens = estimate_tokens(trace.packed_checker_input)
    if trace.task and session.intent == "check":
        if session.lock.config.checkers[0].checker == "devin":
            if (
                trace.task.rules
                and trace.task.context_status == "complete"
                and trace.status != "failed"
            ):
                session.pending = AgentAction(
                    action_id=session.session_id + "-check",
                    session_id=session.session_id,
                    context_hash=session.host_hash,
                    operation="check",
                    evidence_hash=trace.task.evidence_hash(),
                    prompt_hash=hashlib.sha256(trace.packed_checker_input.encode()).hexdigest(),
                )
                session.status = "checking_required"
            else:
                trace.checker_results = [MockChecker().check(trace.task)]
                session.status = "complete" if trace.status != "failed" else "error"
        else:
            execute_checkers(trace, session.lock.config)
            if trace.errors:
                trace.status = "failed"
            session.status = "error" if trace.errors else "complete"
    else:
        session.status = "error" if trace.status == "failed" else "complete"
    session.backend_processing_ms += (perf_counter() - start) * 1000
    if session.mode == "local":
        private_write(
            output / "retrieval-snapshot.json",
            RetrievalSnapshot(
                approved=True,
                provider=session.lock.config.retrieval.retriever,
                corpus_hash=digest(trace.source_content_hashes),
                calls=trace.tool_calls,
            ),
        )
    return save_session(session, output)


def submit_result(directory: Path, payload: Path):
    session = load_session(directory)
    if session.status not in {"retrieval_required", "checking_required"} or session.pending is None:
        raise ValueError("Session has no pending handoff")
    raw = read_json(payload)
    action = session.pending
    if action.operation == "check":
        reply = AgentJudgment.model_validate(raw)
        if (
            reply.session_id,
            reply.action_id,
            reply.context_hash,
            reply.evidence_hash,
            reply.prompt_hash,
        ) != (
            session.session_id,
            action.action_id,
            session.host_hash,
            action.evidence_hash,
            action.prompt_hash,
        ):
            raise ValueError("Checker handoff identity/hash mismatch")
        if datetime.now(UTC) >= session.deadline:
            session.status, session.pending = "error", None
            session.warnings.append("Agent wall-time budget exhausted before checker submission")
            return save_session(session, directory)
        # Reject fabricated/partial citations before persisting an alleged successful result.
        validate_findings(session.trace.task, reply.findings)
        checker = DevinAgentChecker(
            reply,
            simulated=session.host.origin == "synthetic_contract_test",
            settings=session.lock.config.checkers[0].generation,
        )
        result = checker.check(session.trace.task)
        session.judgment = reply
        session.trace.checker_results = [result]
        session.status, session.pending = (
            ("error" if result.status == "error" else "complete"),
            None,
        )
        return save_session(session, directory)
    reply = AgentToolResult.model_validate(raw)
    if (
        reply.session_id,
        reply.action_id,
        reply.context_hash,
        reply.provider_id,
        reply.tool_name,
    ) != (
        session.session_id,
        action.action_id,
        session.host_hash,
        session.host.provider_id,
        action.tool_name,
    ):
        raise ValueError("Tool handoff identity/environment/provider mismatch")
    if reply.retrieved_at < session.started_at or reply.retrieved_at > datetime.now(
        UTC
    ) + timedelta(seconds=60):
        raise ValueError("Tool result timestamp is outside this agent session")
    if reply.search:
        if action.operation != "search" or reply.search.query != action.query.text:
            raise ValueError("Search response does not match the requested query")
        hits = reply.search.hits
        if any(
            len(value) > 4096
            for hit in hits
            for value in (hit.source_id, hit.source_ref, hit.title)
        ):
            raise ValueError("Source identity exceeds the agent handoff field limit")
        if len(hits) > action.query.document_top_k or len({h.source_id for h in hits}) != len(hits):
            raise ValueError("Search response exceeds Top-K or has duplicate source identifiers")
        if reply.search.scope != session.lock.config.retrieval.scope:
            raise ValueError("Search permissions/scope differs from the locked configuration")
        prior = {
            hit.source_id: hit
            for call in session.calls
            if call.result.search
            for hit in call.result.search.hits
        }
        for hit in hits:
            if hit.source_id in prior and (
                prior[hit.source_id].source_ref,
                prior[hit.source_id].title,
            ) != (hit.source_ref, hit.title):
                raise ValueError("Source identity changed between retrieval rounds")
        if len(set(prior) | {h.source_id for h in hits}) > session.max_candidate_sources:
            raise ValueError("Agent candidate-source budget exceeded")
    if reply.document:
        if "\x00" in reply.document.content or not reply.document.content.strip():
            raise ValueError("Fetched document is empty or contains NUL bytes")
        if action.operation != "fetch" or (
            reply.document.source_id,
            reply.document.source_ref,
            reply.document.title,
        ) != (action.source.source_id, action.source.source_ref, action.source.title):
            raise ValueError("Fetched document identity differs from the selected search reference")
    if session.host.origin == "host_observed":
        for ref in (
            [hit.source_ref for hit in reply.search.hits]
            if reply.search
            else [reply.document.source_ref]
            if reply.document
            else []
        ):
            validate_source_uri(ref)
    session.calls.append(CompletedCall(action=action, result=reply))
    private_write(directory / "handoffs" / f"{len(session.calls):03}.json", reply)
    session.pending = None
    return advance(session, directory)


def save_session(session, output):
    session.workflow_ms = (datetime.now(UTC) - session.started_at).total_seconds() * 1000
    private_write(output / "session.json", session)
    if session.pending:
        private_write(output / "action.json", session.pending)
    else:
        (output / "action.json").unlink(missing_ok=True)
    if session.trace:
        private_write(output / "trace.json", session.trace)
        if session.trace.task:
            private_write(output / "task.json", session.trace.task)
            private_write(
                output / "checker-prompt.json", {"prompt": session.trace.packed_checker_input}
            )
    result = summary(session, output)
    private_write(output / "result.json", result)
    private_write(output / "report.md", render_report(session, result), as_text=True)
    return result


def summary(session, output):
    trace = session.trace
    results = trace.checker_results if trace else []
    return {
        "version": "fcgc-agent-result-v1",
        "session_id": session.session_id,
        "status": session.status,
        "mode": session.mode,
        "strategy": session.strategy,
        "source": str(session.source_path),
        "function": session.target.model_dump() if session.target else None,
        "retrieval_provider": session.lock.config.retrieval.retriever,
        "checker_status": str(results[0].status) if results else "not_evaluated",
        "configured_checker": session.lock.config.checkers[0].checker,
        "configuration_hash": digest(session.lock.config.model_dump(mode="json")),
        "rules_evaluated": sum(
            f.decision in {"compliant", "violating", "not_applicable"}
            for checked in results
            for f in checked.findings
        ),
        "violations_found": sum(
            f.decision == "violating" for checked in results for f in checked.findings
        ),
        "unresolved_checks": sum(
            f.decision == "unresolved" for checked in results for f in checked.findings
        ),
        "findings": [f.model_dump(mode="json") for checked in results for f in checked.findings],
        "severity": None,
        "latency_scope": "Core trace times measure the final receipt-replay pass; "
        "cumulative backend "
        "processing and agent workflow wall time are recorded separately.",
        "evidence_status": trace.task.context_status
        if trace and trace.task
        else "pending_or_unavailable",
        "live_access_verified_by_python": False,
        "capture_origin": session.host.origin if session.host else "synthetic_fixture",
        "action": session.pending.model_dump(mode="json") if session.pending else None,
        "counts": {
            "search_calls": sum(c.action.operation == "search" for c in session.calls)
            if session.mode == "wd"
            else sum(c.operation == "search" for c in trace.tool_calls)
            if trace
            else 0,
            "fetch_calls": sum(c.action.operation == "fetch" for c in session.calls)
            if session.mode == "wd"
            else sum(c.operation == "fetch" for c in trace.tool_calls)
            if trace
            else 0,
            "transport_retries": 0,
        },
        "workflow_ms": session.workflow_ms,
        "backend_processing_ms": session.backend_processing_ms,
        "host_tool_duration_ms": sum(c.result.duration_ms for c in session.calls)
        if session.calls and all(c.result.duration_ms is not None for c in session.calls)
        else None,
        "input_estimated_tokens": trace.checker_input_estimated_tokens if trace else None,
        "token_method": "regex-word-punctuation-v1",
        "billed_tokens": None,
        "rovo_credits": None,
        "warnings": session.warnings + (trace.task.warnings if trace and trace.task else []),
        "audit": str(output / "session.json"),
        "report": str(output / "report.md"),
    }


def render_report(session, result):
    trace = session.trace
    function = session.target.name if session.target else "whole artifact"
    title = "FCG Compliance Report" if session.intent == "check" else "FCG Rule Evidence Inspection"
    lines = [
        "# " + title,
        "",
        f"File: `{session.source_path}`. Function: `{function}`.",
        f"Mode/strategy: {session.mode}/{session.strategy}.",
        f"Retrieval: {result['retrieval_provider']}. Workflow: {session.status}.",
        f"Checker: {result['checker_status']}. Evidence: {result['evidence_status']}.",
        "Host-attested capture; Python does not independently authenticate live MCP access.",
        "Judgments cover supplied evidence only; no corpus-wide compliance claim.",
        "",
    ]
    if trace:
        for checked in trace.checker_results:
            lines.append(f"Checker: {checked.execution.provider}/{checked.execution.model}.")
            for finding in checked.findings:
                rule = next(r for r in trace.task.rules if r.evidence_id == finding.evidence_id)
                lines.extend(
                    [
                        f"- {rule.explicit_rule_id or rule.evidence_id}: "
                        f"{finding.applicability}/{finding.decision}; {finding.explanation}",
                        f"  Source: {rule.source_ref}; original lines "
                        f"{rule.normative_span.start_line}-{rule.normative_span.end_line}.",
                    ]
                )
                lines.extend(
                    f"  Code lines {loc.start_line}-{loc.end_line}: `{loc.excerpt}`"
                    for loc in finding.locations
                )
                lines.extend(f"  Condition: {part.span.excerpt}" for part in rule.conditions)
                lines.extend(f"  Exception: {part.span.excerpt}" for part in rule.exceptions)
        if session.intent == "rules" and trace.pipeline:
            selection = getattr(trace.pipeline, "selection", None)
            decisions = {d.evidence_id: d for d in selection.decisions} if selection else {}
            for rule in [r for ex in trace.segmented_documents for r in ex.rules]:
                decision = decisions.get(rule.evidence_id)
                label = rule.explicit_rule_id or rule.evidence_id
                lines.extend(
                    [
                        f"- {label}: {rule.normative_statement}",
                        f"  {rule.source_ref}; {rule.ambiguity_status}; "
                        f"retained={rule.evidence_id in trace.selected_ids}.",
                    ]
                )
                if decision:
                    lines.append(f"  Selection: {decision.reason_codes}; {decision.explanation}")
                lines.extend(
                    f"  {part.kind}: {part.span.excerpt}"
                    for part in rule.conditions + rule.exceptions + rule.supporting_definitions
                )
                lines.extend(f"  Dependency: {part.target}" for part in rule.dependencies)
    counts = result["counts"]
    tokens = result["input_estimated_tokens"]
    lines.extend(
        [
            "",
            "Severity: unavailable without an authoritative requirement "
            "or explicit project policy.",
            f"Calls: {counts}; estimated input tokens={tokens}.",
            f"Workflow ms={session.workflow_ms:.2f}; this includes agent/human waiting time.",
            f"Audit: `{result['audit']}`.",
            "",
            *["- Warning: " + w for w in result["warnings"]],
        ]
    )
    return "\n".join(lines) + "\n"
