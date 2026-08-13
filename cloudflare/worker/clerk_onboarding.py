from __future__ import annotations


MAX_ONBOARDING_BODY_BYTES = 8192
ONBOARDING_ROLES = {"client", "contractor"}
ONBOARDING_TEXT_MAX_LENGTH = 120


class OnboardingError(ValueError):
    pass


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def normalize_email(value: str | None) -> str:
    return compact_spaces(value).lower()


def claim_email(claims: dict) -> str:
    for key in ("email", "primary_email", "primary_email_address"):
        email = normalize_email(claims.get(key))
        if email and "@" in email:
            return email
    raise OnboardingError("A verified Clerk email claim is required.")


def email_claim_verified(claims: dict) -> bool:
    value = claims.get("email_verified")
    return value in {None, True, 1, "1", "true", "verified"}


def onboarding_payload(claims: dict, body: dict) -> dict[str, str]:
    if not isinstance(body, dict):
        raise OnboardingError("Onboarding body must be a JSON object.")
    if not email_claim_verified(claims):
        raise OnboardingError("Clerk email claim is not verified.")

    role = compact_spaces(body.get("role")).lower()
    if role not in ONBOARDING_ROLES:
        raise OnboardingError("Role must be client or contractor.")

    display_name = compact_spaces(body.get("display_name"))[:ONBOARDING_TEXT_MAX_LENGTH]
    company_name = compact_spaces(body.get("company_name"))[:ONBOARDING_TEXT_MAX_LENGTH]
    if not display_name:
        display_name = compact_spaces(claims.get("name"))[:ONBOARDING_TEXT_MAX_LENGTH]
    if not display_name:
        display_name = claim_email(claims).split("@", 1)[0]
    if not company_name:
        company_name = display_name

    return {
        "email": claim_email(claims),
        "role": role,
        "display_name": display_name,
        "company_name": company_name,
    }
