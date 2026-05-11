"""Tests for HRMS service-auth Frappe before_request hook."""

from __future__ import annotations

from types import SimpleNamespace
import importlib.util
import types
from pathlib import Path
import sys
import unittest


SERVICE_AUTH_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path) -> object:
	spec = importlib.util.spec_from_file_location(name, path)
	assert spec and spec.loader
	module = importlib.util.module_from_spec(spec)
	sys.modules[name] = module
	spec.loader.exec_module(module)
	return module


sys.modules.setdefault("hrms", types.ModuleType("hrms"))
service_auth_pkg = types.ModuleType("hrms.service_auth")
service_auth_pkg.__path__ = [str(SERVICE_AUTH_ROOT)]
sys.modules.setdefault("hrms.service_auth", service_auth_pkg)
load_module("hrms.service_auth.route_policy", SERVICE_AUTH_ROOT / "route_policy.py")
load_module("hrms.service_auth.verifier", SERVICE_AUTH_ROOT / "verifier.py")

HOOK_PATH = SERVICE_AUTH_ROOT / "frappe_hook.py"
SPEC = importlib.util.spec_from_file_location("hrms_service_auth_frappe_hook", HOOK_PATH)
assert SPEC and SPEC.loader
frappe_hook = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = frappe_hook
SPEC.loader.exec_module(frappe_hook)

FrappeServiceAuthError = frappe_hook.FrappeServiceAuthError
before_request = frappe_hook.before_request


class FakeHeaders(dict):
	def set(self, key: str, value: str) -> None:
		self[key] = value


class FakeFrappe:
	def __init__(
			self,
			path: str,
			authorization: str | None = None,
			args: dict[str, str] | None = None,
			employees: list[dict[str, object]] | None = None,
			employee: dict[str, object] | None = None,
			leaves: list[dict[str, object]] | None = None,
			attendance: list[dict[str, object]] | None = None,
			roster_events: list[dict[str, object]] | None = None,
			payroll_slips: list[dict[str, object]] | None = None,
			audit_events: list[dict[str, object]] | None = None,
	) -> None:
		self.local = SimpleNamespace(
			request=SimpleNamespace(path=path, method="GET", args=args or {}),
			response_headers=FakeHeaders(),
		)
		self._authorization = authorization
		self._employees = employees or []
		self._employee = employee
		self._leaves = leaves or []
		self._attendance = attendance or []
		self._roster_events = roster_events or []
		self._payroll_slips = payroll_slips or []
		self._audit_events = audit_events or []
		self.get_all_calls = []
		self.get_value_calls = []

	def get_request_header(self, name: str) -> str | None:
		if name.lower() == "authorization":
			return self._authorization
		return None

	def get_all(self, doctype: str, **kwargs: object) -> list[dict[str, object]]:
		self.get_all_calls.append((doctype, kwargs))
		if doctype == "Leave Application":
			return self._leaves
		if doctype == "Attendance":
			return self._attendance
		if doctype == "Shift Assignment":
			return self._roster_events
		if doctype == "Salary Slip":
			return self._payroll_slips
		if doctype == "Activity Log":
			return self._audit_events
		return self._employees

	def get_value(
			self,
			doctype: str,
			name: str,
			fieldname: list[str],
			as_dict: bool,
	) -> dict[str, object] | None:
		self.get_value_calls.append((doctype, name, fieldname, as_dict))
		return self._employee


class StaticCache:
	def __init__(self, principal: object) -> None:
		self.principal = principal


class FakePrincipal:
	client_id = "dhruvanta-one"
	scopes = ("hrms:employee.read",)
	jti = "jti-1"


