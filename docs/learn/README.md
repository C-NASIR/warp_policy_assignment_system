# Learn PolicyOS

Learn is a read-only curriculum with two ordered sections:

1. **Concepts:** 20 lessons organized into five subsections, including a five-lesson organizational sequence.
2. **PolicyOS:** 15 lessons applying those concepts in the application.

The [content map](content-map.md) records the agreed titles and scope. The live
curriculum is in `frontend/content/learn`; its index lists all 35 lessons.
All 20 Concepts lessons and 15 PolicyOS walkthroughs are drafted.

The curriculum follows Rachel's growing fictional company. Root initially operates
the workspace, then delegates work to Morgan.
PolicyOS walkthroughs use a connected training deployment. They are
checked against the current screens and backend contracts; their draft status does
not claim a completed connected-user acceptance review. Each walkthrough records
its source evidence, relevant permissions, and the result learners should inspect.

## Template contract

- Preserve each lesson’s `content_id`, section, and sequence when authoring it.
- Section `meta.json` files and frontmatter `order` define the same lesson order.
- Outlines have `status: outline` and `reading_time: 0`. The UI shows them as
  placeholders without reading estimates or verification badges.
- Outline verification metadata refers to the curriculum structure only, not to
  reviewed lesson content or verified application instructions.
- When authoring a lesson, update its status, reading estimate, prerequisites,
  ownership, and implementation evidence using the existing quality process.
- Run `npm run learn:quality` in `frontend` to validate content, lint, and build.

The workflow audit and audience scenario record the implementation boundaries
used by this curriculum. They are supporting evidence rather than a substitute
for the live lesson order in the content map and section metadata.

The documentation UI is read-only. It does not collect completion state,
helpfulness votes, search misses, or other learning analytics, and it does not
display personalized or related-article recommendations.
