"""Policy creation helpers: what a person can choose, early checks, and the request Palladion expects.

Palladion validates a policy again when it registers it; these checks exist so a mistake is caught on the form,
in plain words, instead of as a refusal afterwards.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

OPERATIONS: dict[str, dict[str, Any]] = {
    "get_transaction_status": {
        "label": "Transaction status", "source": "mock_transaction_api", "max_age": 300,
        "fields": [{"name": "state", "label": "Transaction state", "type": "enum",
                    "values": ["FAILED", "PENDING", "SUCCEEDED"]}]},
    "get_settlement_status": {
        "label": "Settlement status", "source": "mock_settlement_service", "max_age": 300,
        "fields": [{"name": "settlement_state", "label": "Settlement state", "type": "enum",
                    "values": ["UNSETTLED", "PENDING", "SETTLED"]}]},
    "get_incident_status": {
        "label": "Incident status", "source": "mock_incident_api", "max_age": 300,
        "fields": [{"name": "state", "label": "Incident state", "type": "enum",
                    "values": ["OPEN", "INVESTIGATING", "RESOLVED"]}]},
    "get_merchant_summary": {
        "label": "Merchant summary (BI)", "source": "mock_curated_bi", "max_age": 900,
        "fields": [{"name": "result", "label": "Merchant lookup result", "type": "enum",
                    "values": ["FOUND", "NOT_FOUND"]}]},
}

TIME_BASES = [
    {"id": "TRANSACTION_OCCURRED_AT", "label": "When the transaction happened",
     "help": "The date comes from a fresh transaction-status read, never from the customer or the agent. "
             "Use it for rules that governed the payment when it was made."},
    {"id": "CASE_OPENED_AT", "label": "When the case was opened",
     "help": "The date the case was created. Use it for rules about how a case is run."},
    {"id": "EVALUATION_AT", "label": "When the question is asked",
     "help": "The server clock at the moment of the decision. Use it for current handling procedures."},
    {"id": "DOMAIN_EVENT_AT", "label": "When a named event happened",
     "help": "A named, authenticated event on the case (for example dispute_submitted). You must name the event."},
]

OPERATORS = {"enum": ("eq", "in"), "string": ("eq", "in"), "bool": ("eq",),
             "int": ("eq", "in", "lt", "lte", "gt", "gte"), "float": ("eq", "in", "lt", "lte", "gt", "gte")}

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,59}$")


def meta() -> dict[str, Any]:
    return {"operations": OPERATIONS, "time_bases": TIME_BASES, "operators": {k: list(v) for k, v in OPERATORS.items()}}


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _typed(kind: str, raw: Any) -> Any:
    """The value a condition compares against, in the type its fact has; ValueError if it is not one."""
    if kind == "bool":
        if str(raw).lower() in ("true", "false"):
            return str(raw).lower() == "true"
        raise ValueError("true or false")
    if kind == "int":
        return int(str(raw).strip())
    if kind == "float":
        return float(str(raw).strip())
    text = str(raw).strip()
    if not text:
        raise ValueError("a value")
    return text


def _values(operator: str, kind: str, raw: Any) -> Any:
    if operator != "in":
        return _typed(kind, raw)
    items = raw if isinstance(raw, list) else str(raw).split(",")
    values = [_typed(kind, item) for item in items if str(item).strip()]
    if not values:
        raise ValueError("at least one value")
    return values


def validate_draft(draft: dict[str, Any]) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []

    def bad(where: str, message: str) -> None:
        problems.append({"field": where, "message": message})

    for key, label in (("version_id", "Version ID"), ("family_id", "Policy name")):
        if not _IDENTIFIER.match(str(draft.get(key, ""))):
            bad(key, f"{label} must be 1 to 100 letters, digits, dots, dashes or underscores.")
    if not draft.get("case_ids"):
        bad("case_ids", "Choose the case this policy applies to.")
    basis = draft.get("time_basis")
    if basis not in {b["id"] for b in TIME_BASES}:
        bad("time_basis", "Choose which date decides when this policy applies.")
    if (basis == "DOMAIN_EVENT_AT") != bool(str(draft.get("domain_event") or "").strip()):
        bad("domain_event", "Name the event when the policy follows a named event, and only then.")
    start, end = _day(draft.get("valid_from")), _day(draft.get("valid_to")) if draft.get("valid_to") else None
    if start is None:
        bad("valid_from", "Choose the first day the policy applies.")
    if draft.get("valid_to") and (end is None or (start and end <= start)):
        bad("valid_to", "The last day must be after the first day, or left empty for no end.")
    if not draft.get("clauses"):
        bad("clauses", "Pick at least one passage from an approved document as the policy's source.")
    if not str(draft.get("default_outcome", "")).strip():
        bad("default_outcome", "Say what happens when no rule matches.")

    facts: dict[str, dict[str, Any]] = {}
    for number, fact in enumerate(draft.get("facts", []), 1):
        where = f"facts[{number - 1}]"
        name, operation = str(fact.get("name", "")), fact.get("operation")
        if not _NAME.match(name):
            bad(where, "Give each fact a short lowercase name such as transaction_state.")
        elif name in facts:
            bad(where, f"The fact name {name} is used twice.")
        known = OPERATIONS.get(str(operation))
        field = next((f for f in (known or {}).get("fields", []) if f["name"] == fact.get("field")), None)
        if known is None or field is None:
            bad(where, "Choose a system and one of its fields.")
            continue
        if fact.get("type") != field["type"]:
            bad(where, f"{field['label']} is a {field['type']} field.")
        extra = [v for v in fact.get("allowed_values", []) if v not in field["values"]]
        if extra:
            bad(where, f"Not a value of {field['label']}: {', '.join(extra)}.")
        age = fact.get("max_age_seconds")
        if not isinstance(age, int) or not 0 < age <= 86400:
            bad(where, "How old a reading may be must be between 1 second and 24 hours.")
        facts[name] = {**fact, "values": field["values"]}

    seen: set[str] = set()
    clause_count = len(draft.get("clauses", []))
    for number, rule in enumerate(draft.get("rules", []), 1):
        where = f"rules[{number - 1}]"
        rule_id = str(rule.get("id", ""))
        if not _IDENTIFIER.match(rule_id):
            bad(where, "Give each rule an ID of letters, digits, dots, dashes or underscores.")
        elif rule_id in seen:
            bad(where, f"The rule ID {rule_id} is used twice.")
        seen.add(rule_id)
        if not str(rule.get("outcome", "")).strip():
            bad(where, "Say what the rule decides.")
        if not isinstance(rule.get("clause_index"), int) or not 0 <= rule["clause_index"] < clause_count:
            bad(where, "Choose which source passage supports this rule.")
        conditions = rule.get("conditions", [])
        if not conditions:
            bad(where, "A rule needs at least one condition.")
        for condition in conditions:
            fact = facts.get(str(condition.get("fact")))
            if fact is None:
                bad(where, "A condition uses a fact that is not listed under 'Facts the rule needs'.")
                continue
            operator = condition.get("operator")
            if operator not in OPERATORS.get(fact["type"], ()):
                bad(where, f"'{operator}' cannot compare a {fact['type']} fact.")
                continue
            try:
                value = _values(operator, fact["type"], condition.get("value"))
            except ValueError as error:
                bad(where, f"Enter {error} for {fact['name']}.")
                continue
            listed = value if isinstance(value, list) else [value]
            allowed = fact.get("allowed_values") or fact["values"]
            if fact["type"] == "enum" and any(item not in allowed for item in listed):
                bad(where, f"{fact['name']} can only be one of: {', '.join(allowed)}.")
    return problems


def _allowed_values(fact: dict[str, Any]) -> list[str]:
    """An enum fact with no listed values would accept nothing in Palladion, so it defaults to all of them."""
    if fact["type"] != "enum":
        return []
    listed = list(fact.get("allowed_values") or [])
    if listed:
        return listed
    field = next(f for f in OPERATIONS[fact["operation"]]["fields"] if f["name"] == fact["field"])
    return list(field["values"])


def to_payload(draft: dict[str, Any]) -> dict[str, Any]:
    """The body of POST /v1/admin/policies. Call only after validate_draft returned no problems."""
    facts = {f["name"]: f for f in draft.get("facts", [])}
    rules = []
    for rule in draft.get("rules", []):
        parts = []
        for condition in rule["conditions"]:
            operator = condition["operator"]
            parts.append({"field": condition["fact"], "operator": operator,
                          "value": _values(operator, facts[condition["fact"]]["type"], condition["value"])})
        rules.append({"id": rule["id"], "predicate": {rule.get("match", "all"): parts},
                      "outcome": rule["outcome"].strip(), "clause_index": rule["clause_index"]})
    payload: dict[str, Any] = {
        "version_id": draft["version_id"], "family_id": draft["family_id"], "case_ids": list(draft["case_ids"]),
        "time_basis": draft["time_basis"], "valid_from": f"{draft['valid_from']}T00:00:00Z",
        "clauses": [{k: c[k] for k in ("revision_id", "section_id", "start_byte", "end_byte", "sha256")}
                    for c in draft["clauses"]],
        "required_facts": [{"name": f["name"], "type": f["type"], "operation": f["operation"], "field": f["field"],
                            "allowed_values": _allowed_values(f),
                            "max_age_seconds": f["max_age_seconds"]} for f in draft.get("facts", [])],
        "rules": rules, "default_outcome": draft["default_outcome"].strip()}
    if draft.get("valid_to"):
        payload["valid_to"] = f"{draft['valid_to']}T00:00:00Z"
    if draft["time_basis"] == "DOMAIN_EVENT_AT":
        payload["domain_event"] = draft["domain_event"].strip()
    if draft.get("timestamp_max_age_seconds"):
        payload["timestamp_max_age_seconds"] = int(draft["timestamp_max_age_seconds"])
    return payload
