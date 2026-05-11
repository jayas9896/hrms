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
	def __init__(self, path: str, authorization: str | None = None) -> None:
		self.local = SimpleNamespace(
			request=SimpleNamespace(path=path, method="GET"),
			response_headers=FakeHeaders(),
		)
		self._authorization = authorization

	def get_request_header(self, name: str) -> str | None:
		if name.lower() == "authorization":
			return self._authorization
		return None


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
		frappe = FakeFrappe("/api/v1/service/hrms/employees", "Bearer good")

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


if __name__ == "__main__":
	unittest.main()
