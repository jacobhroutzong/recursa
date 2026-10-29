"""CPU-only specification checks. This is deliberately not model inference."""
import hashlib
import json
import time
from datetime import datetime, timezone


def _ordered(mapping):
    remaining = {key: set(refs) for key, refs in mapping.items()}
    order = []
    while remaining:
        ready = sorted(key for key, refs in remaining.items() if not refs)
        if not ready:
            raise ValueError("Cyclic specification relationships")
        order.extend(ready)
        for key in ready:
            del remaining[key]
        for refs in remaining.values():
            refs.difference_update(ready)
    return order


def _indexed_records(records, label):
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise ValueError(f"{label} must be a list of objects")
    ids = [r.get("id") for r in records]
    if any(not isinstance(i, str) or not i.strip() or len(i) > 128 for i in ids) or len(set(ids)) != len(ids):
        raise ValueError(f"{label} IDs must be nonempty, bounded and unique")
    return {r["id"]: r for r in records}


def validate_spec(spec):
    if not isinstance(spec, dict) or not isinstance(spec.get("requirements"), list) or not spec["requirements"]:
        raise ValueError("Specification requires a nonempty requirements list")
    requirements = spec["requirements"]
    indexed = _indexed_records(requirements, "Requirement")
    sections = _indexed_records(spec.get("sections", []), "Section")
    sources = _indexed_records(spec.get("sources", []), "Source")
    known = set(indexed)
    if known & set(sections):
        raise ValueError("Section and requirement IDs must be distinct")
    for field in ("design", "schemas"):
        if not isinstance(spec.get(field, {}), dict):
            raise ValueError(f"{field} must be an object")
    for section in sections.values():
        if not isinstance(section.get("text"), str):
            raise ValueError("Sections require text")
        if section.get("parent_id") is not None and (not isinstance(section["parent_id"], str) or section["parent_id"] not in sections):
            raise ValueError("Unknown parent section")
    _ordered({key: [r["parent_id"]] if r.get("parent_id") else [] for key, r in sections.items()})
    for r in requirements:
        if not isinstance(r.get("text"), str) or not r["text"].strip():
            raise ValueError("Every requirement needs text")
        for field, allowed in (("depends_on", known), ("cross_references", known | set(sections)), ("source_refs", set(sources))):
            refs = r.get(field, [])
            if not isinstance(refs, list) or any(not isinstance(d, str) or d not in allowed for d in refs):
                raise ValueError(f"Unknown {field} reference")
        if r.get("section_id") is not None and (not isinstance(r["section_id"], str) or r["section_id"] not in sections):
            raise ValueError("Unknown requirement section")
        if r.get("parent_id") is not None and (not isinstance(r["parent_id"], str) or r["parent_id"] not in known):
            raise ValueError("Unknown parent requirement")
        if "acceptance" in r:
            criteria = r["acceptance"] if isinstance(r["acceptance"], list) else [r["acceptance"]]
            if not criteria or any(not isinstance(c, str) or not c.strip() for c in criteria):
                raise ValueError("Acceptance criteria must be nonempty strings")
    _ordered({key: [r["parent_id"]] if r.get("parent_id") else [] for key, r in indexed.items()})
    return _ordered({r["id"]: r.get("depends_on", []) for r in requirements})


def run_smoke(spec):
    start = time.perf_counter()
    order = validate_spec(spec)
    encoded = json.dumps(spec, sort_keys=True).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    report = {"requirement_order": order, "spec_sha256": digest,
              "checks": {"unique_ids": True, "dependency_references": True, "acyclic": True},
              "limitation": "Specification validation only; no application generation or model inference."}
    return {"schema_version": 1, "id": "smoke-" + digest[:12],
            "label": spec.get("name", "Specification") + " · CPU check", "mode": "deterministic-smoke",
            "status": "completed", "created_at": datetime.now(timezone.utc).isoformat(), "spec": spec,
            "events": [
                {"id": "load", "parent_id": None, "type": "context", "label": "Load external specification", "status": "completed", "details": {"sha256": digest, "bytes": len(encoded)}},
                {"id": "validate", "parent_id": "load", "type": "validation", "label": "Validate requirements and dependencies", "status": "completed", "details": report},
                {"id": "export", "parent_id": "validate", "type": "artifact", "label": "Export validation report", "status": "completed", "details": {"path": "validation.json"}}],
            "artifacts": [{"path": "validation.json", "content": json.dumps(report, indent=2), "requirements": order}],
            "metrics": {"duration_ms": round((time.perf_counter() - start) * 1000, 3),
                        "model_calls": 0, "cost_usd": 0, "requirements": len(order),
                        "functional_success": None, "requirement_satisfaction": None}}
