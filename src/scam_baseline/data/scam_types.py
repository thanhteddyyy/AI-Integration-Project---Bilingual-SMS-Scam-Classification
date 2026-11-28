"""Vietnamese tier-2 scam_type classes (decision 2026-11-27, docs/GIAI_THICH_TANG2_VA_META_FEATURES.md).

Every class sits under one group of definition_of_ham_spam_scam.md (section 3) so results can also be
reported at the coarse level. 3.4 (malware) is an attack method, not a scenario, and has no class.
"""
from __future__ import annotations

# class -> group of the definition
VI_TIER2_GROUPS: dict[str, str] = {
    "banking_finance": "3.1_brand_authority_spoofing",
    "gov_utility_services": "3.1_brand_authority_spoofing",  # state bodies + essential services (power, water, telecom)
    "delivery_logistics": "3.1_brand_authority_spoofing",
    "job_task_scam": "3.2_financial_task",
    "investment": "3.2_financial_task",
    "loan_debt": "3.2_financial_task",  # lending / debt collection not spoofing a real bank
    "prize_lottery": "3.3_prize_lottery",
    "social_impersonation": "extension_person_impersonation",
    "other_scam": "extension_other",
}
VI_TIER2_CLASSES: list[str] = list(VI_TIER2_GROUPS)

# old label (review files keep the old names) -> tier-2 class
#   telecom_account: 9 messages, same script as power/water cut-off threats (merged 2026-11-27)
#   government_services: renamed 2026-11-27 so the name shows it also covers essential services
# Vietnamese only: English data keeps its own scam_type names (adapters.py) until English tier 2 exists.
VI_SCAM_TYPE_MERGE: dict[str, str] = {
    "telecom_account": "gov_utility_services",
    "government_services": "gov_utility_services",
}


def merge_vi_scam_type(value: str) -> str:
    return VI_SCAM_TYPE_MERGE.get(value, value)
