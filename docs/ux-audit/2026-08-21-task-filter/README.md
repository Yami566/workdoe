# Workdoe Family-to-Task Flow Audit

Date: 2026-08-21

Viewport: 390 x 844 in the Codex in-app browser

## Flow

1. Select `01 Yard & landscaping` on the public marketplace.
2. Select `Pressure washing` from the family-scoped Task control.
3. Confirm that list and approximate map contain only the matching project.
4. Choose `Post this task` and confirm that the same-page project dialog opens
   at Step 3 with pressure-washing scope questions.

## Findings

- The six numbered family choices remain visible as large touch targets.
- The task menu contains 12 yard and landscaping services and does not expose
  unrelated cleaning or systems tasks.
- The selected family, one-project count, map pin, task value, and posting
  action agree with one another.
- Exact task posting skips two already-resolved decisions without skipping the
  description, coarse location, timing, media, or review safeguards.
- Labels, native select semantics, progress text, and dialog structure are
  present in the captured DOM. A real screen-reader session and target-user
  comprehension study remain external acceptance work.

## Evidence

- `01-mobile-selected-task.png`
- `02-mobile-task-prefilled-composer.png`

## Research basis

- USWDS recommends a labeled native select for a bounded option set and calls
  for mobile, keyboard, zoom, and screen-reader testing in the actual product:
  https://designsystem.digital.gov/components/select/
  https://designsystem.digital.gov/components/select/accessibility-tests/

