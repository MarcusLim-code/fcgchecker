"""Bounded synthetic pointer-guard demonstration, not general C analysis."""

import re

from fcgc.checking.compliance_checker import CanonicalChecker, unresolved
from fcgc.schemas.checking import ModelFindings, RuleFinding, SupportingCitation, ViolationLocation

DEMO_RULE = "A required output pointer must be checked for null before its first write."
SHAPE = re.compile(
    r"\s*(?:#include\s*<stddef.h>\s*)?int\s+[A-Za-z_]\w*\s*"
    r"\(\s*int\s*\*\s*(?P<ptr>[A-Za-z_]\w*)\s*\)\s*\{\s*"
    r"(?P<guard>if\s*\(\s*(?P=ptr)\s*==\s*NULL\s*\)\s*return\s+-1\s*;\s*)?"
    r"(?P<write>\*\s*(?P=ptr)\s*=\s*[0-9]+\s*;)\s*return\s+0\s*;\s*\}\s*"
)


class SyntheticDemoChecker(CanonicalChecker):
    provider = "synthetic_demo"
    model = "single-pointer-store-v1"

    def predict(self, task, prompt):
        findings = unresolved(
            task, "Rule or C behavior is outside the synthetic demo subset."
        ).findings
        shape = SHAPE.fullmatch(task.firmware.content)
        for index, rule in enumerate(task.rules):
            if (
                not shape
                or rule.explicit_rule_id != "SFCG-981"
                or rule.normative_statement != DEMO_RULE
                or rule.conditions
                or rule.exceptions
                or rule.dependencies
                or rule.ambiguity_status != "clear"
            ):
                continue
            safe = shape.group("guard") is not None
            line = task.firmware.content.count("\n", 0, shape.start("write")) + 1
            findings[index] = RuleFinding(
                evidence_id=rule.evidence_id,
                applicability="applies",
                decision="compliant" if safe else "violating",
                explanation=(
                    "The supported single-pointer function has an early null guard."
                    if safe
                    else "The supported single-pointer function writes without a null guard."
                ),
                citations=[
                    SupportingCitation(
                        source_id=rule.source_id,
                        source_ref=rule.source_ref,
                        start=rule.normative_span.start,
                        end=rule.normative_span.end,
                        quote=rule.normative_statement,
                    )
                ],
                locations=[]
                if safe
                else [
                    ViolationLocation(
                        start_line=line,
                        end_line=line,
                        excerpt=task.firmware.content.splitlines()[line - 1],
                    )
                ],
            )
        return (
            ModelFindings(findings=findings),
            "Only full single-pointer-store grammar supported.",
            None,
            None,
        )
