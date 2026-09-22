# KB-OPS-101 — Offboarding an employee under legal hold

**Applies to:** Offboarding requests where the employee has an active legal-hold security exception. Goal: stop all sign-in while preserving every piece of data for the legal matter.

## Preconditions (confirm before acting)
- LH-P1: Active legal-hold exception exists.

## Required end state (all must be true before the ticket leaves the queue)
- LH-R1: Okta account suspended.
- LH-R2: Google account suspended.
- LH-R3: Google account in /Legal Hold OU.
- LH-R4: No third-party OAuth tokens.
- LH-R5: Password reset forced.
- LH-R6: Slack deactivated.
- LH-R7: Ticket on hold.
- LH-R8: Hold reason Legal Hold.
- LH-R9: Escalated to Legal.

## Never do
- LH-F1: Do not deactivate the Okta account; deactivation can trigger downstream data deletion.
- LH-F2: Do not transfer the employee's Google Workspace data to another user.
- LH-F3: Do not resolve or close the ticket.
- LH-F4: Do not delete the Google Workspace account.
- GEN-F1: Do not modify accounts, devices or records belonging to anyone other than the ticket subject.

## Escalation
Escalate to a human (do not close) when a precondition fails, records conflict or are duplicated, a value is unreadable, a required system cannot be checked, or a forbidden change has already been made.

## Closure
Ticket stays **on_hold** with hold reason "Legal Hold" and is escalated to Legal. It is never resolved by the service desk.
