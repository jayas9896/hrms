"""Tests for HRMS service-auth route policy."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


POLICY_PATH = Path(__file__).resolve().parents[1] / "route_policy.py"
SPEC = importlib.util.spec_from_file_location("hrms_service_auth_route_policy", POLICY_PATH)
assert SPEC and SPEC.loader
route_policy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = route_policy
SPEC.loader.exec_module(route_policy)

ServiceRoutePolicy = route_policy.ServiceRoutePolicy
UnsupportedServiceRoute = route_policy.UnsupportedServiceRoute


class ServiceRoutePolicyTests(unittest.TestCase):
	def test_resolves_required_scopes_for_known_service_routes(self) -> None:
		policy = ServiceRoutePolicy.default()

		self.assertEqual(
			policy.required_scope("GET", "/api/v1/service/hrms/health"),
			"hrms:admin.read",
		)
		self.assertEqual(
			policy.required_scope("GET", "/api/v1/service/hrms/employees/EMP-0001"),
			"hrms:employee.read",
		)
		self.assertEqual(
			policy.required_scope("POST", "/api/v1/service/hrms/attendance/checkins"),
			"hrms:attendance.write",
		)
		self.assertEqual(
			policy.required_scope("GET", "/api/v1/service/hrms/audit-events?limit=50"),
			"hrms:audit.read",
		)

	def test_rejects_unknown_method_path_and_non_service_path(self) -> None:
		policy = ServiceRoutePolicy.default()

		for method, path in (
			("DELETE", "/api/v1/service/hrms/employees/EMP-0001"),
			("POST", "/api/v1/service/hrms/payroll/slips"),
			("GET", "/api/method/ping"),
		):
			with self.assertRaises(UnsupportedServiceRoute):
				policy.required_scope(method, path)


if __name__ == "__main__":
	unittest.main()
