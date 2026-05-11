#!/usr/bin/env python3
"""Verify Dhruvanta HRMS backend contract docs stay source-truthful."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "AGENTS.md",
    "docs/SERVICE_AUTH_INTEGRATION.md",
    "docs/contracts/hrms-service-api.md",
    "docs/openapi/hrms-service-api.openapi.yaml",
    "hrms/service_auth/verifier.py",
    "hrms/service_auth/route_policy.py",
    "hrms/service_auth/frappe_hook.py",
    "hrms/service_auth/service_handlers.py",
    "hrms/service_auth/tests/test_verifier.py",
    "hrms/service_auth/tests/test_route_policy.py",
    "hrms/service_auth/tests/test_frappe_hook.py",
    "hrms/api/__init__.py",
    "hrms/api/oauth.py",
    "hrms/api/roster.py",
    "hrms/api/system_settings.py",
]

REQUIRED_DOC_TOKENS = {
    "docs/SERVICE_AUTH_INTEGRATION.md": [
        "CONTRACT LOCKED; AUTH GUARD SOURCE-WIRED; HEALTH, EMPLOYEE READ, AND LEAVE LIST SOURCE-WIRED",
        "audience is:",
        "hrms",
        "fail closed",
        "/api/v1/service/hrms/*",
        "GET /api/v1/service/hrms/employees",
        "GET /api/v1/service/hrms/employees/{employeeId}",
        "GET /api/v1/service/hrms/leaves",
        "remaining service routes",
        "hrms:employee.read",
        "hrms:attendance.write",
        "hrms/service_auth/verifier.py",
        "hrms/service_auth/route_policy.py",
        "before_request",
    ],
    "docs/contracts/hrms-service-api.md": [
        "CONTRACT LOCKED; AUTH GUARD SOURCE-WIRED; HEALTH, EMPLOYEE READ, AND LEAVE LIST SOURCE-WIRED",
        "https://api.dhruvantasystems.net/hrms/api",
        "not by exposing broad upstream admin credentials",
        "workspace_pending",
        "permission_denied",
        "Idempotency-Key",
        "hrms/service_auth/verifier.py",
        "hrms/hooks.py",
        "Employee directory",
        "employee detail",
        "leave list",
    ],
    "docs/openapi/hrms-service-api.openapi.yaml": [
        "operationId: listHrmsEmployees",
        "operationId: createHrmsLeave",
        "operationId: createHrmsAttendanceCheckin",
        "operationId: listHrmsRosterEvents",
        "operationId: listHrmsPayrollSlips",
        "hrms:employee.read",
        "hrms:audit.read",
        "Idempotency-Key",
    ],
}

REQUIRED_SOURCE_TOKENS = {
    "hrms/api/__init__.py": [
        "def get_current_user_info",
        "def get_current_employee_info",
        "def get_leave_applications",
        "def get_expense_claims",
        "def upload_base64_file",
    ],
    "hrms/api/roster.py": [
        "def get_events",
        "def create_shift_schedule_assignment",
        "def swap_shift",
    ],
    "hrms/api/oauth.py": ["allow_guest=True", "def oauth_providers"],
    "hrms/api/system_settings.py": ["allow_guest=True", "def get_user_pass_login_disabled"],
    "hrms/service_auth/verifier.py": [
        "EXPECTED_AUDIENCE = \"hrms\"",
        "algorithms=[\"ES256\"]",
        "JwksCache",
        "force_refresh=True",
        "required_scope",
        "insufficient_scope",
    ],
    "hrms/service_auth/route_policy.py": [
        "ServiceRoutePolicy",
        "hrms:employee.read",
        "hrms:audit.read",
        "UnsupportedServiceRoute",
    ],
    "hrms/service_auth/frappe_hook.py": [
        "def before_request",
        "frappe.local.service_client",
        "WWW-Authenticate",
        "list_employees",
        "get_employee",
        "list_leaves",
    ],
    "hrms/service_auth/service_handlers.py": [
        "def list_employees",
        "def get_employee",
        "def list_leaves",
        "frappe.get_all",
        "frappe.get_value",
        "Employee",
        "Leave Application",
        "limit_page_length",
    ],
    "hrms/hooks.py": [
        "Dhruvanta modification",
        "hrms.service_auth.frappe_hook.before_request",
    ],
}

FORBIDDEN_LIVE_CLAIMS = [
    "Dhruvanta service-auth endpoints are live",
    "service-auth endpoints are live",
    "is fully self-service",
    "marked fully self-service now",
]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    if missing:
        fail(f"missing required files: {', '.join(missing)}")

    for path, tokens in REQUIRED_DOC_TOKENS.items():
        text = read(path)
        for token in tokens:
            if token not in text:
                fail(f"{path} missing token: {token}")
        for token in FORBIDDEN_LIVE_CLAIMS:
            if token in text:
                fail(f"{path} contains forbidden live claim: {token}")

    for path, tokens in REQUIRED_SOURCE_TOKENS.items():
        text = read(path)
        for token in tokens:
            if token not in text:
                fail(f"{path} missing expected source token: {token}")

    openapi = read("docs/openapi/hrms-service-api.openapi.yaml")
    if openapi.count("operationId:") < 10:
        fail("OpenAPI contract should expose at least 10 planned operations")
    if "remaining endpoints are not wired yet" not in openapi.lower():
        fail("OpenAPI description must state remaining endpoints are not wired yet")

    print("HRMS service-auth contract verifier passed")


if __name__ == "__main__":
    main()
