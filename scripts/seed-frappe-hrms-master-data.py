#!/usr/bin/env python3
"""Seed minimal HRMS master data for service-auth write smokes."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any


REQUIRED_DOCS: tuple[dict[str, Any], ...] = (
	{
		"doctype": "Gender",
		"name": "Other",
		"gender": "Other",
	},
	{
		"doctype": "Leave Type",
		"name": "Dhruvanta Unpaid Leave",
		"leave_type_name": "Dhruvanta Unpaid Leave",
		"is_lwp": 1,
		"include_holiday": 1,
	},
	{
		"doctype": "Shift Type",
		"name": "General",
		"shift_type_name": "General",
		"start_time": "09:00:00",
		"end_time": "18:00:00",
		"enable_auto_attendance": 0,
	},
)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--bench", default="/home/jayas/frappe-bench", help="Frappe bench path")
	parser.add_argument("--site", default="erp.localhost", help="Frappe site name")
	parser.add_argument("--dry-run", action="store_true", help="Print rows without connecting to Frappe")
	return parser.parse_args()


def bootstrap_frappe(bench: Path) -> None:
	for app in ("frappe", "erpnext", "hrms"):
		app_path = bench / "apps" / app
		if app_path.exists():
			sys.path.insert(0, str(app_path))


def ensure_bench_log_dir(bench: Path) -> None:
	(bench / "logs").mkdir(parents=True, exist_ok=True)
	(bench.parent / "logs").mkdir(parents=True, exist_ok=True)


def ensure_doc(frappe: Any, payload: dict[str, Any]) -> str:
	doctype = str(payload["doctype"])
	name = str(payload["name"])
	if frappe.db.exists(doctype, name):
		return "exists"
	doc = frappe.get_doc(dict(payload))
	doc.flags.ignore_mandatory = True
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True, ignore_mandatory=True)
	return "created"


def main() -> int:
	args = parse_args()
	bench = Path(args.bench).expanduser().resolve()
	if args.dry_run:
		for payload in REQUIRED_DOCS:
			print(f"{payload['doctype']}: {payload['name']}")
		return 0

	bootstrap_frappe(bench)
	ensure_bench_log_dir(bench)
	import frappe  # noqa: PLC0415

	os.chdir(bench / "sites")
	frappe.init(site=args.site, sites_path=str(bench / "sites"))
	frappe.connect()
	try:
		for payload in REQUIRED_DOCS:
			status = ensure_doc(frappe, payload)
			print(f"{status}: {payload['doctype']} {payload['name']}")
		frappe.db.commit()
	finally:
		frappe.destroy()
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
