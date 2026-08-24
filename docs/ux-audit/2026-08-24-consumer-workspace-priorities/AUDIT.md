# Consumer Workspace Priority Audit

Date: 2026-08-24

## Scope

The signed-in consumer project dashboard in Flask and the matching Cloudflare
Worker shell. The seeded owner state contained two active projects, two hidden
projects, and one mutually completed project with repeat-work actions.

## Finding

The default All lane rendered every project status in one mobile stream and
then rendered the completed project again in a separate history section. That
made current decisions compete with paused and finished work, exposed internal
`hidden` wording, and produced a 2,241-pixel phone page before the consumer
reached the end of the workspace.

## Change

- Replaced the overlapping All, Review, Open, and Closed tabs with Active,
  Bids, Paused, and History.
- Made Active the default and kept only open projects in that lane.
- Kept pending decisions in Bids, non-public projects in Paused, and completed
  work plus repeat actions in History.
- Presented hidden projects as Paused and replaced the contradictory Project
  closed bidding phrase with Not accepting bids.
- Preserved old `all`, `open`, and `closed` query values as normalized aliases
  for existing bookmarks and links.
- Applied the same normalization, counts, labels, links, empty states, and
  owner actions to Flask and the Cloudflare Worker renderer.

## Evidence

- `01-mobile-client-dashboard-before.jpg`: mixed default stream and duplicated
  completed-work section at 390x844.
- `02-mobile-client-dashboard-after.jpg`: two-project Active lane at 390x844.
- `03-mobile-client-paused-after.jpg`: owner-facing Paused state and management
  actions.
- `04-mobile-client-history-after.jpg`: completion evidence and repeat-work
  actions isolated in History.
- `05-desktop-client-dashboard-after.jpg`: compact desktop project workspace.
- `06-mobile-client-dashboard-before-after.jpg`: aligned source and accepted
  implementation in one comparison image.
- `07-tablet-client-dashboard-after.jpg`: stable tablet hierarchy and complete
  project rows at 820x1180.

## Acceptance

Browser DOM inspection exposed four specific status links and only the two open
projects in the default Active region. Paused exposed both hidden projects as
Manage links with Not accepting bids. History exposed the completed project
once with Review, Save template, Post again, and Invite again. The active phone
page fell from 2,241 to 1,014 pixels while preserving the established bottom
task navigation and same-domain project routes. The accepted 820x1180 and
1280x720 states keep all four lanes and both active rows visible without text
or control overlap.

## Privacy And Compatibility

The correction filters the existing owner-only dashboard payload. It adds no
route, database field, public response, address, contact value, notification,
rank, or identity inference. The three legacy view values normalize before the
same status filtering; authorization and project-detail permissions are
unchanged.

## Limits

The local browser used seeded owner data and did not exercise production Clerk,
D1, Queues, Email, or Cloudflare Images. The full-page capture utility may
repeat fixed navigation while stitching; DOM inspection is authoritative for
project count and accessible names. Production authentication, private media,
performance, and service-operation checks remain release gates.
