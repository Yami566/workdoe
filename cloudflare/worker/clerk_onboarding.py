from __future__ import annotations

from clerk_identity import CLERK_RESTRICTION_FLAGS, primary_email_from_clerk_user
from content_privacy import contains_disallowed_personal_data
from email_payloads import valid_email

MAX_ONBOARDING_BODY_BYTES = 8192
ONBOARDING_ROLES = {"client", "contractor"}
ONBOARDING_TEXT_MAX_LENGTH = 120


class OnboardingError(ValueError):
    pass


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def claim_email(claims: dict) -> str:
    value = claims.get("email")
    email = value.strip().lower() if isinstance(value, str) else ""
    if len(email) <= 254 and valid_email(email):
        return email
    raise OnboardingError("A verified Clerk email claim is required.")


def claims_with_verified_clerk_email(claims: dict, user_data: dict) -> dict:
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject or user_data.get("id") != subject:
        raise OnboardingError("Clerk user response did not match the verified session.")
    if any(user_data.get(flag, False) is not False for flag in CLERK_RESTRICTION_FLAGS):
        raise OnboardingError("Clerk account is not available for onboarding.")
    email, verified = primary_email_from_clerk_user(user_data)
    if not verified or len(email) > 254 or not valid_email(email):
        raise OnboardingError("A verified Clerk email is required.")
    return {**claims, "email": email, "email_verified": True}


def onboarding_profile(body: dict) -> dict[str, str]:
    if not isinstance(body, dict):
        raise OnboardingError("Onboarding body must be a JSON object.")
    for field in ("role", "display_name", "company_name"):
        if body.get(field) is not None and not isinstance(body[field], str):
            raise OnboardingError("Onboarding profile fields must be text.")
    role = compact_spaces(body.get("role")).lower()
    if role not in ONBOARDING_ROLES:
        raise OnboardingError("Role must be client or contractor.")

    display_name = compact_spaces(body.get("display_name"))[:ONBOARDING_TEXT_MAX_LENGTH]
    company_name = compact_spaces(body.get("company_name"))[:ONBOARDING_TEXT_MAX_LENGTH]
    if not display_name:
        raise OnboardingError("Choose a public business name or non-identifying handle to create a Workdoe account.")
    if contains_disallowed_personal_data((display_name, company_name)):
        raise OnboardingError(
            "Do not include email addresses, phone numbers, or exact street addresses in a public business name or handle."
        )
    if not company_name:
        company_name = display_name

    return {
        "role": role,
        "display_name": display_name,
        "company_name": company_name,
    }


def onboarding_payload(claims: dict, profile: dict[str, str]) -> dict[str, str]:
    if claims.get("email_verified") is not True:
        raise OnboardingError("Clerk email claim is not verified.")
    return {**profile, "email": claim_email(claims)}
