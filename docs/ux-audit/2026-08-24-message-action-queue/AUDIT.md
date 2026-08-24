# Message Action Queue Audit

Date: 2026-08-24

## Scope

The approved-match message inbox and selected thread for signed-in consumers
and contractors in Flask and the matching Cloudflare Worker shell.

## Finding

Unread state correctly survived navigation, but it stopped helping after a
participant opened a message. A read conversation that still needed a response
looked identical to one waiting on the other participant. The mobile inbox also
rendered every conversation as a tall card with a second faux Open button even
though the whole row was already one link.

## Change

- Added All, Needs reply, and Unread lanes for both marketplace roles.
- Derived Needs reply from the latest non-hidden message sender; reading a
  message clears Unread but not Needs reply, while sending a response clears
  Needs reply.
- Replaced stacked message cards and nested-looking Open buttons with one
  compact, scannable inbox surface.
- Prioritized participant, project, latest message, response state, and time;
  retained service and coarse city/state as quiet context.
- Shortened the selected-thread header to the other participant and an Inbox
  action while retaining approved-bid facts, reporting, canonical routes, and
  the server-rendered reply form.
- Replaced four latest-visible-message subqueries with one indexed join in both
  runtime adapters.

## Evidence

- `01-mobile-message-inbox-before.jpg`: two tall linked cards with redundant
  Open controls.
- `02-mobile-message-thread-before.jpg`: previous selected-thread header.
- `03-mobile-message-inbox-after.jpg`: compact action queue and three lanes.
- `04-mobile-message-thread-after.jpg`: shorter participant-focused header.
- `05-tablet-message-inbox-after.jpg`: stable tablet hierarchy.
- `06-desktop-message-inbox-after.jpg`: single-screen desktop queue.
- `07-mobile-message-inbox-before-after.jpg`: aligned source and accepted
  implementation in one comparison image.

## Privacy And Performance

The queue remains available only to an active approved participant. The new
response contains a boolean `needs_reply`, not the latest sender ID. It adds no
table, notification, behavioral score, sentiment inference, rank input, or
public payload. The latest non-hidden message lookup uses the existing
`idx_messages_thread_unread` D1 index and the existing 50-thread bound.

## Acceptance

At the mobile breakpoint, All, Needs reply, and Unread shared one row; the two
seeded conversations rendered in one 844-pixel viewport with document width
equal to viewport width. Both rows retained participant, project, latest
message, coarse service/location, time, and accessible message counts while the
redundant Open controls were absent. The captured inbox content fell from 812
to 709 pixels. Selecting Needs reply updated the canonical URL and retained two
rows; selecting Unread updated the URL and exposed the correct empty state.
Tablet 820x1180 and desktop 1280x720 captures had no horizontal overflow or
text/control collision.

The final run passed 232 tests in 80.180 seconds, including participant-role,
read-state, redaction, Flask/Worker rendering, and indexed query-plan coverage.
The security/provenance gate passed across 595 non-ignored files, Cloudflare
preflight returned no warnings, and Wrangler dry-run packaged the Worker
without deploying.

## Limits

The local browser uses seeded approved matches. Production Clerk, D1, Queues,
Email, Turnstile, and private-media behavior remain separate live release
gates. The screenshots do not substitute for the automated role, read-state,
query-plan, security, or Worker-parity checks recorded with this batch.
