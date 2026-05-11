# Dhruvanta HRMS Service Auth Integration

Status: **CONTRACT LOCKED; AUTH GUARD SOURCE-WIRED; ALL LOCKED SERVICE ROUTES SOURCE-WIRED; BEARER-TOKEN PUBLIC READ/WRITE SMOKES PASSED**.

Dhruvanta HRMS currently serves the Frappe HR application and whitelisted Frappe methods through the gateway path:

```text
https://api.dhruvantasystems.net/hrms/api
```

Those current endpoints use Frappe session/API-key behavior, not Dhruvanta ES256 service-client JWT verification.

The framework-neutral verifier core now lives in
`hrms/service_auth/verifier.py`. It validates ES256 tokens from the service
control plane, audience `hrms`, expiry, JWKS `kid`, and endpoint scopes. It
also discovers and caches JWKS from the issuer metadata and refetches once on a
`kid` miss so key rotation can recover without restarting Frappe. The Frappe
`before_request` guard is source-wired in `hrms/hooks.py`. Hook-level handlers
exist for `GET /api/v1/service/hrms/health`,
`GET /api/v1/service/hrms/employees`,
`POST /api/v1/service/hrms/employees`, and
`GET /api/v1/service/hrms/employees/{employeeId}`, plus
`GET /api/v1/service/hrms/leaves`,
`POST /api/v1/service/hrms/leaves`,
`GET /api/v1/service/hrms/attendance`,
`POST /api/v1/service/hrms/attendance/checkins`,
`GET /api/v1/service/hrms/roster/events`,
`POST /api/v1/service/hrms/roster/assignments`,
`GET /api/v1/service/hrms/payroll/slips`, and
`GET /api/v1/service/hrms/audit-events`, and
`POST /api/v1/service/hrms/activations/dhruvanta-one`; all currently locked service routes in
`hrms/service_auth/route_policy.py` have explicit handlers. The guard uses that
route policy to reject non-contract method/path combinations before scope
verification.

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
| `hrms.activation` | `hrms:activation.provision` | Dhruvanta One activation receiver with non-secret provisioning metadata. |

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

Current status: the locked service-auth routes are source-wired and public
bearer-token read/write smokes have passed. Before adding new routes or
changing the contract:

1. Run successful bearer-token public smokes for the locked
   `/api/v1/service/hrms/*` routes with real SCP service-client tokens.
2. Add source tests for 401 missing-token, 401 wrong-audience, 403 missing-scope, and success.
3. Add OpenAPI examples and curl smoke commands.
4. Update the governance registry and repo log in the same slice.

Before write smokes on a fresh shared Frappe bench, seed minimal HRMS master
data:

```bash
taskset -c 0 nice -n 15 \
  /home/jayas/frappe-bench/env/bin/python \
  /home/jayas/hrms_root/hrms/scripts/seed-frappe-hrms-master-data.py \
  --bench /home/jayas/frappe-bench \
  --site erp.localhost
```

Use `Dhruvanta Unpaid Leave` for leave write smokes when no paid leave
allocation exists yet; it is seeded as leave-without-pay so the smoke does not
depend on payroll policy setup.
