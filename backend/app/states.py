from __future__ import annotations

from typing import Literal, TypedDict


StateGroup = Literal["states", "territories", "other"]


class StateOption(TypedDict):
    code: str
    name: str
    label: str
    group: StateGroup


def _state(code: str, name: str) -> StateOption:
    return {"code": code, "name": name, "label": name, "group": "states"}


def _territory(code: str, name: str) -> StateOption:
    return {
        "code": code,
        "name": name,
        "label": f"{name} (Territory)",
        "group": "territories",
    }


# This is the canonical catalog for every state choice exposed by the API and UI.
# Values saved to employees and policy conditions are always the two-letter code.
STATES: list[StateOption] = [
    _state("AL", "Alabama"),
    _state("AK", "Alaska"),
    _state("AZ", "Arizona"),
    _state("AR", "Arkansas"),
    _state("CA", "California"),
    _state("CO", "Colorado"),
    _state("CT", "Connecticut"),
    _state("DE", "Delaware"),
    _state("FL", "Florida"),
    _state("GA", "Georgia"),
    _state("HI", "Hawaii"),
    _state("ID", "Idaho"),
    _state("IL", "Illinois"),
    _state("IN", "Indiana"),
    _state("IA", "Iowa"),
    _state("KS", "Kansas"),
    _state("KY", "Kentucky"),
    _state("LA", "Louisiana"),
    _state("ME", "Maine"),
    _state("MD", "Maryland"),
    _state("MA", "Massachusetts"),
    _state("MI", "Michigan"),
    _state("MN", "Minnesota"),
    _state("MS", "Mississippi"),
    _state("MO", "Missouri"),
    _state("MT", "Montana"),
    _state("NE", "Nebraska"),
    _state("NV", "Nevada"),
    _state("NH", "New Hampshire"),
    _state("NJ", "New Jersey"),
    _state("NM", "New Mexico"),
    _state("NY", "New York"),
    _state("NC", "North Carolina"),
    _state("ND", "North Dakota"),
    _state("OH", "Ohio"),
    _state("OK", "Oklahoma"),
    _state("OR", "Oregon"),
    _state("PA", "Pennsylvania"),
    _state("RI", "Rhode Island"),
    _state("SC", "South Carolina"),
    _state("SD", "South Dakota"),
    _state("TN", "Tennessee"),
    _state("TX", "Texas"),
    _state("UT", "Utah"),
    _state("VT", "Vermont"),
    _state("VA", "Virginia"),
    _state("WA", "Washington"),
    _state("WV", "West Virginia"),
    _state("WI", "Wisconsin"),
    _state("WY", "Wyoming"),
    _territory("AS", "American Samoa"),
    _territory("GU", "Guam"),
    _territory("MP", "Northern Mariana Islands"),
    _territory("PR", "Puerto Rico"),
    _territory("VI", "U.S. Virgin Islands"),
    {
        "code": "DC",
        "name": "District of Columbia",
        "label": "District of Columbia (Federal District)",
        "group": "other",
    },
]

STATE_BY_CODE = {item["code"]: item for item in STATES}
STATE_CODES = frozenset(STATE_BY_CODE)


def normalize_state_code(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("must be a valid two-letter U.S. state or territory code")
    normalized = value.strip().upper()
    if normalized not in STATE_CODES:
        raise ValueError("must be a valid two-letter U.S. state or territory code")
    return normalized


def state_label(value: str) -> str:
    option = STATE_BY_CODE.get(value.upper())
    return option["label"] if option else value


def matching_state_codes(query: str) -> tuple[str, ...]:
    normalized = query.strip().casefold()
    if not normalized:
        return ()
    return tuple(
        item["code"]
        for item in STATES
        if normalized in item["code"].casefold()
        or normalized in item["name"].casefold()
        or normalized in item["label"].casefold()
    )
