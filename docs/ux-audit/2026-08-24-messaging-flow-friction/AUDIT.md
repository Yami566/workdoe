# Approved-Match Messaging Friction Audit

Date: 2026-08-24

## Scope

Authenticated contractor inbox and approved-match thread at `/messages` and
`/messages/2`, using the same seeded local account, two conversations, and
three-message selected thread before and after the change.

## Steps and health

1. Message list, desktop: healthy. The two threads, participant, location,
   latest message, time, and unread controls are scannable in
   `03-desktop-messages-list-before.jpg`.
2. Open a thread, desktop: improved. The former single conversation surface in
   `04-desktop-thread-before.jpg` required returning to the inbox to switch
   approved matches. `05-desktop-thread-after.jpg` adds a bounded conversation
   rail while preserving the selected project terms, message list, and reply
   composer.
3. Switch conversations, desktop: healthy. Selecting the other conversation
   changed the canonical route from `/messages/2` to `/messages/1`, refreshed
   the title, approved terms, message history, and project link, and retained a
   specific accessible link name.
4. Continue a thread, mobile: healthy after correction. The conversation rail
   is absent below the desktop breakpoint. `07-mobile-thread-before.jpg` and
   `06-mobile-thread-after.jpg` show the same thread; the compact header keeps
   the complete Send action above the fixed primary-task navigation.
5. Continue a thread, tablet: healthy. `10-tablet-thread-after.jpg` preserves
   the bounded message list and visible composer without introducing a dense
   desktop rail at 820x1180.
6. Report a message in production: parity restored. The Cloudflare Worker
   renderer now exposes the same participant-only report disclosure as Flask,
   submits to the existing rate-limited `/api/reports` endpoint, and includes
   Turnstile when configured. Admin review remains read-only.

## Changes

- Reused one local thread-list query for the inbox and selected-thread rail,
  capped at the Worker's existing 50-thread bound.
- Added a desktop conversation rail with current-thread and unread states;
  standard same-domain links preserve direct URLs and no-JavaScript behavior.
- Reused the Worker's thread listing payload to populate the rail and unread
  navigation count, avoiding a separate unread-count query on thread pages.
- Added missing Worker message-report forms using the existing moderation API,
  request rate limiting, idempotency, Turnstile, and worker-actions controller.
- Kept the mobile and tablet conversation focused on the selected thread, then
  compacted the phone header after visual review found the fixed task bar
  clipping Send.
- Added no dependency, message field, email notification, inferred preference,
  or new data recipient.

## Evidence

- `08-desktop-thread-before-after.jpg`: aligned 1280x720 comparison used for
  the desktop review.
- `09-mobile-thread-before-after.jpg`: aligned 390x844 comparison used for the
  phone review.
- `10-tablet-thread-after.jpg`: accepted 820x1180 viewport capture.

## Limits

The DOM pass confirmed named conversation navigation, current-page state,
approved-match summary, message articles, report disclosures, and reply form.
Screenshots do not prove screen-reader announcements, production Turnstile
completion, live moderation delivery, or Core Web Vitals. Those remain final
production acceptance gates.
