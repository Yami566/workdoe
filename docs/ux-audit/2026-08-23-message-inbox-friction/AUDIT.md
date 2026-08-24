# Workdoe Message Inbox Friction Audit

Date: 2026-08-23

## Overall verdict

The inbox permissions and message-read model were already sound, but its first
screen emphasized aggregate counts instead of the next conversation. This pass
keeps the existing Workdoe visual system and replaces the three summary cards
with All and Unread task views, identifies only the other participant in each
row, and preserves the approved-project context and read behavior.

## Flow evidence

1. **Conversation scan: clearer after correction.**
   - `01-mobile-inbox-before.png` shows three non-actionable summary cards and
     repeats both participant names in every row.
   - `02-mobile-inbox-after.png` replaces those cards with two compact filters
     and labels the counterparty as `With Jordan Rivera` for the signed-in
     consumer.
   - `05-mobile-before-after-comparison.png` places the same signed-in state
     side by side. The first conversation begins earlier and the row hierarchy
     is simpler without changing the existing typography or surface treatment.

2. **Unread triage: direct and reversible.**
   - The Unread tab uses the number of conversations with unread messages, not
     the raw unread-message total.
   - `03-mobile-unread-empty-after.png` shows the zero state and a direct return
     to all messages in one mobile viewport.
   - The filter is a canonical server-rendered URL at `/messages?view=unread`;
     an unknown `view` value safely normalizes to All.

3. **Responsive layout: healthy.**
   - The 390x844 browser measurement reported `bodyWidth: 390` and
     `documentWidth: 390`, with the filter at 155 pixels and the empty state at
     203 pixels.
   - `04-desktop-inbox-after.png` at 1280x720 keeps the filters compact and the
     conversation rows scannable. The first row begins at 282 pixels and no
     horizontal overflow was detected.

4. **Role and runtime parity: covered.**
   - A consumer sees the contractor name; a contractor sees the consumer name.
   - Flask and the Cloudflare Worker use the same All/Unread contract and keep
     aggregate analytics in the authorized payload.
   - `HEAD` requests still do not mark a thread read. Opening the thread remains
     the action that updates the participant's private read marker.

## Accessibility checks

- The view selector is a labelled navigation region with ordinary links and
  `aria-current="page"` on the selected view.
- The conversation list is a labelled region; unread counts remain in each
  conversation's accessible name.
- Link targets remain keyboard reachable and the empty state has a normal
  return link.
- DOM and layout checks found no horizontal overflow at 390x844 or 1280x720.

## Evidence limits

- Screenshots and browser DOM checks do not prove full screen-reader support.
- Local seeded data covered a zero-unread consumer state; automated parity
  tests cover a contractor with unread messages and the read transition.
- Production Clerk, D1 latency, and live message delivery require the guarded
  post-deployment acceptance run.
