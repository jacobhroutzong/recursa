"""Indexed external specifications with bounded, observable access."""
from copy import deepcopy
import json
from recursa.engine import validate_spec


class ContextIndex:
    def __init__(self, spec, record=lambda *args: None, max_chars=12000):
        validate_spec(spec)
        self.spec = deepcopy(spec)
        self.requirements = {r["id"]: r for r in self.spec["requirements"]}
        self.sections = {s["id"]: s for s in self.spec.get("sections", [])}
        self.record = record
        self.max_chars = max_chars

    def read(self, requirement_ids):
        """Return selected requirements; error rather than silently truncate JSON."""
        if not isinstance(requirement_ids, list) or not 1 <= len(requirement_ids) <= 32:
            raise ValueError("Read between 1 and 32 requirement IDs")
        result = [deepcopy(self.requirements[key]) for key in requirement_ids]
        if len(json.dumps(result, ensure_ascii=False)) > self.max_chars:
            raise ValueError("Observation too large; select fewer requirements")
        self.record("context", "Read selected requirements", {"requirement_ids": requirement_ids})
        return result

    def search(self, query, limit=10):
        """Literal text search returns IDs and bounded excerpts, not full context."""
        if not isinstance(query, str) or not 1 <= len(query) <= 200 or type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("Search needs a short query and limit 1–20")
        matches = [{"id": key, "excerpt": r["text"][:160]}
                   for key, r in self.requirements.items() if query.casefold() in json.dumps(r).casefold()][:limit]
        self.record("context", "Search external requirements", {"requirement_ids": [r["id"] for r in matches]})
        return matches

    def metadata(self, offset=0, limit=32):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 32:
            raise ValueError("Metadata needs a nonnegative offset and limit 1–32")
        keys = list(self.requirements)
        return {"requirement_ids": keys[offset:offset + limit], "count": len(keys),
                "next_offset": offset + limit if offset + limit < len(keys) else None,
                "section_count": len(self.sections), "section_ids": list(self.sections)[offset:offset + limit],
                "bytes": len(json.dumps(self.spec).encode())}

    def read_section(self, section_id):
        section = deepcopy(self.sections[section_id])
        if len(json.dumps(section, ensure_ascii=False)) > self.max_chars:
            raise ValueError("Section too large; inspect selected requirements instead")
        self.record("context", "Read specification section", {"section_id": section_id})
        return section

    def read_schema(self, name):
        schema = deepcopy(self.spec.get("schemas", {})[name])
        if len(json.dumps(schema, ensure_ascii=False)) > self.max_chars:
            raise ValueError("Schema observation too large")
        self.record("context", "Read data/API schema", {"schema_name": name})
        return schema
