# KB-OPS-104 — Placing an incident on hold

**Applies to:** Incidents blocked on the caller. Putting an incident on hold has a mandatory consequence: the SLA timer must be paused.

## Preconditions (confirm before acting)
- HLD-P1: SLA not already breached.

## Required end state (all must be true before the ticket leaves the queue)
- HLD-R1: Incident on hold.
- HLD-R2: Hold reason Awaiting Caller.
- HLD-R3: SLA paused.
- HLD-R4: Work note mentions awaiting caller.

## Never do
- HLD-F1: Must not happen: Incident resolved/closed.
- GEN-F1: Do not modify accounts, devices or records belonging to anyone other than the ticket subject.

## Escalation
Escalate to a human (do not close) when a precondition fails, records conflict or are duplicated, a value is unreadable, a required system cannot be checked, or a forbidden change has already been made.

## Closure
Incident stays **on_hold** (not resolved).
