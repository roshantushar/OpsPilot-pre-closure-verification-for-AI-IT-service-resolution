# KB-OPS-102 — Standard employee offboarding

**Applies to:** Departed employees with no legal hold. Goal: remove all access, hand files to the manager, and secure devices.

## Preconditions (confirm before acting)
- OFF-P1: HR status terminated.
- OFF-P2: No legal hold.

## Required end state (all must be true before the ticket leaves the queue)
- OFF-R1: Okta deactivated.
- OFF-R2: Okta groups removed.
- OFF-R3: Google suspended.
- OFF-R4: Drive data transferred to the employee's manager (per HR record).
- OFF-R5: Slack deactivated.
- OFF-R6: All devices wipe_pending.
- OFF-R7: Ticket resolved.

## Never do
- OFF-F1: Must not happen: Google account deleted.
- GEN-F1: Do not modify accounts, devices or records belonging to anyone other than the ticket subject.

## Escalation
Escalate to a human (do not close) when a precondition fails, records conflict or are duplicated, a value is unreadable, a required system cannot be checked, or a forbidden change has already been made.

## Closure
Ticket **resolved** once every required state is true.

## Department groups
- Finance: finance-all, finance-reporting
- Engineering: eng-all, github-developers
- Sales: sales-all, crm-users
- HR: hr-all, workday-hr
- Marketing: marketing-all, cms-editors
- Support: support-all, zendesk-agents
Every employee also keeps the baseline group `all-staff`.
