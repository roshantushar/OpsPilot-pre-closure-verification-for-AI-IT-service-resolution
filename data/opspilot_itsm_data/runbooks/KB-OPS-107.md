# KB-OPS-107 — Role or department transfer

**Applies to:** Employees moving between departments. Access must follow the department recorded by HR.

## Preconditions (confirm before acting)
- TRF-P1: HR shows new department.

## Required end state (all must be true before the ticket leaves the queue)
- TRF-R1: Removed from the old department's groups (first department group).
- TRF-R2: Removed from the old department's groups (second department group).
- TRF-R3: Added to the new department's groups (first department group).
- TRF-R4: Added to the new department's groups (second department group).
- TRF-R5: Ticket resolved.

## Never do
- TRF-F1: Must not happen: Baseline all-staff removed.
- GEN-F1: Do not modify accounts, devices or records belonging to anyone other than the ticket subject.

## Escalation
Escalate to a human (do not close) when a precondition fails, records conflict or are duplicated, a value is unreadable, a required system cannot be checked, or a forbidden change has already been made.

## Closure
Ticket **resolved** once group membership matches the new department.

## Department groups
- Finance: finance-all, finance-reporting
- Engineering: eng-all, github-developers
- Sales: sales-all, crm-users
- HR: hr-all, workday-hr
- Marketing: marketing-all, cms-editors
- Support: support-all, zendesk-agents
Every employee also keeps the baseline group `all-staff`.
