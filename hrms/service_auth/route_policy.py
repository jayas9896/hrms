"""Fail-closed HRMS service-auth route policy."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlsplit


class UnsupportedServiceRoute(Exception):
	"""Raised when a request is not part of the locked service API."""


@dataclass(frozen=True)
class RouteRule:
	method: str
	path_pattern: str
	required_scope: str

	def matches(self, method: str, path: str) -> bool:
		if self.method != method:
			return False
		pattern = "^" + re.sub(r"\\{[^/]+\\}", r"[^/]+", re.escape(self.path_pattern)) + "$"
		return re.match(pattern, path) is not None


@dataclass(frozen=True)
class ServiceRoutePolicy:
	rules: tuple[RouteRule, ...]

	@classmethod
	def default(cls) -> "ServiceRoutePolicy":
		return cls(
			(
				RouteRule("GET", "/api/v1/service/hrms/health", "hrms:admin.read"),
				RouteRule("GET", "/api/v1/service/hrms/employees", "hrms:employee.read"),
				RouteRule("POST", "/api/v1/service/hrms/employees", "hrms:employee.write"),
				RouteRule("GET", "/api/v1/service/hrms/employees/{employeeId}", "hrms:employee.read"),
				RouteRule("GET", "/api/v1/service/hrms/leaves", "hrms:leave.read"),
				RouteRule("POST", "/api/v1/service/hrms/leaves", "hrms:leave.write"),
				RouteRule("GET", "/api/v1/service/hrms/attendance", "hrms:attendance.read"),
				RouteRule("POST", "/api/v1/service/hrms/attendance/checkins", "hrms:attendance.write"),
				RouteRule("GET", "/api/v1/service/hrms/roster/events", "hrms:roster.read"),
				RouteRule("POST", "/api/v1/service/hrms/roster/assignments", "hrms:roster.write"),
				RouteRule("GET", "/api/v1/service/hrms/payroll/slips", "hrms:payroll.read"),
				RouteRule("GET", "/api/v1/service/hrms/audit-events", "hrms:audit.read"),
			)
		)

	def required_scope(self, method: str, path: str) -> str:
		normalized_method = method.strip().upper()
		normalized_path = urlsplit(path).path
		for rule in self.rules:
			if rule.matches(normalized_method, normalized_path):
				return rule.required_scope
		raise UnsupportedServiceRoute(
			f"unsupported service route: {normalized_method} {normalized_path}"
		)
