"""Case/group-cluster statistics; repetitions never become independent samples."""

import itertools
import math
import random
import statistics


def quantile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def describe(values):
    values = [v for v in values if v is not None]
    if not values:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "sd": None,
            "iqr": None,
            "min": None,
            "max": None,
        }
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "sd": statistics.stdev(values) if len(values) > 1 else None,
        "iqr": quantile(values, 0.75) - quantile(values, 0.25),
        "min": min(values),
        "max": max(values),
    }


def paired_statistics(case_differences, groups, samples=2000, seed=0):
    grouped = {}
    for case in sorted(case_differences):
        grouped.setdefault(groups[case], []).append(case_differences[case])
    grouped = {key: grouped[key] for key in sorted(grouped)}
    values = [statistics.mean(value) for value in grouped.values()]
    output = {
        "case_count": len(case_differences),
        "independent_cluster_count": len(values),
        "case_deltas": case_differences,
        "cluster_deltas": dict(zip(grouped, values, strict=True)),
        "delta_summary": describe(values),
        "ci95_mean_delta": None,
        "paired_dz": None,
        "sign_test_p": None,
        "sign_flip_p": None,
        "test_method": "not enough independent matched groups",
    }
    if len(values) < 2:
        return output
    sd = statistics.stdev(values)
    mean = statistics.mean(values)
    output["paired_dz"] = mean / sd if sd else None
    rng = random.Random(seed)
    boot = [statistics.mean(rng.choices(values, k=len(values))) for _ in range(samples)]
    output["ci95_mean_delta"] = [quantile(boot, 0.025), quantile(boot, 0.975)]
    nonzero = [v for v in values if abs(v) > 1e-12]
    if nonzero:
        n = len(nonzero)
        minority = min(sum(v > 0 for v in nonzero), sum(v < 0 for v in nonzero))
        output["sign_test_p"] = min(
            1.0, 2 * sum(math.comb(n, i) for i in range(minority + 1)) / 2**n
        )
    else:
        output["sign_test_p"] = 1.0
    observed = abs(mean)
    if len(values) <= 16:
        distribution = [
            abs(statistics.mean(v * s for v, s in zip(values, signs, strict=True)))
            for signs in itertools.product((-1, 1), repeat=len(values))
        ]
        output["sign_flip_p"] = sum(v >= observed - 1e-12 for v in distribution) / len(distribution)
        output["test_method"] = (
            "exact cluster sign-flip; symmetry assumption; exact sign test also reported"
        )
    else:
        extreme = sum(
            abs(statistics.mean(v * rng.choice((-1, 1)) for v in values)) >= observed - 1e-12
            for _ in range(samples)
        )
        output["sign_flip_p"] = (extreme + 1) / (samples + 1)
        output["test_method"] = "Monte Carlo cluster sign-flip with +1 correction"
    return output


def holm(values):
    """Map hypothesis keys to Holm-adjusted p-values within one metric/panel family."""
    ordered = sorted((value, key) for key, value in values.items() if value is not None)
    result, previous = {}, 0.0
    for index, (p, key) in enumerate(ordered):
        previous = max(previous, min(1.0, p * (len(ordered) - index)))
        result[key] = previous
    return result
