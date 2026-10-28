# Workdoe wireframe inventory

Status date: 2026-10-25

This inventory maps the agreed Workdoe MVP wireframe to the local Flask prototype and the Cloudflare Worker production application. A screen is marked complete only when its route, role checks, data path, and user-facing state are implemented.

| Audience | Screen or workflow | Local route | Cloudflare route | Status |
| --- | --- | --- | --- | --- |
| Public | Home with numbered six-family work filter, live project list, and map | `/` | `/` | Complete; the compact `00` plus `01`-`06` icon strip uses the same canonical family values as posting |
| Public | Same-domain email-code sign in and account creation beside the numbered work-family filter and live map | `/login`, `/create-account`, `/start/verify` | `/login`, `/create-account` | Complete; production uses Clerk same-domain email-code sign-in |
| Public | Project draft before account verification | `/post-project` | `/post-project` | Complete; a 24-hour server-side draft continues to the protected project form after verification |
| Public | Contractor profile preview | `/contractors/<id>` | `/contractors/<id>` | Complete; unrelated visitors see work facts and portfolio but not the contractor's optional website |
| Public | Project search teaser and approximate map | `/` | `/` | Complete |
| Public | Safety and trust | `/safety` | `/safety` | Complete |
| Client | Project dashboard | `/client/dashboard` | `/client/dashboard` | Complete |
| Client | Private consumer profile and saved project areas | `/client/profile` | `/client/profile` | Complete; saved city/ZIP areas can prefill a new project and remain owner-only |
| Client | Six-step project composer with family icons, numbered task tiles, native-select fallback, and optional budget range | `/post-project` to `/jobs/new` | `/post-project` to `/jobs/new` | Complete; changing families clears an incompatible task. Public photo uploads are disabled for the beta |
| Client | Edit project | `/client/jobs/<id>/edit` | `/client/jobs/<id>/edit` | Complete |
| Client | Project detail and retained-media access | `/client/jobs/<id>` | `/client/jobs/<id>` | Permission checks complete; new public media uploads are disabled for the beta |
| Client | Bid request inbox | `/client/requests` | `/client/requests` | Complete |
| Client | Received-order comparison plus full review and approve/reject mini bids; view or extend an expired non-full bid window | `/client/jobs/<id>#mini-bids` | `/client/jobs/<id>#mini-bids` | Complete; up to four pending offers compare terms and separately qualified provider facts without a score or paid order; four-slot usage and seven-day deadline are visible and extensions are audited |
| Client | Approved private message thread | `/messages/<id>` | `/messages/<id>` | Complete |
| Client | Same-page structured project close-out, reopen, completion confirmation, and four-stage journey | `/client/jobs/<id>` | `/client/jobs/<id>` | Complete in code; private note remains owner/admin only and production two-account acceptance remains required |
| Contractor | Work dashboard | `/contractor/dashboard` | `/contractor/dashboard` | Complete |
| Contractor | Profile setup and portfolio readiness | `/contractor/profile` | `/contractor/profile` | Seven-step storefront readiness and HTTPS-only website validation are shared by Flask and Worker; new portfolio uploads are disabled for the beta |
| Contractor | Lead list with numbered work-family/category/search filters, map, saved view, and visible bid availability | `/leads` | `/leads` | Complete; family selection is deterministic and saved alert matching rechecks the selected family |
| Contractor | Project detail, deadline/cap-enforced mini-bid form, and bidder-only lead-quality feedback | `/jobs/<id>` | `/jobs/<id>` | Complete; feedback is operational and not a public rating |
| Contractor | Active message threads | `/messages` | `/messages` | Complete |
| Contractor | Workdoe-matched outcomes and independent completion confirmation | `/contractor/dashboard#completed-work` | `/contractor/dashboard#completed-work` | Complete in code; non-Workdoe close outcomes do not become completed-work history and exact addresses remain excluded |
| Admin | Moderation dashboard and audit history | `/admin` | `/admin` | Complete |
| Admin | Published-to-match, close-out, lead-quality, and verified-fulfillment metrics | `/admin` | `/admin` | Complete in code; production metrics require real pilot data and human review thresholds |

## Owner decisions recorded

1. Visitors may complete a project draft before email verification. The draft expires after 24 hours, excludes photos, and is consumed when the verified consumer posts the project.
2. One account has one permanent marketplace role during the beta. Existing consumer and contractor records ignore conflicting role requests.
3. Project posts support optional whole-dollar minimum and maximum budgets. Either bound may stand alone; an entered maximum cannot be lower than the minimum.
4. Every project accepts at most four mini bids for seven calendar days. All
   submissions count toward capacity regardless of later approval/rejection;
   an owning consumer may add seven days only after a non-full window expires.

## Launch dependencies

- Clerk production same-domain email-code credentials, D1 migrations, and
  Worker bindings are verified in the current production record. A fresh
  owner-entered consumer and contractor email-code journey remains required.
- Keep public photo uploads disabled until a separate private-media decision is
  approved and tested.
- Add operator-approved privacy policy and terms before broad public onboarding. This repository does not invent legal language on the operator's behalf.
