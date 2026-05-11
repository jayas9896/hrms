"""Service-auth route handlers for Dhruvanta HRMS."""

from __future__ import annotations

from datetime import date
import json
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

AUDIT_EVENT_FIELDS = (
	"name",
	"subject",
	"content",
	"operation",
	"status",
	"reference_doctype",
	"reference_name",
	"user",
	"full_name",
	"ip_address",
	"communication_date",
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


def create_employee(
		frappe: Any,
		request: Any,
		*,
		request_id: str | None,
) -> tuple[dict[str, Any], int]:
	idempotency_key = _header(frappe, "Idempotency-Key")
	if not idempotency_key:
		return _idempotency_required(request_id, "employee imports"), 428

	replayed = _find_completed_idempotency(frappe, idempotency_key)
	if replayed is not None:
		replayed["request_id"] = request_id
		replayed["replayed"] = True
		return replayed, 200

	body = _json_body(request)
	first_name = body.get("firstName") or body.get("first_name")
	company = body.get("company")
	gender = body.get("gender")
	date_of_birth = body.get("dateOfBirth") or body.get("date_of_birth")
	date_of_joining = body.get("dateOfJoining") or body.get("date_of_joining")
	required = (
		("firstName", first_name),
		("company", company),
		("gender", gender),
		("dateOfBirth", date_of_birth),
		("dateOfJoining", date_of_joining),
	)
	missing = [name for name, value in required if not value]
	if missing:
		return _invalid_request(request_id, missing[0]), 400

	employee = _insert_doc(
		frappe,
		{
			"doctype": "Employee",
			"first_name": first_name,
			"middle_name": body.get("middleName") or body.get("middle_name"),
			"last_name": body.get("lastName") or body.get("last_name"),
			"employee_name": body.get("displayName") or body.get("employeeName"),
			"company": company,
			"gender": gender,
			"date_of_birth": date_of_birth,
			"date_of_joining": date_of_joining,
			"status": body.get("status") or "Active",
			"user_id": body.get("userId") or body.get("user_id"),
			"department": body.get("department"),
			"designation": body.get("designation"),
		},
	)
	response = {
		"request_id": request_id,
		"status": "accepted",
		"employeeId": employee.name,
		"idempotencyKey": idempotency_key,
	}
	_record_completed_idempotency(frappe, idempotency_key, response, "Employee", employee.name)
	frappe.db.commit()
	return response, 201


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


def list_audit_events(frappe: Any, request: Any, *, request_id: str | None) -> dict[str, Any]:
	limit = _bounded_limit(getattr(request, "args", {}).get("limit"))
	rows = frappe.get_all(
		"Activity Log",
		fields=list(AUDIT_EVENT_FIELDS),
		order_by="communication_date desc, creation desc",
		limit_page_length=limit,
	)
	return {
		"request_id": request_id,
		"items": [_audit_event_payload(row) for row in rows],
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


def create_roster_assignment(
		frappe: Any,
		request: Any,
		*,
		request_id: str | None,
) -> tuple[dict[str, Any], int]:
	idempotency_key = _header(frappe, "Idempotency-Key")
	if not idempotency_key:
		return _idempotency_required(request_id, "roster assignments"), 428

	replayed = _find_completed_idempotency(frappe, idempotency_key)
	if replayed is not None:
		replayed["request_id"] = request_id
		replayed["replayed"] = True
		return replayed, 200

	body = _json_body(request)
	employee_id = body.get("employeeId") or body.get("employee_id")
	shift_type = body.get("shiftType") or body.get("shift_type")
	start_date = body.get("startDate") or body.get("start_date")
	company = body.get("company")
	required = (
		("employeeId", employee_id),
		("shiftType", shift_type),
		("startDate", start_date),
		("company", company),
	)
	missing = [name for name, value in required if not value]
	if missing:
		return _invalid_request(request_id, missing[0]), 400

	assignment = _insert_doc(
		frappe,
		{
			"doctype": "Shift Assignment",
			"employee": employee_id,
			"shift_type": shift_type,
			"start_date": start_date,
			"end_date": body.get("endDate") or body.get("end_date"),
			"company": company,
			"status": body.get("status") or "Active",
			"shift_location": body.get("shiftLocation") or body.get("shift_location"),
			"overtime_type": body.get("overtimeType") or body.get("overtime_type"),
		},
	)
	response = {
		"request_id": request_id,
		"status": "accepted",
		"assignmentId": assignment.name,
		"idempotencyKey": idempotency_key,
	}
	_record_completed_idempotency(frappe, idempotency_key, response, "Shift Assignment", assignment.name)
	frappe.db.commit()
	return response, 201


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


def create_attendance_checkin(
		frappe: Any,
		request: Any,
		*,
		request_id: str | None,
) -> tuple[dict[str, Any], int]:
	idempotency_key = _header(frappe, "Idempotency-Key")
	if not idempotency_key:
		return _idempotency_required(request_id, "attendance check-ins"), 428

	replayed = _find_completed_idempotency(frappe, idempotency_key)
	if replayed is not None:
		replayed["request_id"] = request_id
		replayed["replayed"] = True
		return replayed, 200

	body = _json_body(request)
	employee_id = body.get("employeeId") or body.get("employee_id")
	checkin_time = body.get("time") or body.get("timestamp")
	missing = [
		name
		for name, value in (("employeeId", employee_id), ("time", checkin_time))
		if not value
	]
	if missing:
		return _invalid_request(request_id, missing[0]), 400

	checkin = _insert_doc(
		frappe,
		{
			"doctype": "Employee Checkin",
			"employee": employee_id,
			"time": checkin_time,
			"log_type": body.get("logType") or body.get("log_type"),
			"device_id": body.get("deviceId") or body.get("device_id"),
			"latitude": body.get("latitude"),
			"longitude": body.get("longitude"),
		},
	)
	response = {
		"request_id": request_id,
		"status": "accepted",
		"checkinId": checkin.name,
		"idempotencyKey": idempotency_key,
	}
	_record_completed_idempotency(frappe, idempotency_key, response, "Employee Checkin", checkin.name)
	frappe.db.commit()
	return response, 201


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


def create_leave_application(
		frappe: Any,
		request: Any,
		*,
		request_id: str | None,
) -> tuple[dict[str, Any], int]:
	idempotency_key = _header(frappe, "Idempotency-Key")
	if not idempotency_key:
		return _idempotency_required(request_id, "leave applications"), 428

	replayed = _find_completed_idempotency(frappe, idempotency_key)
	if replayed is not None:
		replayed["request_id"] = request_id
		replayed["replayed"] = True
		return replayed, 200

	body = _json_body(request)
	employee_id = body.get("employeeId") or body.get("employee_id")
	leave_type = body.get("leaveType") or body.get("leave_type")
	from_date = body.get("fromDate") or body.get("from_date")
	to_date = body.get("toDate") or body.get("to_date")
	company = body.get("company")
	required = (
		("employeeId", employee_id),
		("leaveType", leave_type),
		("fromDate", from_date),
		("toDate", to_date),
		("company", company),
	)
	missing = [name for name, value in required if not value]
	if missing:
		return _invalid_request(request_id, missing[0]), 400

	leave = _insert_doc(
		frappe,
		{
			"doctype": "Leave Application",
			"naming_series": body.get("namingSeries") or "HR-LAP-.YYYY.-",
			"employee": employee_id,
			"leave_type": leave_type,
			"from_date": from_date,
			"to_date": to_date,
			"half_day": 1 if body.get("halfDay") or body.get("half_day") else 0,
			"half_day_date": body.get("halfDayDate") or body.get("half_day_date"),
			"description": body.get("description"),
			"company": company,
			"posting_date": body.get("postingDate") or body.get("posting_date") or date.today().isoformat(),
			"status": body.get("status") or "Open",
		},
	)
	response = {
		"request_id": request_id,
		"status": "accepted",
		"leaveId": leave.name,
		"idempotencyKey": idempotency_key,
	}
	_record_completed_idempotency(frappe, idempotency_key, response, "Leave Application", leave.name)
	frappe.db.commit()
	return response, 201


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


def _insert_doc(frappe: Any, payload: dict[str, Any]) -> Any:
	doc = frappe.get_doc(payload)
	doc.flags.ignore_permissions = True
	doc = doc.insert(ignore_permissions=True)
	return doc


def _header(frappe: Any, name: str) -> str | None:
	value = frappe.get_request_header(name)
	return str(value).strip() if value else None


def _json_body(request: Any) -> dict[str, Any]:
	if hasattr(request, "get_json"):
		body = request.get_json(silent=True)
		if isinstance(body, dict):
			return body
	return {}


def _idempotency_required(request_id: str | None, resource_name: str) -> dict[str, Any]:
	return {
		"request_id": request_id,
		"code": "HRMS_IDEMPOTENCY_KEY_REQUIRED",
		"message": f"Idempotency-Key header is required for {resource_name}",
	}


def _invalid_request(request_id: str | None, missing_field: str) -> dict[str, Any]:
	return {
		"request_id": request_id,
		"code": "HRMS_INVALID_REQUEST",
		"message": f"Missing required field: {missing_field}",
	}


def _find_completed_idempotency(frappe: Any, key: str) -> dict[str, Any] | None:
	rows = frappe.get_all(
		"Integration Request",
		fields=["name", "status", "output"],
		filters={
			"integration_request_service": "dhruvanta-hrms-service-auth",
			"request_id": key,
		},
		limit_page_length=1,
	)
	if not rows or rows[0].get("status") != "Completed" or not rows[0].get("output"):
		return None
	try:
		parsed = json.loads(str(rows[0]["output"]))
	except (TypeError, ValueError):
		return None
	return parsed if isinstance(parsed, dict) else None


def _record_completed_idempotency(
		frappe: Any,
		key: str,
		output: dict[str, Any],
		reference_doctype: str,
		reference_docname: str,
) -> None:
	frappe.get_doc(
		{
			"doctype": "Integration Request",
			"integration_request_service": "dhruvanta-hrms-service-auth",
			"request_id": key,
			"status": "Completed",
			"output": json.dumps(output, separators=(",", ":")),
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname,
		}
	).insert(ignore_permissions=True)


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


def _audit_event_payload(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"eventId": row.get("name"),
		"subject": row.get("subject"),
		"content": row.get("content"),
		"operation": row.get("operation"),
		"status": row.get("status"),
		"referenceDoctype": row.get("reference_doctype"),
		"referenceName": row.get("reference_name"),
		"userId": row.get("user"),
		"userName": row.get("full_name"),
		"ipAddress": row.get("ip_address"),
		"eventTime": _string_value(row.get("communication_date")),
	}


def _string_value(value: object) -> object:
	return value.isoformat() if hasattr(value, "isoformat") else value
