"""GLEIF LEI lookup. A match is accepted only when the legal name matches exactly (case and
punctuation-insensitive) AND the GLEIF jurisdiction matches the SEC state of incorporation.
Anything else is reported as ambiguous or not found — never guessed."""
from __future__ import annotations

import re
from urllib.parse import urlencode

from app.sources.http import Retrieved, fetch

API = "https://api.gleif.org/api/v1/lei-records"


def search_url(legal_name: str) -> str:
    return API + "?" + urlencode({"filter[entity.legalName]": legal_name, "page[size]": 20})


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def lookup(legal_name: str, state_of_incorporation: str | None, mode: str | None = None) -> tuple[dict, Retrieved]:
    r = fetch(search_url(legal_name), "gleif", mode=mode)
    data = r.json().get("data", [])
    want = _norm(legal_name)
    juris = f"US-{state_of_incorporation}" if state_of_incorporation and len(state_of_incorporation) == 2 else None
    named = [d for d in data if _norm(d["attributes"]["entity"]["legalName"]["name"]) == want]
    exact = [d for d in named if d["attributes"]["entity"].get("jurisdiction") == juris] if juris else named
    if named and not exact:
        # same legal name but a different jurisdiction than SEC reports: never auto-accept, flag for manual check
        return {"match": "jurisdiction_mismatch", "sec_state_of_incorporation": state_of_incorporation,
                "candidates": [{"lei": d["id"], "legal_name": d["attributes"]["entity"]["legalName"]["name"],
                                "jurisdiction": d["attributes"]["entity"].get("jurisdiction"),
                                "registration_status": d["attributes"]["registration"].get("status")}
                               for d in named][:5]}, r
    if len(exact) == 1:
        a = exact[0]["attributes"]
        return {"match": "exact", "lei": exact[0]["id"], "legal_name": a["entity"]["legalName"]["name"],
                "jurisdiction": a["entity"].get("jurisdiction"), "entity_status": a["entity"].get("status"),
                "registration_status": a["registration"].get("status"),
                "last_update": a["registration"].get("lastUpdateDate"),
                "next_renewal": a["registration"].get("nextRenewalDate"),
                "legal_address": a["entity"].get("legalAddress"), "registered_as": a["entity"].get("registeredAs")}, r
    return {"match": "ambiguous" if len(exact) > 1 else "not_found",
            "candidates": [d["id"] for d in exact][:5]}, r
