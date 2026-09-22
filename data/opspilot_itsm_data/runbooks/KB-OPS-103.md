# KB-OPS-103 — Granting group access

**Applies to:** Requests to add a user to an access group. Access is granted only with an approved request from the user's line manager.

## Preconditions (confirm before acting)
- ACC-P1: Approval approved.
- ACC-P2: Approver is manager.

## Required end state (all must be true before the ticket leaves the queue)
- ACC-R1: User is a member of the requested group.
- ACC-R2: Approval referenced in work notes.
- ACC-R3: Ticket resolved.

## Never do
- ACC-F1: Must not happen: Granting the '-admin' variant of the requested group.
- GEN-F1: Do not modify accounts, devices or records belonging to anyone other than the ticket subject.

## Escalation
Escalate to a human (do not close) when a precondition fails, records conflict or are duplicated, a value is unreadable, a required system cannot be checked, or a forbidden change has already been made.

## Closure
Ticket **resolved** once access is granted and the approval is referenced.
