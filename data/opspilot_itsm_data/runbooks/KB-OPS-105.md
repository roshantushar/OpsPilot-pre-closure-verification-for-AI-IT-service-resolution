# KB-OPS-105 — Lost or stolen laptop

**Applies to:** A user reports a lost or stolen company laptop. Goal: secure that device and the user's sessions without disrupting their other devices.

## Preconditions (confirm before acting)
- LST-P1: Lost device belongs to caller.

## Required end state (all must be true before the ticket leaves the queue)
- LST-R1: Lost mode enabled.
- LST-R2: Lost device locked.
- LST-R3: Okta sessions revoked.
- LST-R4: OAuth tokens revoked.
- LST-R5: Incident category security.
- LST-R6: Ticket resolved.

## Never do
- LST-F1: Must not happen: Other device locked/wiped.
- LST-F2: Must not happen: Okta deactivated.
- GEN-F1: Do not modify accounts, devices or records belonging to anyone other than the ticket subject.

## Escalation
Escalate to a human (do not close) when a precondition fails, records conflict or are duplicated, a value is unreadable, a required system cannot be checked, or a forbidden change has already been made.

## Closure
Ticket **resolved** once the device and sessions are secured.
