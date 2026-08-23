# Workdoe Auth Simplification

The local Workdoe prototype uses a native email-code fallback, while the
Cloudflare Worker contains Workdoe's same-domain Clerk integration. Both paths
follow the same product flow:

1. Returning users open Clerk's maintained `SignIn` component on `/login` and request a one-time code without leaving Workdoe.
2. Consumers may draft a project at `/post-project`, then verify on
   `/create-account`; contractors start from the live project board.
3. New users choose a Workdoe role and optional profile details around the maintained sign-in-or-up component.
4. Clerk verifies the one-time code, then Workdoe creates the role-specific profile and continues to the right dashboard or selected lead.
5. Signed-in users manage identity and security on `/account`, which stays on
   Workdoe and mounts Clerk's maintained `UserProfile` component in production.

## Why this is simpler

- Email is the only sign-in identifier; usernames are not required.
- New users do not need to choose Clerk, GitHub, Google, or another provider.
- Clerk's maintained `SignIn` component handles sign-in, sign-up transfer, bot protection, invitation tickets, and any required session tasks.
- Workdoe does not call Clerk's low-level sign-in or sign-up attempt APIs from the browser.
- Role and destination are inferred from the user's chosen action.
- Role, name, and company/household choices are held in short-lived tab storage for at most 30 minutes so Clerk's verification redirect cannot discard them.
- Selected leads stay attached through `/login`, `/create-account`, and code verification.
- A valid project draft stays attached through verification without putting
  project content in a URL or identity-provider record.
- An existing account keeps its original consumer or contractor role even if
  a later sign-in starts from the other workflow.

## Clerk production option

Clerk's current docs support a combined sign-in-or-up flow and email-code/passwordless strategies. For the Cloudflare production path, configure:

- Sign up with email enabled.
- Sign in with email enabled.
- Email-code OTP as the primary strategy.
- Password sign-in disabled.
- Restricted sign-up mode enabled for the controlled beta.
- No username requirement.
- `https://workdoe.com/create-account` configured as Clerk's custom sign-up URL,
  so application invitation tickets return to the Workdoe role form.
- A same-domain Workdoe route such as `/create-account`, `/post-project`, or
  `/login`, not a public jump to a hosted Clerk login page.
- `CLERK_FRONTEND_API_URL=https://workdoe.com/__clerk` and `CLERK_PROXY_URL=https://workdoe.com/__clerk` so the in-page mount uses Workdoe's same-domain Clerk Frontend API proxy.
- `CLERK_FAPI=https://frontend-api.clerk.dev` as the upstream Clerk Frontend API target for the Worker proxy.
- Invitation-ticket sign-up for new controlled-beta accounts; normal email-code
  sign-in for existing invited accounts.
- `users.auth_provider = 'clerk'` and `users.external_subject = <Clerk user id>` after identity verification.
- Workdoe-owned role/profile creation after Clerk identity verification.
- Clerk's prebuilt `SignIn` with `withSignUp: true` and hash routing on Workdoe entry pages.
- Clerk's `@clerk/ui` bundle loaded before ClerkJS, as required by the current JavaScript SDK integration.
- Clerk's prebuilt `UserProfile` on `/account` with hash routing, so account and
  passkey settings remain inside `workdoe.com` without adding custom WebAuthn code.
- Passkeys enabled in Clerk only after the production domain is verified;
  passkeys are domain-bound and must be created and used on the Workdoe domain.

Sources:

- https://clerk.com/docs/guides/development/custom-flows/authentication/sign-in-or-up
- https://clerk.com/docs/guides/development/custom-flows/authentication/email-sms-otp
- https://clerk.com/docs/guides/development/custom-flows/authentication/application-invitations
- https://clerk.com/docs/guides/secure/restricting-access
- https://clerk.com/docs/guides/configure/auth-strategies/sign-up-sign-in-options
- https://clerk.com/docs/js-frontend/reference/components/user/user-profile
- https://clerk.com/docs/guides/development/custom-flows/authentication/passkeys
- https://clerk.com/docs/guides/secure/best-practices/csp-headers

## Cloudflare production option

For Cloudflare-first hosting, keep the app-owned role/profile tables in D1. Clerk should own public OTP login when `WORKDOE_AUTH_PROVIDER=clerk`; Cloudflare Email Service should own Workdoe transactional mail such as match reminders, admin digests, fallback OTP, and password reset fallback. Cloudflare Access OTP can protect internal/admin-only surfaces, but it is a perimeter access tool, not a full public marketplace account system.

Sources:

- https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/one-time-pin/
- https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/
- https://developers.cloudflare.com/email-service/
