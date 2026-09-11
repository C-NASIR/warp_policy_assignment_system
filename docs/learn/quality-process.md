# Learn PolicyOS quality process

## Release gate

Run `npm run learn:quality` from `frontend` before merging learning-center work.
The gate validates the MDX build, metadata contract, unique IDs, ownership,
review intervals, implementation evidence, section navigation, internal article
links, contextual help links, lint, and the production build. CI repeats the
same checks on changes to learning content or its supporting code.

Every feature change must update the affected article and its `verified_by`
evidence in the same pull request. A changed behavior resets `last_verified` and
sets `review_by` to the next quarterly review; stable concepts and reference
material may use a semiannual review. The automated gate allows up to 95 or 185
days so calendar-quarter and six-month dates are representable.

## Ownership and review

`content-owners.yml` is the registry of accountable product roles. Frontmatter
must use one of those exact owner names. The owner checks the connected product,
permission boundaries, empty/error states, and all cited tests. Product
Education checks plain language and curriculum placement. A target reader then
attempts the task without coaching before the article moves to `approved`.

## Accessibility and usability checklist

For every new or changed documentation page:

1. Navigate the page using keyboard only, including visible focus.
2. Confirm links, tables, landmarks, and navigation have usable accessible names
   and semantics.
3. Check zoom at 200%, narrow mobile layout, reduced motion, and text wrapping.
4. Ask one reader from the primary audience to complete the documented task
   without coaching and record the result in the review report.

## Read-only boundary

Documentation pages do not collect completion state, article reactions, search
queries, or other usage analytics. Content improvements come from the scheduled
owner review and moderated reader review described above. The UI may link between
articles and to relevant application pages, but it does not generate personalized
or related-article recommendations.

## Incident path

If documentation contradicts connected behavior, label or remove the unsafe
instruction immediately, open a product/documentation issue, and return the
article to `technical-review`. Security, permission, approval, or data-loss
claims are release blockers.
