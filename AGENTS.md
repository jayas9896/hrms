# Dhruvanta HRMS Agent Notes

This repository is Dhruvanta HRMS, based on Frappe HR.

## Governance Rules

- Keep Dhruvanta Systems as the primary product brand. Frappe HR may appear only as "Powered by Frappe HR" where compliance or attribution is needed.
- Do not claim Dhruvanta service-auth endpoints are live until source code wires the verifier and route handlers.
- Commit only explicit files. Do not use `git add -A`.
- Use the governance repository's atomic commit script for governance-repo updates:
  `/home/jayas/dhruvanta-platform-governance/scripts/atomic-commit.sh`.
- Backend public origin is `https://api.dhruvantasystems.net/hrms/api`.
- Customer/admin/support frontend origins are:
  - `https://hrms.dhruvantasystems.com`
  - `https://admin.hrms.dhruvantasystems.com`
  - `https://support.hrms.dhruvantasystems.com`

## Backend Contract Status

Current runtime is Frappe/ERPNext session auth plus upstream whitelisted methods.
The Dhruvanta service-to-service API is contract-locked but not wired yet.
Run this verifier after touching backend contract docs:

```sh
python3 scripts/verify-service-auth-contract.py
```

