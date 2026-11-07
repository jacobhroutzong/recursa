"""Validate and combine completed local comparison blocks for Studio."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from run_task_comparison import load_case
from recursa.experiments import atomic_json


LABELS = {"tasks": "Task Management", "operations": "Operations Analytics"}
MATCHED_FIELDS = ("model", "revision", "weights_sha256", "runtime_binary_sha256",
                  "rlm_runtime_source_sha256", "budget", "output_tokens_per_call")
METHODS = {"direct", "structured", "rlm"}


def assemble(paths):
    blocks = [json.loads(path.read_bytes()) for path in paths]
    first = blocks[0]
    settings = {k: v for k, v in first["settings"].items() if k != "seed"}
    repair_budget = first.get("repair_budget")
    cases = {case: {} for case in LABELS}
    for block in blocks:
        if (any(block[key] != first[key] for key in MATCHED_FIELDS)
                or {k: v for k, v in block["settings"].items() if k != "seed"} != settings
                or block["paid_api_calls"] != 0 or block["budget"]["max_repairs"] != 0
                or block.get("repair_budget") != repair_budget):
            raise ValueError("Incompatible model, runtime, settings or budget")
        case = block["case_id"]
        seed = block["settings"]["seed"]
        if case not in cases or seed in cases[case]:
            raise ValueError("Unknown or duplicate case and seed block")
        trials = block["trials"]
        if len(trials) != 3 or {trial["method"] for trial in trials} != METHODS:
            raise ValueError("Incomplete method block")
        if any(trial["usage"]["reserved_calls"] < 1 for trial in trials):
            raise ValueError("A recorded arm has no reserved inference")
        cases[case][seed] = block
    if len(cases["tasks"]) < 2 or cases["tasks"].keys() != cases["operations"].keys():
        raise ValueError("Both specifications need at least two matched seed blocks")
    published = []
    for case, label in LABELS.items():
        spec, original, scenarios = load_case(case)
        ids = [scenario["id"] for scenario in scenarios]
        expected = {
            "spec_sha256": sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest(),
            "scenarios_sha256": sha256(json.dumps(scenarios, sort_keys=True).encode()).hexdigest(),
            "original_scenarios_sha256": sha256(original).hexdigest(),
            "requirement_count": len(spec["requirements"]), "scenario_ids": ids,
        }
        for block in cases[case].values():
            if any(block[key] != value for key, value in expected.items()):
                raise ValueError(f"{case} block does not match the reviewed inputs")
            for trial in block["trials"]:
                outcomes = [trial]
                if repair_budget:
                    repair = trial["repair"]
                    usage = repair["usage"]
                    if (not 0 <= repair["attempts"] <= 1 or (usage and usage["reserved_calls"] > 1)
                            or (repair["after"] is not None and repair["status"] not in {"rechecked", "still-failing"})):
                        raise ValueError("Invalid bounded repair observation")
                    if repair["after"] is not None:
                        outcomes.append(repair["after"])
                for outcome in outcomes:
                    checks = outcome["scenarios"]
                    rate = outcome["end_to_end_pass_rate"]
                    if rate is not None and (
                        [check["id"] for check in checks] != ids
                        or rate != sum(check["status"] == "passed" for check in checks) / len(ids)
                    ):
                        raise ValueError("Browser measurement does not match its scenario outcomes")
        published.append({"id": case, "label": label, "requirement_count": expected["requirement_count"],
                          "scenario_count": len(ids), "blocks": [cases[case][seed] for seed in sorted(cases[case])]})
    result = {"schema_version": 1, "kind": "matched-local-series", "model": first["model"],
              "total_trials": sum(len(block["trials"]) for block in blocks), "cases": published}
    if repair_budget:
        result.update(kind="matched-local-repair-series", repair_budget=repair_budget)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("blocks", nargs="+", type=Path)
    args = parser.parse_args()
    atomic_json(args.output, assemble(args.blocks))


if __name__ == "__main__":
    main()
