# Dhruvanta HRMS Service Auth Integration

Status: **CONTRACT LOCKED; VERIFIER CORE SOURCE-READY; NOT WIRED YET**.

Dhruvanta HRMS currently serves the Frappe HR application and whitelisted Frappe methods through the gateway path:

```text
https://api.dhruvantasystems.net/hrms/api
```

Those current endpoints use Frappe session/API-key behavior, not Dhruvanta ES256 service-client JWT verification.

The framework-neutral verifier core now lives in
`hrms/service_auth/verifier.py`. It validates ES256 tokens from the service
control plane, audience `hrms`, expiry, JWKS `kid`, and endpoint scopes. The
Frappe request hook, JWKS discovery/cache, and `/api/v1/service/hrms/*`
handlers are still not wired.

## Locked Dhruvanta Service Contract

The future service-auth surface is reserved under:

```text
/api/v1/service/hrms/*
```

The resource-server audience is:

```text
hrms
```

The contract follows `/home/jayas/dhruvanta-platform-governance/docs/standards/service-to-service-auth.md`:

- ES256 bearer JWTs from the service control plane.
- `aud` must equal `hrms`.
- `scope` must include the endpoint-specific permission.
- Missing, expired, malformed, wrong-audience, or insufficient-scope tokens fail closed.
- No unauthenticated fallback to Frappe session auth is allowed for `/api/v1/service/hrms/*`.
- Service-client groups must be provisioned in SCP at group level, not as broad shared clients.

## Reserved Scope Groups

| Group | Scopes | Purpose |
| --- | --- | --- |
| `hrms.read` | `hrms:employee.read`, `hrms:leave.read`, `hrms:attendance.read`, `hrms:payroll.read`, `hrms:roster.read` | Dhruvanta One and support read-only dashboards. |
| `hrms.write` | `hrms:employee.write`, `hrms:leave.write`, `hrms:attendance.write`, `hrms:roster.write` | Controlled internal automation. |
| `hrms.admin` | `hrms:admin.read`, `hrms:admin.write`, `hrms:audit.read` | Admin/support operations with additional human approval gates. |

## Current Whitelisted Surfaces

The upstream HRMS app exposes many Frappe whitelisted methods. The Dhruvanta-facing subset used by current UI shells is:

- `hrms.api.get_current_user_info`
- `hrms.api.get_current_employee_info`
- `hrms.api.get_all_employees`
- `hrms.api.get_hr_settings`
- `hrms.api.get_attendance_calendar_events`
- `hrms.api.get_leave_applications`
- `hrms.api.get_leave_balance_map`
- `hrms.api.get_expense_claims`
- `hrms.api.get_expense_claim_summary`
- `hrms.api.get_attachments`
- `hrms.api.upload_base64_file`
- `hrms.api.roster.get_events`
- `hrms.api.oauth.oauth_providers` (guest)
- `hrms.api.system_settings.get_user_pass_login_disabled` (guest)

Frontend engineers must treat this current surface as Frappe-session based. Customer signup/login/onboarding should be driven by Dhruvanta One and/or the future SSO workspace provisioning flow, not by exposing broad upstream admin credentials.

## Implementation Gate

Before changing the status from contract-locked to live:

1. Mount the dedicated service-auth verifier from `hrms/service_auth/verifier.py`
   in a Frappe request hook with JWKS discovery/cache and `kid` refresh.
2. Add explicit route handlers for `/api/v1/service/hrms/*`.
3. Add source tests for 401 missing-token, 401 wrong-audience, 403 missing-scope, and success.
4. Add OpenAPI examples and curl smoke commands.
5. Update the governance registry and repo log in the same slice.
