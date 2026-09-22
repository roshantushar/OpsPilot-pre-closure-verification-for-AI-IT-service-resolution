# KB-OPS-106 — Account lockout and MFA reset

**Applies to:** Users locked out of Okta after identity has been verified by the service desk. Only current, active employees may be unlocked.

## Preconditions (confirm before acting)
- LCK-P1: HR status active.

## Required end state (all must be true before the ticket leaves the queue)
- LCK-R1: Okta unlocked (ACTIVE).
- LCK-R2: Password reset required.
- LCK-R3: MFA reset issued.
- LCK-R4: Work note records identity verified.
- LCK-R5: Ticket resolved.

## Never do
- GEN-F1: Do not modify accounts, devices or records belonging to anyone other than the ticket subject.

## Escalation
Escalate to a human (do not close) when a precondition fails, records conflict or are duplicated, a value is unreadable, a required system cannot be checked, or a forbidden change has already been made.

## Closure
Ticket **resolved** once access is restored safely.