class FrappeHookTests(unittest.TestCase):
	def test_non_service_paths_are_ignored(self) -> None:
		frappe = FakeFrappe("/api/method/ping")

		before_request(frappe_module=frappe)

		self.assertFalse(hasattr(frappe.local, "service_client"))

	def test_service_path_requires_bearer_token_and_sets_header(self) -> None:
		frappe = FakeFrappe("/api/v1/service/hrms/employees")

		with self.assertRaises(FrappeServiceAuthError) as raised:
			before_request(frappe_module=frappe)

		self.assertEqual(raised.exception.http_status_code, 401)
		self.assertIn("WWW-Authenticate", frappe.local.response_headers)

	def test_valid_service_request_sets_service_client(self) -> None:
		frappe = FakeFrappe("/api/v1/service/hrms/audit-events", "Bearer good")

		with self.assertRaises(Exception):
			before_request(
				frappe_module=frappe,
				jwks_cache=StaticCache(FakePrincipal()),
				verify_token=lambda token, jwks_cache, required_scope: jwks_cache.principal,
			)

		self.assertEqual(frappe.local.service_client["id"], "dhruvanta-one")
		self.assertEqual(frappe.local.service_client["scopes"], ("hrms:employee.read",))
		self.assertEqual(frappe.local.service_client["jti"], "jti-1")

	def test_health_route_returns_json_response_from_hook(self) -> None:
		frappe = FakeFrappe("/api/v1/service/hrms/health", "Bearer good")

		with self.assertRaises(Exception) as raised:
			before_request(
				frappe_module=frappe,
				jwks_cache=StaticCache(FakePrincipal()),
				verify_token=lambda token, jwks_cache, required_scope: jwks_cache.principal,
			)

		response = raised.exception.get_response({})
		self.assertEqual(response.status_code, 200)
		self.assertIn(b'"service":"dhruvanta-hrms"', response.data)
		self.assertIn(b'"status":"ok"', response.data)

	def test_employee_list_route_returns_directory_payload(self) -> None:
		frappe = FakeFrappe(
			"/api/v1/service/hrms/employees",
			"Bearer good",
			args={"limit": "25"},
			employees=[
				{
					"name": "EMP-0001",
					"employee_name": "Ada Lovelace",
					"status": "Active",
					"company": "Dhruvanta Systems",
					"department": "Engineering",
					"designation": "Engineer",
					"user_id": "ada@example.test",
				}
			],
		)

		with self.assertRaises(Exception) as raised:
			before_request(
				frappe_module=frappe,
				jwks_cache=StaticCache(FakePrincipal()),
				verify_token=lambda token, jwks_cache, required_scope: jwks_cache.principal,
			)

		response = raised.exception.get_response({})
		self.assertEqual(response.status_code, 200)
		self.assertIn(b'"request_id":"jti-1"', response.data)
		self.assertIn(b'"employeeId":"EMP-0001"', response.data)
		self.assertIn(b'"displayName":"Ada Lovelace"', response.data)
		self.assertEqual(frappe.get_all_calls[0][0], "Employee")
		self.assertEqual(frappe.get_all_calls[0][1]["limit_page_length"], 25)

	def test_employee_detail_route_returns_employee_payload(self) -> None:
		frappe = FakeFrappe(
			"/api/v1/service/hrms/employees/EMP-0001",
			"Bearer good",
			employee={
				"name": "EMP-0001",
				"employee_name": "Ada Lovelace",
				"status": "Active",
				"company": "Dhruvanta Systems",
				"department": "Engineering",
				"designation": "Engineer",
				"user_id": "ada@example.test",
			},
		)

		with self.assertRaises(Exception) as raised:
			before_request(
				frappe_module=frappe,
				jwks_cache=StaticCache(FakePrincipal()),
				verify_token=lambda token, jwks_cache, required_scope: jwks_cache.principal,
			)

		response = raised.exception.get_response({})
		self.assertEqual(response.status_code, 200)
		self.assertIn(b'"request_id":"jti-1"', response.data)
		self.assertIn(b'"employeeId":"EMP-0001"', response.data)
		self.assertIn(b'"displayName":"Ada Lovelace"', response.data)
		self.assertEqual(frappe.get_value_calls[0][0], "Employee")
		self.assertEqual(frappe.get_value_calls[0][1], "EMP-0001")

	def test_employee_detail_route_returns_not_found_payload(self) -> None:
		frappe = FakeFrappe(
			"/api/v1/service/hrms/employees/EMP-MISSING",
			"Bearer good",
		)

		with self.assertRaises(Exception) as raised:
			before_request(
				frappe_module=frappe,
				jwks_cache=StaticCache(FakePrincipal()),
				verify_token=lambda token, jwks_cache, required_scope: jwks_cache.principal,
			)

		response = raised.exception.get_response({})
		self.assertEqual(response.status_code, 404)
		self.assertIn(b'"code":"HRMS_EMPLOYEE_NOT_FOUND"', response.data)
		self.assertIn(b'"request_id":"jti-1"', response.data)

	def test_leave_list_route_returns_leave_payload(self) -> None:
		frappe = FakeFrappe(
			"/api/v1/service/hrms/leaves",
			"Bearer good",
			args={"limit": "20", "employeeId": "EMP-0001"},
			leaves=[
				{
					"name": "LV-0001",
					"employee": "EMP-0001",
					"employee_name": "Ada Lovelace",
					"leave_type": "Privilege Leave",
					"from_date": "2026-05-10",
					"to_date": "2026-05-11",
					"total_leave_days": 2,
					"status": "Approved",
				}
			],
		)

		with self.assertRaises(Exception) as raised:
			before_request(
				frappe_module=frappe,
				jwks_cache=StaticCache(FakePrincipal()),
				verify_token=lambda token, jwks_cache, required_scope: jwks_cache.principal,
			)

		response = raised.exception.get_response({})
		self.assertEqual(response.status_code, 200)
		self.assertIn(b'"request_id":"jti-1"', response.data)
		self.assertIn(b'"leaveId":"LV-0001"', response.data)
		self.assertIn(b'"employeeId":"EMP-0001"', response.data)
		self.assertEqual(frappe.get_all_calls[-1][0], "Leave Application")
		self.assertEqual(frappe.get_all_calls[-1][1]["limit_page_length"], 20)
		self.assertEqual(
			frappe.get_all_calls[-1][1]["filters"],
			{"employee": "EMP-0001"},
		)

	def test_attendance_list_route_returns_attendance_payload(self) -> None:
		frappe = FakeFrappe(
			"/api/v1/service/hrms/attendance",
			"Bearer good",
			args={"limit": "15", "employeeId": "EMP-0001"},
			attendance=[
				{
					"name": "ATT-0001",
					"employee": "EMP-0001",
					"employee_name": "Ada Lovelace",
					"attendance_date": "2026-05-10",
					"status": "Present",
					"company": "Dhruvanta Systems",
				}
			],
		)

		with self.assertRaises(Exception) as raised:
			before_request(
				frappe_module=frappe,
				jwks_cache=StaticCache(FakePrincipal()),
				verify_token=lambda token, jwks_cache, required_scope: jwks_cache.principal,
			)

		response = raised.exception.get_response({})
		self.assertEqual(response.status_code, 200)
		self.assertIn(b'"request_id":"jti-1"', response.data)
		self.assertIn(b'"attendanceId":"ATT-0001"', response.data)
		self.assertIn(b'"employeeId":"EMP-0001"', response.data)
		self.assertEqual(frappe.get_all_calls[-1][0], "Attendance")
		self.assertEqual(frappe.get_all_calls[-1][1]["limit_page_length"], 15)
		self.assertEqual(
			frappe.get_all_calls[-1][1]["filters"],
			{"employee": "EMP-0001"},
		)

	def test_roster_events_route_returns_roster_payload(self) -> None:
		frappe = FakeFrappe(
			"/api/v1/service/hrms/roster/events",
			"Bearer good",
			args={"limit": "30", "employeeId": "EMP-0001"},
			roster_events=[
				{
					"name": "SHIFT-0001",
					"employee": "EMP-0001",
					"employee_name": "Ada Lovelace",
					"shift_type": "General",
					"start_date": "2026-05-10",
					"end_date": "2026-05-10",
					"status": "Active",
				}
			],
		)

		with self.assertRaises(Exception) as raised:
			before_request(
				frappe_module=frappe,
				jwks_cache=StaticCache(FakePrincipal()),
				verify_token=lambda token, jwks_cache, required_scope: jwks_cache.principal,
			)

		response = raised.exception.get_response({})
		self.assertEqual(response.status_code, 200)
		self.assertIn(b'"request_id":"jti-1"', response.data)
		self.assertIn(b'"eventId":"SHIFT-0001"', response.data)
		self.assertIn(b'"employeeId":"EMP-0001"', response.data)
		self.assertEqual(frappe.get_all_calls[-1][0], "Shift Assignment")
		self.assertEqual(frappe.get_all_calls[-1][1]["limit_page_length"], 30)
		self.assertEqual(
			frappe.get_all_calls[-1][1]["filters"],
			{"employee": "EMP-0001"},
		)

	def test_payroll_slips_route_returns_payroll_payload(self) -> None:
		frappe = FakeFrappe(
			"/api/v1/service/hrms/payroll/slips",
			"Bearer good",
			args={"limit": "10", "employeeId": "EMP-0001"},
			payroll_slips=[
				{
					"name": "SAL-0001",
					"employee": "EMP-0001",
					"employee_name": "Ada Lovelace",
					"start_date": "2026-05-01",
					"end_date": "2026-05-31",
					"net_pay": 125000,
					"gross_pay": 150000,
					"status": "Submitted",
				}
			],
		)

		with self.assertRaises(Exception) as raised:
			before_request(
				frappe_module=frappe,
				jwks_cache=StaticCache(FakePrincipal()),
				verify_token=lambda token, jwks_cache, required_scope: jwks_cache.principal,
			)

		response = raised.exception.get_response({})
		self.assertEqual(response.status_code, 200)
		self.assertIn(b'"request_id":"jti-1"', response.data)
		self.assertIn(b'"salarySlipId":"SAL-0001"', response.data)
		self.assertIn(b'"employeeId":"EMP-0001"', response.data)
		self.assertEqual(frappe.get_all_calls[-1][0], "Salary Slip")
		self.assertEqual(frappe.get_all_calls[-1][1]["limit_page_length"], 10)
		self.assertEqual(
			frappe.get_all_calls[-1][1]["filters"],
			{"employee": "EMP-0001"},
		)

	def test_audit_events_route_returns_activity_log_payload(self) -> None:
		frappe = FakeFrappe(
			"/api/v1/service/hrms/audit-events",
			"Bearer good",
			args={"limit": "12"},
			audit_events=[
				{
					"name": "ACT-0001",
					"subject": "Ada Lovelace updated",
					"content": "Employee record changed",
					"operation": "Update",
					"status": "Success",
					"reference_doctype": "Employee",
					"reference_name": "EMP-0001",
					"user": "admin@example.test",
					"full_name": "Admin User",
					"ip_address": "127.0.0.1",
					"communication_date": "2026-05-10 10:00:00",
				}
			],
		)

		with self.assertRaises(Exception) as raised:
			before_request(
				frappe_module=frappe,
				jwks_cache=StaticCache(FakePrincipal()),
				verify_token=lambda token, jwks_cache, required_scope: jwks_cache.principal,
			)

		response = raised.exception.get_response({})
		self.assertEqual(response.status_code, 200)
		self.assertIn(b'"request_id":"jti-1"', response.data)
		self.assertIn(b'"eventId":"ACT-0001"', response.data)
		self.assertIn(b'"subject":"Ada Lovelace updated"', response.data)
		self.assertEqual(frappe.get_all_calls[-1][0], "Activity Log")
		self.assertEqual(frappe.get_all_calls[-1][1]["limit_page_length"], 12)


if __name__ == "__main__":
	unittest.main()
