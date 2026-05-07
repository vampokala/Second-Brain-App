#!/usr/bin/env python3
"""
Compare evaluation metrics between baseline and current results.
Used in GitHub Actions to gate PRs based on regression thresholds.
"""

import json
import sys
import argparse
from typing import Dict, Tuple


def load_metrics(filepath: str) -> Dict:
    """Load metrics from JSON file."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {filepath} not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: {filepath} is not valid JSON")
        sys.exit(1)


def compare_metrics(
    baseline: Dict, current: Dict, threshold_pct: float = 5.0
) -> Tuple[bool, Dict]:
    """
    Compare baseline and current metrics.

    Returns:
        (passed: bool, results: Dict with details)
    """
    results = {
        "passed": True,
        "regressions": [],
        "threshold_pct": threshold_pct,
    }

    # Metrics to track (lower is better for latency/cost, higher is better for quality)
    latency_metrics = [
        "total_p50_ms",
        "total_p95_ms",
        "retrieval_avg_ms",
        "generation_avg_ms",
    ]
    quality_metrics = [
        "citation_groundedness_avg",
        "nli_faithfulness_avg",
    ]
    cost_metrics = ["avg_per_request_usd"]

    # Check latency (should not increase by >threshold%)
    baseline_latency = baseline.get("latency", {})
    current_latency = current.get("latency", {})

    for metric in latency_metrics:
        baseline_val = baseline_latency.get(metric)
        current_val = current_latency.get(metric)

        if baseline_val is None or current_val is None:
            continue

        pct_change = ((current_val - baseline_val) / baseline_val) * 100

        if pct_change > threshold_pct:
            results["regressions"].append({
                "metric": metric,
                "baseline": baseline_val,
                "current": current_val,
                "pct_change": pct_change,
                "direction": "worse (latency increased)",
            })
            results["passed"] = False

    # Check quality (should not decrease by >threshold%)
    baseline_quality = baseline.get("quality", {})
    current_quality = current.get("quality", {})

    for metric in quality_metrics:
        baseline_val = baseline_quality.get(metric)
        current_val = current_quality.get(metric)

        if baseline_val is None or current_val is None:
            continue

        pct_change = ((baseline_val - current_val) / baseline_val) * 100 if baseline_val > 0 else 0

        if pct_change > threshold_pct:
            results["regressions"].append({
                "metric": metric,
                "baseline": baseline_val,
                "current": current_val,
                "pct_change": pct_change,
                "direction": "worse (quality decreased)",
            })
            results["passed"] = False

    # Check cost (should not increase by >threshold%)
    baseline_cost = baseline.get("cost", {})
    current_cost = current.get("cost", {})

    for metric in cost_metrics:
        baseline_val = baseline_cost.get(metric)
        current_val = current_cost.get(metric)

        if baseline_val is None or current_val is None:
            continue

        pct_change = ((current_val - baseline_val) / baseline_val) * 100 if baseline_val > 0 else 0

        if pct_change > threshold_pct:
            results["regressions"].append({
                "metric": metric,
                "baseline": baseline_val,
                "current": current_val,
                "pct_change": pct_change,
                "direction": "worse (cost increased)",
            })
            results["passed"] = False

    return results["passed"], results


def main():
    parser = argparse.ArgumentParser(
        description="Compare evaluation metrics between baseline and current"
    )
    parser.add_argument("--baseline", required=True, help="Path to baseline metrics JSON")
    parser.add_argument("--current", required=True, help="Path to current metrics JSON")
    parser.add_argument(
        "--threshold", type=float, default=5.0, help="Regression threshold in percent (default: 5%)"
    )
    parser.add_argument("--strict", action="store_true", help="Fail on any regression")

    args = parser.parse_args()

    baseline = load_metrics(args.baseline)
    current = load_metrics(args.current)

    threshold = 0 if args.strict else args.threshold
    passed, results = compare_metrics(baseline, current, threshold_pct=threshold)

    print(json.dumps(results, indent=2))

    if not passed:
        print(f"\n❌ Regression detected ({len(results['regressions'])} metric(s) failed)")
        for reg in results["regressions"]:
            print(f"  - {reg['metric']}: {reg['pct_change']:.1f}% {reg['direction']}")
        sys.exit(1)
    else:
        print("\n✅ All metrics pass regression gate")
        sys.exit(0)


if __name__ == "__main__":
    main()
