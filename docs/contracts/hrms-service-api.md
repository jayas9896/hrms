# Dhruvanta HRMS Backend API Contract

Status: **CONTRACT LOCKED; AUTH GUARD SOURCE-WIRED; HEALTH, EMPLOYEE READ, LEAVE LIST, ATTENDANCE LIST, AND ROSTER EVENTS SOURCE-WIRED** for
`/api/v1/service/hrms/*`.

This document is the backend-first contract for Dhruvanta HRMS. It records what frontend shells can assume today and what backend routes must provide before HRMS is marked self-service in Dhruvanta One.

## Runtime Origins

| Surface | Origin |
| --- | --- |
| Public backend gateway | `https://api.dhruvantasystems.net/hrms/api` |
| Customer UI | `https://hrms.dhruvantasystems.com` |
| Admin UI | `https://admin.hrms.dhruvantasystems.com` |
| Support UI | `https://support.hrms.dhruvantasystems.com` |
| Local bench origin | `http://127.0.0.1:18080` with host header `erp.localhost` |

## Current Backend Reality

The active runtime is Frappe HR/ERPNext. Current methods are reached through Frappe's method API, for example:

```text
GET /api/method/hrms.api.get_current_user_info
GET /api/method/hrms.api.get_current_employee_info
GET /api/method/hrms.api.get_hr_settings
GET /api/method/hrms.api.get_leave_applications
GET /api/method/hrms.api.roster.get_events
GET /api/method/hrms.api.oauth.oauth_providers
```

Authenticated calls require the current Frappe session/API-key mechanism. Guest calls are limited to login discovery helpers.

The ES256/JWKS/scope verifier core is source-ready in
`hrms/service_auth/verifier.py`. It includes issuer discovery, JWKS caching, and
one-time `kid` miss refresh for key rotation readiness. The source-ready route policy in
`hrms/service_auth/route_policy.py` locks method/path-to-scope mapping and
rejects non-contract routes fail-closed. The Frappe `before_request` guard is
source-wired in `hrms/hooks.py`; hook-level handlers exist for health, employee
directory, employee detail reads, leave list reads, attendance list reads, and
roster event reads, while the remaining locked routes are still pending.

## Future Dhruvanta Service API

All future cross-product calls use:

```text
/api/v1/service/hrms/*
Authorization: Bearer <SCP ES256 JWT>
aud: hrms
```

### Planned Endpoints

| Method | Path | Scope | Frontend/Admin Need |
| --- | --- | --- | --- |
| `GET` | `/api/v1/service/hrms/health` | `hrms:admin.read` | Admin readiness card and Dhruvanta One onboarding check. |
| `GET` | `/api/v1/service/hrms/employees` | `hrms:employee.read` | Employee directory, customer dashboard search, support lookup. |
| `GET` | `/api/v1/service/hrms/employees/{employeeId}` | `hrms:employee.read` | Employee profile detail. |
| `POST` | `/api/v1/service/hrms/employees` | `hrms:employee.write` | Controlled service onboarding or migration import. |
| `GET` | `/api/v1/service/hrms/leaves` | `hrms:leave.read` | Leave calendar/list UI. |
| `POST` | `/api/v1/service/hrms/leaves` | `hrms:leave.write` | Leave request creation from Dhruvanta UI. |
| `GET` | `/api/v1/service/hrms/attendance` | `hrms:attendance.read` | Attendance timeline, metrics, dashboards. |
| `POST` | `/api/v1/service/hrms/attendance/checkins` | `hrms:attendance.write` | Controlled check-in integrations. |
| `GET` | `/api/v1/service/hrms/roster/events` | `hrms:roster.read` | Roster calendar and shift views. |
| `POST` | `/api/v1/service/hrms/roster/assignments` | `hrms:roster.write` | Admin shift planning. |
| `GET` | `/api/v1/service/hrms/payroll/slips` | `hrms:payroll.read` | Employee payroll self-service and support lookup. |
| `GET` | `/api/v1/service/hrms/audit-events` | `hrms:audit.read` | Dhruvanta One aggregated audit view. |

### Shared Request Rules

- Every write endpoint requires `Idempotency-Key`.
- Every response includes `request_id`.
- Pagination uses `cursor` and `limit`.
- Errors use `application/problem+json`:

```json
{
  "type": "https://dhruvantasystems.com/problems/forbidden",
  "title": "Forbidden",
  "status": 403,
  "code": "FORBIDDEN",
  "request_id": "req_..."
}
```

## Frontend Contract Notes

Frontend pages should be able to render these backend states without special-casing transport failures:

- `not_authenticated`: user has no Dhruvanta/Frappe session.
- `workspace_pending`: Dhruvanta One account exists, but HRMS workspace is not provisioned.
- `service_unavailable`: backend gateway reaches HRMS but Frappe/bench is unhealthy.
- `permission_denied`: authenticated user lacks customer/admin/support role.
- `partial_data`: dashboard loaded but an upstream Frappe module timed out.

Customer UI needs employee self-service, leave, attendance, expense, payroll summary, and notifications.
Customer signup/login/onboarding must be implemented through Dhruvanta One and service provisioning, not by exposing broad upstream admin credentials.
Admin UI needs workspace provisioning, employee import, approval queues, payroll controls, audit, and health.
Support UI needs read-only search, impersonation-free diagnostics, audit history, and field-level action controls.

## Not Ready Yet

HRMS must not be marked fully self-service until these are complete:

- Dhruvanta service-auth verifier is implemented and tested.
- Remaining `/api/v1/service/hrms/*` routes are backed by explicit handlers.
- Dhruvanta One onboarding can provision or link a Frappe workspace fail-closed.
- Admin/support realms use Dhruvanta auth and TOTP, not shared Frappe administrator credentials.
- Gateway route-registry tests cover HRMS route behavior.
