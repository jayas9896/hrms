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

LEAVE_FIELDS = (
	"name",
	"employee",
	"employee_name",
	"leave_type",
	"from_date",
	"to_date",
	"total_leave_days",
	"status",
)

ATTENDANCE_FIELDS = (
	"name",
	"employee",
	"employee_name",
	"attendance_date",
	"status",
	"company",
)

ROSTER_EVENT_FIELDS = (
	"name",
	"employee",
	"employee_name",
	"shift_type",
	"start_date",
	"end_date",
	"status",
)

PAYROLL_SLIP_FIELDS = (
	"name",
	"employee",
	"employee_name",
	"start_date",
	"end_date",
	"net_pay",
	"gross_pay",
	"status",
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


def list_payroll_slips(frappe: Any, request: Any, *, request_id: str | None) -> dict[str, Any]:
	args = getattr(request, "args", {})
	limit = _bounded_limit(args.get("limit"))
	filters = {}
	employee_id = args.get("employeeId")
	if employee_id:
		filters["employee"] = employee_id
	rows = frappe.get_all(
		"Salary Slip",
		fields=list(PAYROLL_SLIP_FIELDS),
		filters=filters,
		order_by="end_date desc, modified desc",
		limit_page_length=limit,
	)
	return {
		"request_id": request_id,
		"items": [_payroll_slip_payload(row) for row in rows],
		"limit": limit,
		"nextCursor": None,
	}


def list_roster_events(frappe: Any, request: Any, *, request_id: str | None) -> dict[str, Any]:
	args = getattr(request, "args", {})
	limit = _bounded_limit(args.get("limit"))
	filters = {}
	employee_id = args.get("employeeId")
	if employee_id:
		filters["employee"] = employee_id
	rows = frappe.get_all(
		"Shift Assignment",
		fields=list(ROSTER_EVENT_FIELDS),
		filters=filters,
		order_by="start_date desc, modified desc",
		limit_page_length=limit,
	)
	return {
		"request_id": request_id,
		"items": [_roster_event_payload(row) for row in rows],
		"limit": limit,
		"nextCursor": None,
	}


def list_attendance(frappe: Any, request: Any, *, request_id: str | None) -> dict[str, Any]:
	args = getattr(request, "args", {})
	limit = _bounded_limit(args.get("limit"))
	filters = {}
	employee_id = args.get("employeeId")
	if employee_id:
		filters["employee"] = employee_id
	rows = frappe.get_all(
		"Attendance",
		fields=list(ATTENDANCE_FIELDS),
		filters=filters,
		order_by="attendance_date desc, modified desc",
		limit_page_length=limit,
	)
	return {
		"request_id": request_id,
		"items": [_attendance_payload(row) for row in rows],
		"limit": limit,
		"nextCursor": None,
	}


def list_leaves(frappe: Any, request: Any, *, request_id: str | None) -> dict[str, Any]:
	args = getattr(request, "args", {})
	limit = _bounded_limit(args.get("limit"))
	filters = {}
	employee_id = args.get("employeeId")
	if employee_id:
		filters["employee"] = employee_id
	rows = frappe.get_all(
		"Leave Application",
		fields=list(LEAVE_FIELDS),
		filters=filters,
		order_by="from_date desc, modified desc",
		limit_page_length=limit,
	)
	return {
		"request_id": request_id,
		"items": [_leave_payload(row) for row in rows],
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


def _leave_payload(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"leaveId": row.get("name"),
		"employeeId": row.get("employee"),
		"employeeName": row.get("employee_name"),
		"leaveType": row.get("leave_type"),
		"fromDate": _string_value(row.get("from_date")),
		"toDate": _string_value(row.get("to_date")),
		"totalDays": row.get("total_leave_days"),
		"status": row.get("status"),
	}


def _attendance_payload(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"attendanceId": row.get("name"),
		"employeeId": row.get("employee"),
		"employeeName": row.get("employee_name"),
		"attendanceDate": _string_value(row.get("attendance_date")),
		"status": row.get("status"),
		"company": row.get("company"),
	}


def _roster_event_payload(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"eventId": row.get("name"),
		"employeeId": row.get("employee"),
		"employeeName": row.get("employee_name"),
		"shiftType": row.get("shift_type"),
		"startDate": _string_value(row.get("start_date")),
		"endDate": _string_value(row.get("end_date")),
		"status": row.get("status"),
	}


def _payroll_slip_payload(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"salarySlipId": row.get("name"),
		"employeeId": row.get("employee"),
		"employeeName": row.get("employee_name"),
		"startDate": _string_value(row.get("start_date")),
		"endDate": _string_value(row.get("end_date")),
		"netPay": row.get("net_pay"),
		"grossPay": row.get("gross_pay"),
		"status": row.get("status"),
	}


def _string_value(value: object) -> object:
	return value.isoformat() if hasattr(value, "isoformat") else value
