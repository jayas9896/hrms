"""Dhruvanta HRMS service-client JWT verification helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any
from urllib.request import Request, urlopen

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


class JwksCache:
	"""Discovery-backed JWKS cache for the future Frappe request hook."""

	def __init__(
		self,
		issuer_base_url: str = EXPECTED_ISSUER,
		*,
		fetch_json: Any | None = None,
		ttl_seconds: int = 300,
	) -> None:
		self.issuer_base_url = issuer_base_url.rstrip("/")
		self.fetch_json = fetch_json or _fetch_json
		self.ttl_seconds = max(1, ttl_seconds)
		self._jwks_uri: str | None = None
		self._jwks: dict[str, Any] | None = None
		self._expires_at = 0.0

	def get_jwks(self, *, force_refresh: bool = False) -> dict[str, Any]:
		now = time.time()
		if not force_refresh and self._jwks is not None and now < self._expires_at:
			return self._jwks
		jwks_uri = self._jwks_uri or self._discover_jwks_uri()
		jwks = self.fetch_json(jwks_uri)
		if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
			raise ServiceAuthError(503, "temporarily_unavailable", "jwks response invalid")
		self._jwks = jwks
		self._expires_at = now + self.ttl_seconds
		return jwks

	def _discover_jwks_uri(self) -> str:
		discovery_url = f"{self.issuer_base_url}/.well-known/openid-configuration"
		discovery = self.fetch_json(discovery_url)
		jwks_uri = discovery.get("jwks_uri") if isinstance(discovery, dict) else None
		if not isinstance(jwks_uri, str) or not jwks_uri:
			raise ServiceAuthError(503, "temporarily_unavailable", "issuer discovery missing jwks_uri")
		self._jwks_uri = jwks_uri
		return jwks_uri


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


def verify_service_token_with_jwks_cache(
	token: str,
	*,
	jwks_cache: JwksCache,
	required_scope: str | None = None,
	issuer: str = EXPECTED_ISSUER,
	audience: str = EXPECTED_AUDIENCE,
) -> ServicePrincipal:
	try:
		return verify_service_token(
			token,
			jwks=jwks_cache.get_jwks(),
			required_scope=required_scope,
			issuer=issuer,
			audience=audience,
		)
	except ServiceAuthError as exc:
		if exc.status_code != 503 or exc.description != "jwks key unavailable":
			raise
		return verify_service_token(
			token,
			jwks=jwks_cache.get_jwks(force_refresh=True),
			required_scope=required_scope,
			issuer=issuer,
			audience=audience,
		)


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


def _fetch_json(url: str) -> dict[str, Any]:
	request = Request(
		url,
		headers={
			"Accept": "application/json, application/jwk-set+json",
			"User-Agent": "Dhruvanta-HRMS-ServiceAuth/1.0",
		},
	)
	try:
		with urlopen(request, timeout=5) as response:
			payload = response.read().decode("utf-8")
	except OSError as exc:
		raise ServiceAuthError(503, "temporarily_unavailable", "jwks fetch failed") from exc
	data = json.loads(payload)
	if not isinstance(data, dict):
		raise ServiceAuthError(503, "temporarily_unavailable", "json response invalid")
	return data
