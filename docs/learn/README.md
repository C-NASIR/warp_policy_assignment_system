# Learn PolicyOS: Phase 1

This directory is the source of truth for the learning center's content plan.
Phase 1 covers audience definition, a workflow and behavior audit, the shared
teaching scenario, and the curriculum map. It intentionally does not add the
`/learn` route or documentation packages; those belong to Phase 2.

## Deliverables

- [Audiences and teaching scenario](audiences-and-scenario.md) defines who the
  learning center serves and the fictional Avery Chen example used throughout.
- [Workflow audit](workflow-audit.md) records what the current application does,
  where it does it, and the claims authors can safely make.
- [Content map](content-map.md) is the build queue for beginner lessons, core
  concepts, guides, reference, and troubleshooting.

## Product decisions

1. The learning center lives at `/learn` inside the existing PolicyOS shell.
2. Connected deployments require a signed-in user. Every signed-in user can read
   the common learning content; an article's links back into PolicyOS remain
   permission-aware.
3. The beginner course follows one assignment from employee facts through
   matching, resolution, preview and approval, then history and audit.
4. Articles distinguish connected behavior from demo behavior. Demo mode is a
   visual sandbox, is non-persistent, and is not evidence that a production
   workflow supports an exercise.
5. The isolated Avery Chen scenario replaces the proposal's “Maya” example.
   `frontend/lib/demo-data.ts` already contains Maya Patel as an established
   manager, so reusing that name for a new hire would make examples ambiguous.
6. Written content and deterministic search come before interactive exercises or
   an AI documentation assistant.

## Content contract for Phase 2

Each MDX article should use this minimum frontmatter contract. `owner` is a team
or role, not necessarily a named person.

```yaml
title: Why an assignment was produced
description: Follow employee facts through matching and resolution.
section: start-here
order: 60
audiences:
  - operator
permissions:
  - employees:read
  - assignments:read
owner: policy-engine
status: draft
last_verified: 2026-09-05
review_by: 2026-12-05
verified_by:
  - backend/tests/test_assignment_explanations.py
```

Required fields are `title`, `description`, `section`, `order`, `audiences`,
`permissions`, `owner`, `status`, `last_verified`, `review_by`, and
`verified_by`. Use an empty `permissions` list for concepts that every signed-in
user can read. Permission metadata controls task links and callouts; it must not
silently remove the conceptual explanation.

Allowed statuses are `outline`, `draft`, `technical-review`, `product-review`,
`approved`, and `retired`.

## Authoring and verification workflow

1. Start from an entry in `content-map.md`; preserve its ID in the article as
   `content_id`.
2. Write the article against the connected application behavior in
   `workflow-audit.md` and cite the relevant implementation or test in
   `verified_by`.
3. Have the feature owner verify every procedural step in a connected workspace.
4. Have a reader from the primary audience complete the task without coaching.
5. Move the article to `approved`, record `last_verified`, and set a review date
   no more than 90 days later for workflow content or 180 days later for stable
   concepts.
6. When a feature changes, update its article in the same change set. If behavior
   cannot be verified, label the affected passage and do not present it as a
   supported workflow.

## Phase 1 completion check

- [x] Current features and visible workflows inventoried.
- [x] Connected and demo behavior separated.
- [x] Primary and secondary learner audiences defined.
- [x] Reusable fictional employee, account, fields, policies, and expected
      assignments defined.
- [x] Ordered beginner curriculum outlined.
- [x] Concepts, guides, reference, and troubleshooting queues outlined.
- [x] Permissions and implementation evidence attached to planned content.
- [ ] Product and feature owners have approved the baseline content map.

The unchecked approval is the only organizational sign-off; the repository
artifacts required to make that review are complete.

## Phase 2 handoff

Phase 2 should implement only the content foundation: MDX loading, the `/learn`
route, responsive reading layout, navigation, table of contents, article
metadata, and authenticated access. It should seed one short article from each
top-level section to validate information architecture without pulling Phase 3
writing into the infrastructure change.
