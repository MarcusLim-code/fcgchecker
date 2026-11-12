"""Post-hoc rule metrics. Runtime retrieval/checking never imports annotation labels."""

import itertools
import statistics


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def unique(values):
    return list(dict.fromkeys(values))


def retrieval_metrics(ranked_ids, applicable_ids, k):
    if k < 1:
        raise ValueError("Rule K must be positive")
    if len(applicable_ids) != len(set(applicable_ids)):
        raise ValueError("Duplicate ground-truth rule IDs")
    ranked = unique(ranked_ids)
    expected = set(applicable_ids)
    at_k = ranked[:k]
    relevant = expected.intersection(at_k)
    precision, recall = ratio(len(relevant), len(at_k)), ratio(len(relevant), len(expected))
    f2 = ratio(
        5 * len(relevant),
        5 * len(relevant) + 4 * (len(expected) - len(relevant)) + len(at_k) - len(relevant),
    )
    return {
        "rule_k": k,
        "ranked_ids_at_k": at_k,
        "returned_at_k": len(at_k),
        "relevant_at_k": len(relevant),
        "precision_at_k": precision,
        "recall_at_k": recall,
        "f2_at_k": f2,
        "all_applicable_present": sorted(expected.intersection(ranked)),
        "all_applicable_missing": sorted(expected.difference(ranked)),
        "all_evidence_coverage": ratio(len(expected.intersection(ranked)), len(expected)),
        "duplicate_observations_removed": len(ranked_ids) - len(ranked),
    }


def compliance_metrics(expected, predictions, *, eligible=True):
    """Strict end-to-end rule detection; abstentions are separated from wrong judgments.

    predictions: canonical rule ID, decision, and inclusive one-based code ranges.
    expected: canonical rule ID, expected_status, violation_spans.
    """
    ids = [rule["rule_id"] for rule in expected]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate ground-truth rule IDs")
    truth = {rule["rule_id"]: rule for rule in expected}
    violations = {key for key, rule in truth.items() if rule["expected_status"] == "violation"}
    ambiguous = {key for key, rule in truth.items() if rule["expected_status"] == "uncertain"}
    groups = {}
    for prediction in predictions:
        groups.setdefault(prediction["rule_id"], []).append(prediction)
    decisions = {}
    conflicts = []
    for key, rows in groups.items():
        distinct = {row["decision"] for row in rows}
        if len(distinct) > 1:
            conflicts.append(key)
        decisions[key] = next(iter(distinct)) if len(distinct) == 1 else "unresolved"
    unresolved = sorted(key for key, decision in decisions.items() if decision == "unresolved")
    missing = sorted(set(truth) - set(decisions))
    common = {
        "eligible": eligible,
        "ambiguous_ground_truth_ids": sorted(ambiguous),
        "unresolved_rule_ids": unresolved,
        "missing_prediction_ids": missing,
        "conflicting_duplicate_ids": sorted(conflicts),
        "potential_undetected_violation_ids": sorted(violations),
    }
    if not eligible:
        return {
            **common,
            **dict.fromkeys(
                [
                    "tp",
                    "fp",
                    "fn",
                    "precision",
                    "recall",
                    "f1",
                    "rule_attribution_accuracy",
                    "attribution_denominator",
                    "false_negative_ids",
                    "false_positive_ids",
                    "fn_abstained_or_missing",
                    "fn_wrong_judgment",
                ]
            ),
        }
    predicted = {key for key, decision in decisions.items() if decision == "violating"} - ambiguous
    tp, fp, fn = predicted & violations, predicted - violations, violations - predicted
    precision, recall = ratio(len(tp), len(tp) + len(fp)), ratio(len(tp), len(tp) + len(fn))
    f1 = ratio(2 * len(tp), 2 * len(tp) + len(fp) + len(fn))

    def overlaps(locations, ranges):
        return any(
            max(location["start_line"], span["start_line"])
            <= min(location["end_line"], span["end_line"])
            for location in locations
            for span in ranges
        )

    attributed = localized = 0
    all_sites = [span for key in violations for span in truth[key]["violation_spans"]]
    for key in predicted:
        locations = [location for row in groups[key] for location in row.get("locations", [])]
        if overlaps(locations, all_sites):
            localized += 1
            if key in violations and overlaps(locations, truth[key]["violation_spans"]):
                attributed += 1
    abstained = {key for key in fn if decisions.get(key, "unresolved") == "unresolved"}
    return {
        **common,
        "tp": len(tp),
        "fp": len(fp),
        "fn": len(fn),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "rule_attribution_accuracy": ratio(attributed, localized),
        "attribution_denominator": localized,
        "false_negative_ids": sorted(fn),
        "false_positive_ids": sorted(fp),
        "fn_abstained_or_missing": sorted(abstained),
        "fn_wrong_judgment": sorted(fn - abstained),
        "potential_undetected_violation_ids": sorted(fn),
    }


def set_stability(observations):
    pairs = list(itertools.combinations([set(row) for row in observations], 2))
    if not pairs:
        return None
    return statistics.mean(len(a & b) / len(a | b) if a | b else 1.0 for a, b in pairs)
