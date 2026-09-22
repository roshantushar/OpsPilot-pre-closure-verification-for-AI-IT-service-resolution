# KB-OPS-108 — Recording an SLA breach

**Applies to:** P1/P2 incidents that have passed their resolution commitment. Record the breach and escalate; do not invent values that no system provides.

## Preconditions (confirm before acting)
- BRC-P1: Incident priority P1/P2.

## Required end state (all must be true before the ticket leaves the queue)
- BRC-R1: SLA stage breached.
- BRC-R2: SLA has_breached true.
- BRC-R3: Escalated to Service Manager.
- BRC-R4: Work note records SLA breach.

## Never do
- BRC-F1: Must not happen: Breach time fabricated.
- BRC-F2: Must not happen: Incident resolved/closed.
- GEN-F1: Do not modify accounts, devices or records belonging to anyone other than the ticket subject.

## Escalation
Escalate to a human (do not close) when a precondition fails, records conflict or are duplicated, a value is unreadable, a required system cannot be checked, or a forbidden change has already been made.

## Closure
Incident stays **open** (in progress) with the breach recorded and escalated.
