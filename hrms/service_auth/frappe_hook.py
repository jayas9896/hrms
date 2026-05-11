"""Frappe before_request hook for HRMS service-auth paths."""

from __future__ import annotations

import json
from typing import Any, Callable

from hrms.service_auth.route_policy import ServiceRoutePolicy, UnsupportedServiceRoute
from hrms.service_auth.service_handlers import list_employees
from hrms.service_auth.verifier import (
	JwksCache,
	ServiceAuthError,
	extract_bearer_token,
	verify_service_token_with_jwks_cache,
)


def _http_exception_base() -> type[Exception]:
	try:
		from werkzeug.exceptions import HTTPException

		return HTTPException
	except ModuleNotFoundError:
		return Exception


class FrappeServiceAuthError(Exception):
	def __init__(self, status_code: int, message: str) -> None:
		super().__init__(message)
		self.http_status_code = status_code


class FrappeServiceResponse(_http_exception_base()):
	def __init__(self, body: dict[str, Any], status_code: int = 200) -> None:
		self.body = json.dumps(body, separators=(",", ":")).encode("utf-8")
		self.status_code = status_code
		try:
			from werkzeug.wrappers import Response

			super().__init__(
				response=Response(
					self.body,
					status=status_code,
					content_type="application/json",
				)
			)
		except ModuleNotFoundError:
			super().__init__(self.body.decode("utf-8"))

	def get_response(self, environ: Any | None = None) -> Any:
		try:
			return super().get_response(environ)  # type: ignore[misc]
		except AttributeError:
			return _FallbackResponse(self.body, self.status_code)


class _FallbackResponse:
	def __init__(self, data: bytes, status_code: int) -> None:
		self.data = data
		self.status_code = status_code


_JWKS_CACHE = JwksCache()


def before_request(
	*,
	frappe_module: Any | None = None,
	jwks_cache: JwksCache | None = None,
	route_policy: ServiceRoutePolicy | None = None,
	verify_token: Callable[..., Any] = verify_service_token_with_jwks_cache,
) -> None:
	frappe = frappe_module or _import_frappe()
	request = getattr(frappe.local, "request", None)
	path = getattr(request, "path", "")
	if not path.startswith("/api/v1/service/hrms/"):
		return

	policy = route_policy or ServiceRoutePolicy.default()
	try:
		required_scope = policy.required_scope(getattr(request, "method", ""), path)
		token = extract_bearer_token(frappe.get_request_header("Authorization"))
		principal = verify_token(
			token,
			jwks_cache=jwks_cache or _JWKS_CACHE,
			required_scope=required_scope,
		)
	except UnsupportedServiceRoute as exc:
		raise FrappeServiceAuthError(404, str(exc)) from exc
	except ServiceAuthError as exc:
		_set_authenticate_header(frappe, exc.www_authenticate)
		raise FrappeServiceAuthError(exc.status_code, exc.description) from exc

	frappe.local.service_client = {
		"id": principal.client_id,
		"scopes": principal.scopes,
		"jti": principal.jti,
	}
	if path == "/api/v1/service/hrms/health":
		raise FrappeServiceResponse(
			{
				"service": "dhruvanta-hrms",
				"status": "ok",
				"authenticatedClient": principal.client_id,
			}
		)
	if path == "/api/v1/service/hrms/employees":
		raise FrappeServiceResponse(
			list_employees(frappe, request, request_id=principal.jti)
		)


def _set_authenticate_header(frappe: Any, value: str) -> None:
	headers = getattr(frappe.local, "response_headers", None)
	if headers is None:
		return
	if hasattr(headers, "set"):
		headers.set("WWW-Authenticate", value)
	else:
		headers["WWW-Authenticate"] = value


def _import_frappe() -> Any:
	import frappe

	return frappe
