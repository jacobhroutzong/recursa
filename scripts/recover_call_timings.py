"""Project measured llama-server timings from the historical paired runs."""
import argparse
import json
from pathlib import Path
import re

from assemble_comparison_series import assemble
from recursa.experiments import atomic_json


TIMING = re.compile(
    r"slot print_timing: id +0 \| task (?P<task>\d+) \| prompt eval time =\s+"
    r"(?P<prompt>[\d.]+) ms /\s+(?P<input>\d+) tokens[^\n]*\n"
    r"[^\n]*slot print_timing: id +0 \| task (?P=task) \| +eval time =\s+"
    r"(?P<decode>[\d.]+) ms /\s+(?P<output>\d+) tokens[^\n]*\n"
    r"[^\n]*slot print_timing: id +0 \| task (?P=task) \| +total time =\s+"
    r"(?P<total>[\d.]+) ms /\s+(?P<tokens>\d+) tokens"
)


def timing_rows(log):
    rows = list(TIMING.finditer(log))
    if ("n_slots = 1," not in log or not rows or len(rows) != log.count("total time =")
            or len(rows) != len({row["task"] for row in rows})):
        raise ValueError("Expected a complete serial timing log with unique server task IDs")
    return rows


def request_events(path, reserved):
    if not reserved and not path.is_file():
        return []
    session = json.loads(path.read_bytes())
    events = [event for event in session["events"] if "prompt_sha256" in event]
    if len(events) != reserved or session["reserved_calls"] != reserved:
        raise ValueError("Provider event count differs from the recorded reservations")
    return events


def match_call(event, row, output_cap):
    timing = {name: float(row[name]) for name in ("prompt", "decode", "total")}
    tokens = dict(zip(("prompt_tokens", "completion_tokens", "total_tokens"),
                      (int(row[name]) for name in ("input", "output", "tokens"))))
    if (abs(timing["prompt"] + timing["decode"] - timing["total"]) > 0.02
            or tokens["prompt_tokens"] + tokens["completion_tokens"] != tokens["total_tokens"]):
        raise ValueError("Inconsistent server timing row")
    usage = event.get("provider_reported_usage")
    error = event.get("error_classification")
    if event["status"] == "completed" and usage == tokens:
        status = "completed"
    elif error == "IncompleteResponse" and usage is None and tokens["completion_tokens"] == output_cap:
        status = "incomplete"
    else:
        raise ValueError("Server timing does not match the provider event")
    return {"status": status, "timing_source": "llama-server-evaluation",
            "duration_ms": timing["total"], "prompt_eval_ms": timing["prompt"],
            "generation_ms": timing["decode"], "tokens": tokens, "error_classification": error}


def recover(block_paths):
    series = assemble(block_paths)
    cases = {(case["id"], block["settings"]["seed"]): block
             for case in series["cases"] for block in case["blocks"]}
    logs = {}
    for path in block_paths:
        directory = path.parent
        block_info = json.loads(path.read_bytes())
        block = cases[block_info["case_id"], block_info["settings"]["seed"]]
        log = directory.parent / "llama-server.log"
        if log not in logs:
            logs[log] = iter(timing_rows(log.read_text(encoding="utf-8")))
        rows = logs[log]
        for trial in block["trials"]:
            private = directory / trial["method"] / "private"
            initial = request_events(private / "provider/session-report.json", trial["usage"]["reserved_calls"])
            repair = trial["repair"]["usage"]
            later = request_events(private / "paired-repair/provider/session-report.json",
                                   repair["reserved_calls"] if repair else 0)
            calls = [match_call(event, next(rows), block["output_tokens_per_call"])
                     for event in initial + later]
            trial["initial_calls"] = [{"number": index, **call}
                                      for index, call in enumerate(calls[:len(initial)], 1)]
    if any(next(rows, None) is not None for rows in logs.values()):
        raise ValueError("Unmatched server timing rows")
    return series


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("blocks", nargs="+", type=Path, help="Case blocks in each server's original run order")
    args = parser.parse_args()
    atomic_json(args.output, recover(args.blocks))


if __name__ == "__main__":
    main()
