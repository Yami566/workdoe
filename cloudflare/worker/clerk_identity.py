from __future__ import annotations

CLERK_RESTRICTION_FLAGS = ("banned", "locked", "disabled", "deprovisioned")


def primary_email_from_clerk_user(user_data: dict) -> tuple[str, bool]:
    primary_id = user_data.get("primary_email_address_id")
    addresses = user_data.get("email_addresses")
    if not isinstance(primary_id, str) or not primary_id or not isinstance(addresses, list):
        return "", False
    for address in addresses:
        if not isinstance(address, dict) or address.get("id") != primary_id:
            continue
        value = address.get("email_address")
        verification = address.get("verification")
        verified = isinstance(verification, dict) and verification.get("status") == "verified"
        return (value.strip().lower() if isinstance(value, str) else ""), verified
    return "", False
