# Learn PolicyOS

This directory is the source of truth for the learning center's content plan.
Phase 1 covers audience definition, a workflow and behavior audit, the shared
teaching scenario, and the curriculum map. Phase 2 provides the Fumadocs and MDX
foundation at `/learn`. Phase 3 provides the first usable beginner curriculum.

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
5. Move the article to `approved`, record `last_verified`, and set the next
   quarterly review for workflow content or semiannual review for stable concepts.
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

## Phase 2 status

Phase 2 is implemented in `frontend`:

- Fumadocs MDX compiles and validates `frontend/content/learn`.
- `/learn/[[...slug]]` renders the landing page and articles.
- The PolicyOS-integrated layout provides desktop and mobile navigation, article
  metadata, generated tables of contents, and previous/next links.
- Connected deployments use the existing session proxy to protect `/learn`; the
  common content remains readable by every signed-in user.
- Product links explain missing permissions instead of exposing an unusable
  destination.
- One technical-review sample exists in each planned top-level section.

Full article search, contextual links from application controls, and practical
feature coverage remain Phase 4 work.

## Phase 3 status

Phase 3 is implemented in `frontend/content/learn`:

- The ordered B01–B10 beginner course follows Avery Chen from employee inputs
  through matching, resolution, explanations, change safety, overrides, history,
  and audit.
- Every P0 concept article required by the course is published under Core
  concepts.
- The glossary defines the terms used across the first usable release.
- Worked tables and answer-reveal checks let a novice reconstruct Avery's five
  assignment fields without requiring mutation access.
- Optional product links remain permission-aware, and the prose identifies when
  an administrator must perform a step.
- Claims remain tied to implementation and test evidence through article
  metadata.

The articles remain in `technical-review` until feature owners and target readers
complete the authoring and verification workflow above. Phase 3 implementation
does not mark that organizational review as complete.

## Phase 4 status

Phase 4 is implemented across the learning content and application shell:

- Every P0/P1 concept, workflow guide, feature reference, and troubleshooting
  article in the content map is published.
- Quick Find searches article titles, descriptions, headings, and body text in
  addition to its permission-filtered product pages and actions.
- Major product routes expose a contextual Help link to the relevant guide or
  reference article.
- Articles link back into application screens through permission-aware controls;
  unavailable actions explain the required permission.
- Article pages include responsive related-article cards generated from nearby
  content in the same curriculum section.

P2 reference depth and the formal quality and measurement program remain
later-phase work. Phase 4 articles remain in `technical-review` until their
workflow and reader reviews are complete.

## Phase 5 status

Phase 5 is implemented as an isolated client-side learning layer:

- The Practice section contains an Avery assignment lab, priority/cardinality
  simulator, effective-date simulator, and scored course knowledge check.
- Exercises use only the fictional teaching fixture and deterministic rules
  verified against backend tests. They never call the PolicyOS API or read or
  mutate workspace data.
- Every exercise labels its isolation and provides immediate outcome-specific
  feedback, explanations, and a reset or retry path.
- Learners can opt into per-article progress on their device. Progress uses one
  versioned local-storage record, is disabled by default, and can be cleared by
  choosing **Stop tracking**.
- The exercise layout and controls adapt to mobile widths and use native labels,
  fieldsets, radios, checkboxes, ranges, dates, and live feedback regions.

The Practice articles remain in `technical-review` until target readers complete
the usability and accessibility review. Phase 6 will formalize those checks and
measurement rather than expanding the exercise fixture into customer data.

## Phase 6 status

Phase 6 is implemented as a repeatable quality and measurement program:

- `npm run learn:quality` validates metadata, owners, review dates,
  implementation evidence, section navigation, article links, contextual help,
  lint, and the production build; CI runs the gate on relevant changes.
- A named role registry assigns every article to a maintained product area, and
  quarterly or semiannual due dates make stale content fail validation.
- The accessibility and usability review records implementation findings and a
  reusable target-reader protocol without fabricating organizational sign-off.
- Connected articles collect fixed-choice helpfulness feedback, and Quick Find
  records only debounced zero-result queries. Demo mode records neither.
- Users with `audit:read` can see aggregate helpfulness, articles needing
  attention, and unsuccessful searches on the Audit page. Raw user-level events
  are not exposed in that view.

Articles remain `technical-review` until their content owner and target reader
complete the organizational approval steps. Phase 6 supplies the enforcement,
review method, and product evidence needed to complete those sign-offs.
