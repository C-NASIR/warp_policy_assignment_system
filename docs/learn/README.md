# Learn PolicyOS

Learn is a curriculum with three ordered sections:

1. **Concepts:** 16 lessons introducing the domain from first principles.
2. **PolicyOS:** 15 lessons applying those concepts in the application.
3. **Practice:** 12 lessons for experiments and independent challenges.

The [content map](content-map.md) records the agreed titles and scope. The live
curriculum is in `frontend/content/learn`; its index lists all 43 lessons.
All 16 Concepts lessons and 15 PolicyOS walkthroughs are drafted. The 12 Practice
lesson bodies remain exactly `Empty for Now`. Practice activities are placeholders.

PolicyOS walkthroughs follow Rachel in a connected training deployment. They are
checked against the current screens and backend contracts; their draft status does
not claim a completed connected-user acceptance review. Each walkthrough records
its source evidence, relevant permissions, and the result learners should inspect.

## Template contract

- Preserve each lesson’s `content_id`, section, and sequence when authoring it.
- Section `meta.json` files and frontmatter `order` define the same lesson order.
- Outlines have `status: outline` and `reading_time: 0`. The UI shows them as
  placeholders without reading estimates, verification badges, completion
  controls, or feedback forms.
- Outline verification metadata refers to the curriculum structure only, not to
  reviewed lesson content or verified application instructions.
- When authoring a lesson, update its status, reading estimate, prerequisites,
  ownership, and implementation evidence using the existing quality process.
- Run `npm run learn:quality` in `frontend` to validate content, lint, and build.

The workflow audit, audience scenario, and quality documents in this directory
remain supporting material from the previous learning center. Their historical
article inventories and phase completion statements do not describe this new
curriculum template.
