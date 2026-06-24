package main

import rego.v1

test_denies_missing_required_control if {
	deny["required control AIGOV-003 is not satisfied or waived"] with input as {"controls": {}}
		with data.required_controls as ["AIGOV-003"]
}

test_allows_satisfied_with_evidence if {
	count(deny) == 0 with input as {"controls": {"AIGOV-003": {"status": "satisfied", "evidence": "KMS"}}}
		with data.required_controls as ["AIGOV-003"]
}

test_denies_satisfied_without_evidence if {
	deny["control AIGOV-003 is marked satisfied but has no evidence"] with input as {"controls": {"AIGOV-003": {"status": "satisfied"}}}
		with data.required_controls as ["AIGOV-003"]
}

test_allows_waived_control if {
	count(deny) == 0 with input as {"controls": {"AIGOV-003": {"status": "not_applicable"}}}
		with data.required_controls as ["AIGOV-003"]
}
