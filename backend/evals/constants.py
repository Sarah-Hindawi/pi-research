"""
Shared lookup tables for state codes and contributing-factor codes.
"""

STATE_CODES: dict[str, str] = {
    "california":   "CA",
    "texas":        "TX",
    "new york":     "NY",
    "florida":      "FL",
    "pennsylvania": "PA",
    "washington":   "WA",
}

FACTOR_CODES: dict[str, str] = {
    "dui":                            "DUI",
    "dwi":                            "DUI",
    "driving too fast":               "SPEEDING",
    "speeding":                       "SPEEDING",
    "failure to maintain lane":       "FAILURE_MAINTAIN",
    "failure to obey traffic control":"TRAFFIC_CONTROL",
    "failure to use":                 "UNSAFE_VEHICLE",
    "horn":                           "UNSAFE_VEHICLE",
    "failure to yield at a yield":    "FAILURE_TO_YIELD",
    "failure to yield":               "FAILURE_TO_YIELD",
    "fleeing a police":               "TRAFFIC_CONTROL",
    "fleeing the scene":              "TRAFFIC_CONTROL",
    "following too closely":          "TAILGATING",
    "improper lane":                  "IMPROPER_LANE",
    "improper passing":               "IMPROPER_PASSING",
    "improper starting":              "BACKING",
    "improper stopping":              "FAILURE_TO_STOP",
    "improper turning":               "FAILURE_TO_SIGNAL",
    "reckless driving":               "RECKLESS_DRIVING",
    "wireless telephone":             "DISTRACTED",
    "texting":                        "DISTRACTED",
}


def state_to_code(state: str) -> str:
    return STATE_CODES.get(state.strip().lower(), "")


def factor_name_to_code(name: str) -> str:
    n = name.lower().strip()
    for key, code in FACTOR_CODES.items():
        if key in n:
            return code
    return ""
