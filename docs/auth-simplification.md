# Workdoe Auth Simplification

The current worktree does not contain Clerk, GitHub auth, or patient-scheduling code. The local Workdoe prototype now uses the simpler target flow directly:

1. Returning users enter email on `/login` and request a one-time code without leaving Workdoe.
2. New users choose the action on `/start`: post a job or find work.
3. New users enter email, name, and company/household.
4. Verify a one-time code, then continue to the right dashboard or selected lead.

## Why this is simpler

- Email is the only sign-in identifier; usernames are not required.
- New users do not need to choose Clerk, GitHub, Google, or another provider.
- The same verifier handles sign-in and account creation after email verification.
- Role and destination are inferred from the user's chosen action.
- Selected leads stay attached through `/login`, `/start`, and code verification.

## Clerk production option

Clerk's current docs support a combined sign-in-or-up flow and email-code/passwordless strategies. For the Cloudflare production path, configure:

- Sign up with email enabled.
- Sign in with email enabled.
- Email-code OTP as the primary strategy.
- No username requirement.
- A same-domain Workdoe route such as `/start` or `/login`, not a public jump to a hosted Clerk login page.
- `CLERK_FRONTEND_API_URL=https://workdoe.com/__clerk` and `CLERK_PROXY_URL=https://workdoe.com/__clerk` so the in-page mount uses Workdoe's same-domain Clerk Frontend API proxy.
- `CLERK_FAPI=https://frontend-api.clerk.dev` as the upstream Clerk Frontend API target for the Worker proxy.
- `signUpIfMissing`-style behavior where supported so account existence is not revealed before verification.
- `users.auth_provider = 'clerk'` and `users.external_subject = <Clerk user id>` after identity verification.
- Workdoe-owned role/profile creation after Clerk identity verification.

Sources:

- https://clerk.com/docs/guides/development/custom-flows/authentication/sign-in-or-up
- https://clerk.com/docs/guides/development/custom-flows/authentication/email-sms-otp
- https://clerk.com/docs/guides/configure/auth-strategies/sign-up-sign-in-options

## Cloudflare production option

For Cloudflare-first hosting, keep the app-owned role/profile tables in D1. Clerk should own public OTP login when `WORKDOE_AUTH_PROVIDER=clerk`; Cloudflare Email Service should own Workdoe transactional mail such as match reminders, admin digests, fallback OTP, and password reset fallback. Cloudflare Access OTP can protect internal/admin-only surfaces, but it is a perimeter access tool, not a full public marketplace account system.

Sources:

- https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/one-time-pin/
- https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/
- https://developers.cloudflare.com/email-service/
