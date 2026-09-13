# Learn curriculum map

The curriculum has 37 ordered lessons in two sections. All 21 Concepts lessons and 16 PolicyOS walkthroughs are drafted.

The learning story begins with a company hiring Rachel and gradually turning individual decisions into policies. After the assignment model is established, an organizational sequence follows the same company from one Root user through delegated responsibilities, scoped visibility, and independent review. PolicyOS walkthroughs then apply both stories in the application.

## Concepts — 21 lessons

### From decisions to assignments

1. **Your first employee:** The decisions every employer needs to make.
2. **From decisions to policies:** Turning repeated decisions into reusable rules.
3. **Who does a policy apply to?:** Employee facts and conditions.
4. **What does a policy give someone?:** Assignment fields and their possible values.
5. **What is an assignment?:** The difference between a general rule and one employee's result.

### How policies combine

6. **Combining conditions:** Expressing “all,” “any,” and “not.”
7. **When several policies apply:** Matching rules versus selecting results.
8. **One value or many?:** Why pay schedules and application access resolve differently.
9. **When policies disagree:** Priority and unresolved conflicts.

### Groups and exceptions

10. **Assigning through groups:** Applying shared policies through explicit membership.
11. **Making an exception:** Manual overrides and their relationship to policy results.

### Change, time, and evidence

12. **Policies over time:** Effective dates, versions, and scheduled changes.
13. **When circumstances change:** Recalculating assignments through reconciliation.
14. **Changing things safely:** Previewing a change before committing it.
15. **Explaining what happened:** Assignment explanations, history, and audit records.

### People, accounts, and access

16. **Who can do what?:** Root setup, the employee/account distinction, and the first delegated user.
17. **Turn responsibilities into roles:** Permissions as actions and roles as reusable bundles.
18. **Permissions and scopes work together:** Employee and assignment-field visibility as independent data boundaries.
19. **Access through the reporting tree:** Linked manager accounts, direct and indirect reports, and the mechanisms that remain separate.
20. **Access to your own information:** Combining a linked account, read permissions, and self scope in the existing application.

### Controlled access

21. **Separate proposing from authorizing:** Policy authorship, activation, approval, execution, and the full supported request lifecycle.

Lessons 16–21 are one connected organizational sequence. `CON16` is the entry point for the access model, and **Changing things safely** introduces preview safety. Independent organizational review has its primary conceptual home in lesson 21.

## PolicyOS — 16 lessons

1. **Find your way around:** Where employees, policies, assignments, and evidence live.
2. **Meet your first employee:** Read an employee record and identify the facts policies use.
3. **Define an assignment field:** Choose what policies can assign and whether it accepts one or many values.
4. **Create your first policy:** Connect a simple condition to an assignment value.
5. **Build richer conditions:** Use nested condition groups and derived facts.
6. **Preview and activate a policy:** Inspect its effect before putting it into use.
7. **Read an employee's assignments:** Trace a result back to its source.
8. **Handle competing policies:** Configure priority and investigate conflicts.
9. **Use groups:** Manage membership and attach policies.
10. **Manage an exception:** Add, inspect, and remove an override.
11. **Schedule a policy change:** Create a version with a future effective date.
12. **Update employee facts:** Follow the resulting assignment changes.
13. **Investigate past decisions:** Use assignment history and the audit log.
14. **Manage access:** Give Morgan a configured People operator role and user account.
15. **Limit access with scopes:** Configure reporting-tree, selected-field, and self access and verify their combination.
16. **Review controlled changes:** Follow Morgan's exact policy proposal through Jordan's decision and execution.

The existing `manage-access` and `review-controlled-changes` URLs and content IDs remain stable. **Review controlled changes** follows explicit access configuration so readers understand how Morgan and Jordan receive their different responsibilities before using them.
