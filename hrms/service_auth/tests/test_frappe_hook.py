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
	) -> None:
		self.local = SimpleNamespace(
			request=SimpleNamespace(path=path, method="GET", args=args or {}),
			response_headers=FakeHeaders(),
		)
		self._authorization = authorization
		self._employees = employees or []
		self._employee = employee
		self._leaves = leaves or []
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
		frappe = FakeFrappe("/api/v1/service/hrms/attendance", "Bearer good")

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


if __name__ == "__main__":
	unittest.main()
