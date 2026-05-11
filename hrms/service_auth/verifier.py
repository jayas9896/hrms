"""Dhruvanta HRMS service-client JWT verification helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

import jwt


EXPECTED_ISSUER = "https://api.dhruvantasystems.net/service-control-plane"
EXPECTED_AUDIENCE = "hrms"


@dataclass(frozen=True)
class ServicePrincipal:
	client_id: str
	scopes: tuple[str, ...]
	jti: str | None


class ServiceAuthError(Exception):
	def __init__(self, status_code: int, error: str, description: str) -> None:
		super().__init__(description)
		self.status_code = status_code
		self.error = error
		self.description = description

	@property
	def www_authenticate(self) -> str:
		return f'Bearer error="{self.error}", error_description="{self.description}"'


def extract_bearer_token(authorization_header: str | None) -> str:
	if authorization_header is None:
		raise ServiceAuthError(401, "invalid_request", "missing bearer token")
	parts = authorization_header.strip().split()
	if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
		raise ServiceAuthError(401, "invalid_request", "malformed bearer token")
	return parts[1]


def verify_service_token(
	token: str,
	*,
	jwks: dict[str, Any],
	required_scope: str | None = None,
	issuer: str = EXPECTED_ISSUER,
	audience: str = EXPECTED_AUDIENCE,
) -> ServicePrincipal:
	key = _key_for_token(token, jwks)
	try:
		claims = jwt.decode(
			token,
			key=key,
			algorithms=["ES256"],
			issuer=issuer,
			audience=audience,
			options={"require": ["exp", "iss", "aud"]},
		)
	except jwt.ExpiredSignatureError as exc:
		raise ServiceAuthError(401, "invalid_token", "token expired") from exc
	except jwt.InvalidAudienceError as exc:
		raise ServiceAuthError(403, "invalid_token", "wrong audience") from exc
	except jwt.InvalidIssuerError as exc:
		raise ServiceAuthError(401, "invalid_token", "wrong issuer") from exc
	except jwt.InvalidTokenError as exc:
		raise ServiceAuthError(401, "invalid_token", "token verification failed") from exc

	scopes = _scopes(claims)
	if required_scope and required_scope not in scopes:
		raise ServiceAuthError(403, "insufficient_scope", "required scope missing")

	client_id = str(claims.get("client_id") or claims.get("azp") or claims.get("sub") or "")
	if not client_id:
		raise ServiceAuthError(401, "invalid_token", "client id missing")

	jti = claims.get("jti")
	return ServicePrincipal(client_id=client_id, scopes=tuple(sorted(scopes)), jti=str(jti) if jti else None)


def _key_for_token(token: str, jwks: dict[str, Any]) -> Any:
	try:
		header = jwt.get_unverified_header(token)
	except jwt.InvalidTokenError as exc:
		raise ServiceAuthError(401, "invalid_token", "token header invalid") from exc
	kid = header.get("kid")
	if not kid:
		raise ServiceAuthError(401, "invalid_token", "token kid missing")

	for key in jwks.get("keys") or []:
		if key.get("kid") == kid:
			return jwt.algorithms.ECAlgorithm.from_jwk(json.dumps(key))
	raise ServiceAuthError(503, "temporarily_unavailable", "jwks key unavailable")


def _scopes(claims: dict[str, Any]) -> set[str]:
	scope = claims.get("scope")
	if isinstance(scope, str):
		return {item for item in scope.split() if item}
	if isinstance(scope, list):
		return {str(item) for item in scope if str(item)}
	scp = claims.get("scp")
	if isinstance(scp, list):
		return {str(item) for item in scp if str(item)}
	return set()
