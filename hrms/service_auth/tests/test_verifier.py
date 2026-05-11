"""Tests for Dhruvanta HRMS service-client JWT verification."""

from __future__ import annotations

import time
import unittest
from uuid import uuid4
import importlib.util
from pathlib import Path
import sys

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

VERIFIER_PATH = Path(__file__).resolve().parents[1] / "verifier.py"
SPEC = importlib.util.spec_from_file_location("hrms_service_auth_verifier", VERIFIER_PATH)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = verifier
SPEC.loader.exec_module(verifier)

EXPECTED_AUDIENCE = verifier.EXPECTED_AUDIENCE
EXPECTED_ISSUER = verifier.EXPECTED_ISSUER
ServiceAuthError = verifier.ServiceAuthError
extract_bearer_token = verifier.extract_bearer_token
verify_service_token = verifier.verify_service_token


class ServiceAuthVerifierTests(unittest.TestCase):
	def setUp(self) -> None:
		self.private_key = ec.generate_private_key(ec.SECP256R1())
		public_jwk = jwt.algorithms.ECAlgorithm.to_jwk(self.private_key.public_key(), as_dict=True)
		public_jwk.update({"kid": "hrms-test-key", "use": "sig", "alg": "ES256"})
		self.jwks = {"keys": [public_jwk]}

	def token(self, **overrides: object) -> str:
		now = int(time.time())
		claims: dict[str, object] = {
			"iss": EXPECTED_ISSUER,
			"aud": EXPECTED_AUDIENCE,
			"sub": "dhruvanta-one",
			"scope": "hrms:employee.read hrms:attendance.write",
			"jti": str(uuid4()),
			"iat": now,
			"exp": now + 300,
		}
		claims.update(overrides)
		return jwt.encode(claims, self.private_key, algorithm="ES256", headers={"kid": "hrms-test-key"})

	def test_extracts_bearer_token_fail_closed(self) -> None:
		self.assertEqual(extract_bearer_token("Bearer abc.def"), "abc.def")
		for header in (None, "", "Basic abc", "Bearer"):
			with self.assertRaises(ServiceAuthError) as raised:
				extract_bearer_token(header)
			self.assertEqual(raised.exception.status_code, 401)

	def test_accepts_es256_token_with_expected_issuer_audience_and_scope(self) -> None:
		principal = verify_service_token(
			self.token(),
			jwks=self.jwks,
			required_scope="hrms:employee.read",
		)

		self.assertEqual(principal.client_id, "dhruvanta-one")
		self.assertIn("hrms:employee.read", principal.scopes)
		self.assertRegex(principal.jti, r"^[0-9a-f-]{36}$")

	def test_rejects_wrong_audience_and_missing_scope(self) -> None:
		with self.assertRaises(ServiceAuthError) as wrong_audience:
			verify_service_token(self.token(aud="erp"), jwks=self.jwks)
		self.assertEqual(wrong_audience.exception.status_code, 403)
		self.assertEqual(wrong_audience.exception.error, "invalid_token")

		with self.assertRaises(ServiceAuthError) as missing_scope:
			verify_service_token(
				self.token(scope="hrms:attendance.write"),
				jwks=self.jwks,
				required_scope="hrms:employee.read",
			)
		self.assertEqual(missing_scope.exception.status_code, 403)
		self.assertEqual(missing_scope.exception.error, "insufficient_scope")

	def test_rejects_unknown_kid_and_expired_token(self) -> None:
		with self.assertRaises(ServiceAuthError) as unknown_key:
			verify_service_token(self.token(), jwks={"keys": []})
		self.assertEqual(unknown_key.exception.status_code, 503)

		with self.assertRaises(ServiceAuthError) as expired:
			verify_service_token(self.token(exp=int(time.time()) - 1), jwks=self.jwks)
		self.assertEqual(expired.exception.status_code, 401)


if __name__ == "__main__":
	unittest.main()
