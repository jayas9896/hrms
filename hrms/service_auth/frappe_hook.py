"""Frappe before_request hook for HRMS service-auth paths."""

from __future__ import annotations

from typing import Any, Callable

from hrms.service_auth.route_policy import ServiceRoutePolicy, UnsupportedServiceRoute
from hrms.service_auth.verifier import (
	JwksCache,
	ServiceAuthError,
	extract_bearer_token,
	verify_service_token_with_jwks_cache,
)


class FrappeServiceAuthError(Exception):
	def __init__(self, status_code: int, message: str) -> None:
		super().__init__(message)
		self.http_status_code = status_code


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
