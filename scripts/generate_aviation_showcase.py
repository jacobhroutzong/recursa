"""Collect three local model-generated Aviation showcase source files."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from generate_operations_showcase import code_reply
from recursa.experiments import atomic_json
from recursa.provider_worker import SupervisedProviderAdapter


PROMPTS = {
    "index.html": """Write only a complete HTML document for a fictional Aviation Operations dashboard.
Use lang=en, viewport, one main and heading Aviation Operations, with a prominent label
Synthetic exercise · Non-operational. Link ./styles.css and local module ./app.js.
Use .hero for the header, .toolbar for controls, .metrics for stats, and .panel for each section.
Include select#terminal labeled Terminal (All terminals, T1, T2), select#window labeled Time range
(Full exercise, 08:30–09:30 UTC), and select#status labeled Flight status (All statuses, On time, Delayed).
Each option's value is exactly its visible text. Use buttons #advance (Advance 5 min), #pause (Pause exercise),
#reset (Reset exercise), #sort (Reverse schedule), #prepare (Prepare summary), #export (Export JSON).
Include #clock, #quality, #flight-count, #conflict-count, #board-order and #feedback text slots.
Use table#board aria-label="Flight board", column headers Flight, Terminal, UTC, Movement, Stand, Status, empty tbody.
Use labeled regions: section#stands aria-label="Stand assignments"; section#conflicts aria-label="Stand conflicts";
section#alerts aria-label="Simulated alerts"; section#detail aria-label="Flight detail";
section#summary aria-label="Exercise summary". Each can contain a title followed by empty div#<id>-body.
Use no inline styles, inline handlers, or external dependencies.""",
    "views.js": """Write only JavaScript source for views.js. Export precisely these three functions:
renderBoard(tbody, flights, openFlight), renderStands(container, flights), renderAlerts(container, alerts, acknowledge).
Use DOM creation, textContent and replaceChildren. No innerHTML. No event delegation or global queries.
renderBoard clears tbody and inserts one row per flight in incoming order with cells: button with text flight.id
which invokes openFlight(flight.id), terminal, scheduled, movement, stand, status.
renderStands clears container, then appends an article.assignment for each flight, showing its stand, flight.id,
start and end with UTC. Empty state text for no rows.
renderAlerts clears container and appends an article.alert for each alert, showing id, priority, source, message
and flight ID. If alert.ack is a string, show Acknowledged at <ack> UTC. Otherwise add a button with exact text
Acknowledge <id> invoking acknowledge(alert.id). Show an empty state for no alerts.
Keep these renderers compact, complete, and self-contained. Return no HTML document or Markdown explanation.""",
    "styles.css": """Write only a stylesheet for a fictional airport operations console. Near-black navy surfaces,
strong cyan headings, thin cool-gray borders and a readable amber synthetic label. Distinct but restrained.
Style .hero, .toolbar, .metrics, .panel, .assignment, .alert, tables, buttons, select elements and focus-visible.
Use system fonts, a roomy max-width, visibly labeled statuses, and responsive wrapping below 700px.
Allow tables to scroll inside panels on narrow screens. Do not use remote fonts, images, or JS.""",
}


def generate(output, model, config, *, authorize_live=False):
    if urlsplit(config["base_url"]).hostname != "127.0.0.1" or config["budget"]["max_cost_usd"] != 0:
        raise ValueError("The showcase requires a zero-spend local loopback model")
    adapter = SupervisedProviderAdapter(config, output / "private/provider", authorize_live=authorize_live)
    files = []
    for path, prompt in PROMPTS.items():
        text = adapter.complete(model, [{"role": "system", "content": f"Return only the source for {path}."},
                                        {"role": "user", "content": prompt}])
        files.append({"path": path, "content": code_reply(text), "call": len(files) + 1})
        atomic_json(output / "model-files.json", files)
        print(f"Recorded generated {path}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--provider-config", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--authorize-live", action="store_true")
    args = parser.parse_args()
    generate(args.output, args.model, json.loads(args.provider_config.read_bytes()),
             authorize_live=args.authorize_live)
