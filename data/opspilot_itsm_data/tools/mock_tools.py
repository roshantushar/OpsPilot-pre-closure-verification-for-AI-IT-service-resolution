"""Read-only mock enterprise tools for OpsPilot (the ONLY way OpsPilot should see state).

    from tools.mock_tools import MockITSM
    env = MockITSM("public/states/lh-03-run1.json")
    env.get_okta_user("nikhil.lau@acme.example")

Contract for every tool:
  RETURNS  {"ok": True, "count": n, "results": [...]}  (deep copies; never live state)
  FAILS    {"ok": False, "error": "503 Service Unavailable", "system": ...} when the
           system is unavailable for this case; {"ok": True, "count": 0, ...} when not found
  IRREVERSIBLE?  No. There are no write tools.
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MockITSM:
    def __init__(self, state_file):
        p = Path(state_file)
        self._state = json.loads((p if p.is_absolute() else ROOT / p).read_text())
        self.calls = []  # call log for traces

    def _query(self, system, table, **match):
        self.calls.append({"system": system, "table": table, "match": match})
        if system in self._state.get("_unavailable", []):
            return {"ok": False, "error": "503 Service Unavailable", "system": system}
        rows = [copy.deepcopy(r) for r in self._state[system][table].values()
                if all(r.get(k) == v for k, v in match.items())]
        return {"ok": True, "count": len(rows), "results": rows}

    # HR (source of truth for employment)
    def get_hr_employee(self, email: str):
        """Employment status, department, manager, legal-hold flag, notes."""
        return self._query("hr", "employees", email=email)

    # Identity and collaboration
    def get_okta_user(self, email: str):
        """Okta status, groups, active sessions, reset flags."""
        return self._query("okta", "users", email=email)

    def get_google_user(self, email: str):
        """Google Workspace suspension, org unit, OAuth tokens, data transfer, deletion."""
        return self._query("google_workspace", "users", email=email)

    def get_slack_user(self, email: str):
        """Slack deactivation flag."""
        return self._query("slack", "users", email=email)

    # Devices
    def list_devices(self, owner_email: str):
        """All Intune devices owned by a user."""
        return self._query("intune", "devices", owner=owner_email)

    def get_device(self, device_id: str):
        """One Intune device by id (includes its owner)."""
        return self._query("intune", "devices", device_id=device_id)

    # ServiceNow
    def get_incident(self, number: str):
        """Incident state, hold reason, escalation, category, priority, work notes."""
        return self._query("servicenow", "incidents", number=number)

    def list_slas(self, incident_number: str):
        return self._query("servicenow", "slas", incident=incident_number)

    def list_approvals(self, ticket_number: str):
        return self._query("servicenow", "approvals", ticket=ticket_number)

    def list_security_exceptions(self, employee_email: str):
        """Legal holds and other security exceptions."""
        return self._query("servicenow", "security_exceptions", employee_email=employee_email)

    # Runbooks (direct lookup; no RAG needed)
    @staticmethod
    def lookup_runbook(runbook_id: str):
        p = ROOT / "runbooks" / f"{runbook_id}.md"
        if not p.exists():
            return {"ok": False, "error": f"runbook {runbook_id} not found"}
        return {"ok": True, "runbook_id": runbook_id, "text": p.read_text()}


TOOL_NAMES = ["get_hr_employee", "get_okta_user", "get_google_user", "get_slack_user",
              "list_devices", "get_device", "get_incident", "list_slas", "list_approvals",
              "list_security_exceptions", "lookup_runbook"]
