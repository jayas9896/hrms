"""Service-auth route handlers for Dhruvanta HRMS."""

from __future__ import annotations

from typing import Any


EMPLOYEE_FIELDS = (
	"name",
	"employee_name",
	"status",
	"company",
	"department",
	"designation",
	"user_id",
)


def list_employees(frappe: Any, request: Any, *, request_id: str | None) -> dict[str, Any]:
	limit = _bounded_limit(getattr(request, "args", {}).get("limit"))
	rows = frappe.get_all(
		"Employee",
		fields=list(EMPLOYEE_FIELDS),
		order_by="modified desc",
		limit_page_length=limit,
	)
	return {
		"request_id": request_id,
		"items": [_employee_payload(row) for row in rows],
		"limit": limit,
		"nextCursor": None,
	}


def get_employee(
		frappe: Any,
		employee_id: str,
		*,
		request_id: str | None,
) -> tuple[dict[str, Any], int]:
	row = frappe.get_value(
		"Employee",
		employee_id,
		fieldname=list(EMPLOYEE_FIELDS),
		as_dict=True,
	)
	if row is None:
		return {
			"request_id": request_id,
			"code": "HRMS_EMPLOYEE_NOT_FOUND",
			"message": "Employee not found",
		}, 404
	return {
		"request_id": request_id,
		"employee": _employee_payload(row),
	}, 200


def _bounded_limit(raw: object) -> int:
	try:
		parsed = int(str(raw)) if raw is not None else 50
	except ValueError:
		return 50
	return min(max(parsed, 1), 100)


def _employee_payload(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"employeeId": row.get("name"),
		"displayName": row.get("employee_name"),
		"status": row.get("status"),
		"company": row.get("company"),
		"department": row.get("department"),
		"designation": row.get("designation"),
		"userId": row.get("user_id"),
	}
