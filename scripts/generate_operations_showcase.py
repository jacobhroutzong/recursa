"""Generate and verify a local Operations Analytics showcase with bounded model calls."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recursa.budget import Deadline
from recursa.experiments import atomic_json
from recursa.pipeline import verify_application
from recursa.provider_worker import SupervisedProviderAdapter

CONTRACT = """
DOM bindings (put each id on the control itself, never on a wrapper):
select#team aria-label="Team", options and values All teams, North, South.
select#period aria-label="Reporting period", options and values Jan 1–3, Jan 2.
select#sort aria-label="Sort orders", options and values ID, Duration.
button#save text "Save view", button#export text "Export CSV", button#prev, button#next.
div#volume, div#rate, div#median and div#excluded get their entire text from JS.
div#daily is filled by JS. span#page and p#feedback receive text.
table#staffing aria-label="Staffing comparison", headers Team, Hours, Completed, Note, empty tbody.
table#orders aria-label="Orders", headers ID, Day, Team, Duration, Status, empty tbody.
"""
DOMAIN = """
domain.js must start with export function dashboard(team, period, sort, requestedPage).
team is All teams, North or South. period is Jan 1–3 or Jan <day>; sort is ID or Duration.
Return {volume, rate, median, excluded, orders, allOrders, staffing, daily, page, pages}.
orders is the current page, allOrders is all filtered sorted orders. Both use
{id,day,team,minutes,completed}. Excluded counts invalid records in the entire input.
volume is the number of filtered valid orders. rate is rounded percent, median uses all filtered durations.
Use null for rate and median when empty. staffing rows are {team,hours,completed,incomplete}.
Include all selected teams even if missing staffing, and flag a missing team/day in the current period.
Completed counts valid completed orders in the same period for that team. daily is {day,volume,rate} per day.
Use five rows per page. Clamp requestedPage to a new local variable page. Do not access the DOM or storage.
"""
FILES = {
    "index.html": "Write HTML with one <main> containing all controls and a heading Operations Analytics. Follow the DOM bindings literally. "
                  "Keep id=team and id=period on SELECT elements. Use the exact option values. "
                  "Link ./styles.css and use <script type=\"module\" src=\"./app.js\"></script>. "
                  "Group controls in .toolbar, metrics in .metrics, chart and tables in .panel sections. "
                  "Include span#page and p#feedback, even when empty. Do not omit main.",
    "domain.js": "Write only JavaScript for the pure data module. Use the given function contract and fixed data. "
                 "Use short array operations. First validate all raw orders. Then select days and teams. "
                 "Filter by BOTH, and compute volume as filtered.length, rate as completed/volume, "
                 "and median as the average of the two middle durations when volume is even. "
                 "Group staffing by team. Count completed orders, not staffing rows. "
                 "Return one daily row per selected day. Treat empty team as an empty string.",
    "app.js": "Write only JavaScript. Import {dashboard} from './domain.js' and bind the existing DOM. "
              "Write a single helper renderRows(tableId, rows) which clears the existing table tbody and calls "
              "tbody.insertRow().insertCell() for each cell. Reuse it for both tables. Never rebuild headers. "
              "Use textContent, createElement, and replaceChildren; no innerHTML or inline event handlers. "
              "Render 'Volume: N', 'Completion rate: N%' and 'Median turnaround: N min' with empty values if null. "
              "Render 'Excluded records: N', 'Staffing hours: N', 'Completed orders: N', and 'Staffing data incomplete' literally. "
              "Create one button per daily row with aria-label Jan <day>, and visible volume and rate. Chart click filters by its day "
              "and retains the team. Select changes rerender and reset page. Save view writes team, period, chart day, and sort to localStorage; "
              "on load restore all of them to the controls. Sort and pagination rerender. Export all filtered sorted rows with quoted CSV. "
              "Use feedback text without native dialogs. Keep app.js under 120 lines and avoid repeated declarations.",
    "styles.css": "Write only stylesheet rules for styles.css. Do not write HTML, JavaScript, or style tags. "
                  "Design a polished responsive light operations dashboard. Use a pale blue-gray canvas, ink headings, teal "
                  "accents, clean bordered cards, compact KPI cards and chart, and well-spaced controls. Keep the headline, "
                  "controls, KPIs and chart visible at typical desktop size. Style the given markup. No remote assets.",
}


def code_reply(text):
    fence = re.fullmatch(r"```(?:html|javascript|js|css)?[ \t]*\r?\n(.*?)\r?\n```[ \t]*",
                         text.strip(), re.DOTALL)
    return fence[1] if fence else text.strip()


def generate(output, model, config):
    if urlsplit(config["base_url"]).hostname != "127.0.0.1" or config["budget"]["max_cost_usd"] != 0:
        raise ValueError("The showcase requires a zero-spend local loopback model")
    spec = json.loads((ROOT / "examples/specs/operations-local-reviewed.json").read_bytes())
    scenarios = json.loads((ROOT / "examples/specs/operations-local-acceptance.json").read_bytes())
    ids = [r["id"] for r in spec["requirements"]]
    adapter = SupervisedProviderAdapter(config, output / "private/provider", authorize_live=True)
    deadline = Deadline(config["budget"]["max_wall_seconds"])
    artifacts = []
    provenance = []

    def request(path, instruction, context):
        messages = [{"role": "system", "content": f"The only requested output is {path}. " + instruction
                     + " Return only its complete source."},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)}]
        body = code_reply(adapter.complete(model, messages, deadline=deadline))
        if path != "index.html" and re.match(r"\s*<(?:!doctype|html|style|script)", body, re.IGNORECASE):
            raise ValueError(f"Model returned markup instead of {path}")
        digest = sha256(body.encode()).hexdigest()
        provenance.append({"path": path, "sha256": digest, "call": len(adapter.summary()["events"])})
        return {"path": path, "content": body, "requirements": ids}

    for path, instruction in FILES.items():
        contexts = {
            "index.html": {"dom_bindings": CONTRACT},
            "domain.js": {"function_contract": DOMAIN, "dataset": spec["requirements"][1]["text"]},
            "app.js": {"dom_bindings": CONTRACT, "data_api": DOMAIN},
            "styles.css": {"selectors": ".toolbar, .metrics, .panel, body, header, main, table, button, "
                                       "label, select, #daily, #feedback",
                           "layout": "Operations dashboard with toolbar, KPI cards, chart and two tables"},
        }
        context = contexts[path]
        artifacts.append(request(path, instruction, context))

    for attempt in range(config["budget"]["max_repairs"] + 1):
        result = verify_application(spec, artifacts, output / f"verification-{attempt:02}", scenarios=scenarios,
                                    deadline=deadline)
        atomic_json(output / "showcase-report.json", {
            "model": model, "attempt": attempt, "status": result["status"], "provenance": provenance,
            "application_report": str(output / f"verification-{attempt:02}/application-report.json"),
        })
        print(f"Operations candidate {attempt}: {result['status']} "
              f"({result['verification']['end_to_end_pass_rate']} browser rate)", flush=True)
        if result["status"] == "passed" or attempt == config["budget"]["max_repairs"]:
            return result["status"]
        failed = [check for check in result["verification"]["checks"] if check["status"] in {"failed", "timeout"}]
        details = []
        for check in failed:
            scenario = next((s for s in scenarios if s["id"] == check.get("scenario_id")), None)
            step = check.get("completed_steps", 0)
            details.append({"kind": check["kind"], "diagnostic": check.get("diagnostic", "")[:700],
                            "blocked": check.get("blocked_activity", []),
                            "failed_step": scenario["steps"][step] if scenario and step < len(scenario["steps"]) else None})
        html = next(artifact["content"] for artifact in artifacts if artifact["path"] == "index.html")
        missing_shell = not re.search(r"<main\b", html, re.IGNORECASE) or any(
            not re.search(rf"""\bid=["']{identifier}["']""", html) for identifier in ("page", "feedback"))
        target = next((path for path in ("domain.js", "app.js") if any(
            check["path"] == path and check["kind"] != "browser" for check in failed)), None)
        if target is None:
            target = "index.html" if missing_shell or any("entry" in item["diagnostic"] for item in details) else "app.js"
        context = {"failed_checks": details, "dom_bindings": CONTRACT, "data_api": DOMAIN,
                   "source": next(artifact["content"] for artifact in artifacts if artifact["path"] == target)}
        updated = request(target, f"Repair {target} using the failing checks. Preserve behavior that passes. "
                          + FILES[target], context)
        artifacts = [updated if artifact["path"] == target else deepcopy(artifact) for artifact in artifacts]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--provider-config", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--authorize-live", action="store_true")
    args = parser.parse_args()
    if not args.authorize_live:
        parser.error("--authorize-live is required for model execution")
    status = generate(args.output, args.model, json.loads(args.provider_config.read_bytes()))
    raise SystemExit(0 if status == "passed" else 1)
