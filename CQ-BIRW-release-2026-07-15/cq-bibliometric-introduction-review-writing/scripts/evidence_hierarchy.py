#!/usr/bin/env python3
"""Claim-fit evidence-source normalization and tiering."""
from __future__ import annotations

import re
from typing import Any


TYPE_ALIASES = {
    "article": "journal-article", "journal article": "journal-article", "journal-article": "journal-article", "jour": "journal-article",
    "review": "review", "systematic review": "systematic-review", "meta-analysis": "meta-analysis",
    "dissertation": "thesis", "thesis": "thesis", "phd thesis": "thesis", "master thesis": "thesis",
    "book-chapter": "book-chapter", "book chapter": "book-chapter", "chapter": "book-chapter", "book": "book",
    "proceedings-article": "conference-paper", "conference paper": "conference-paper", "conference-paper": "conference-paper", "conference": "conference-paper",
    "preprint": "preprint", "posted-content": "preprint", "working paper": "working-paper",
    "report": "report", "editorial": "editorial", "paratext": "paratext", "other": "other",
}


def normalize_publication_type(record: dict[str, Any]) -> str:
    raw = str(record.get("publication_type_normalized") or record.get("type") or "other").strip().casefold().replace("_", "-")
    title = str(record.get("title") or "").casefold()
    normalized = TYPE_ALIASES.get(raw, raw if raw in set(TYPE_ALIASES.values()) else "other")
    if re.search(r"\bmeta[- ]analysis\b", title): normalized = "meta-analysis"
    elif re.search(r"\bsystematic review\b", title): normalized = "systematic-review"
    return normalized


def classify_evidence_source(record: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or {}
    ptype = normalize_publication_type(record)
    raw = record.get("raw") or {}
    title = str(record.get("title") or "")
    retracted = bool(record.get("retracted") or raw.get("is_retracted") or re.search(r"\bretracted\b", title, re.I))
    aggregate_record = bool(re.search(r"\b(?:full issue|entire issue|table of contents)\b|(?:整期|全期|目录)", title, re.I))
    conference_primary = bool(record.get("conference_primary") or policy.get("conference_primary"))
    full_paper = bool(record.get("full_paper") or (record.get("fulltext") or {}).get("local_path") or raw.get("is_full_paper"))
    peer_review = "unknown"
    roles: list[str] = []
    if retracted or aggregate_record or ptype in {"editorial", "paratext"} or not title.strip():
        tier, reason = "D", "撤稿、编辑性集合记录或身份信息不足，不能支持正式正向论断"
        peer_review = "not-eligible"
    elif ptype in {"journal-article", "review", "systematic-review", "meta-analysis"}:
        tier, reason, peer_review = "A", "同行评审期刊文献", "peer-reviewed-assumed"
        roles = ["empirical"] if ptype == "journal-article" else ["synthesis"]
    elif ptype in {"book", "book-chapter"}:
        # Books are first-choice for theory/conceptual history, but not an
        # automatic substitute for focal empirical evidence.
        tier, reason, peer_review, roles = "A", "学术专著/章节：仅优先用于理论、概念史和历史发展", "scholarly-source", ["theory", "concept-history"]
    elif ptype == "conference-paper" and conference_primary and full_paper:
        tier, reason, peer_review, roles = "A", "主要会议型学科的正式同行评审全文", "peer-reviewed-explicit", ["empirical", "emerging"]
    elif ptype in {"thesis", "conference-paper", "report"}:
        tier, reason = "B", "学位论文、一般正式会议全文或方法完整的机构报告"
        peer_review = "examined" if ptype == "thesis" else "review-status-limited"
        roles = ["supplement", "unique-context", "counterevidence"]
    elif ptype in {"preprint", "working-paper"}:
        tier, reason, peer_review, roles = "C", "预印本、工作论文或早期研究", "not-confirmed", ["exploratory", "emerging", "counterevidence"]
    else:
        tier, reason, peer_review, roles = "D", "文献类型或正式出版状态无法确认", "unknown", []
    return {"publication_type_normalized": ptype, "peer_review_status": peer_review, "evidence_tier": tier, "tier_reason": reason, "claim_use_roles": roles}


def enrich_evidence_source(record: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    enriched = dict(record)
    enriched.update(classify_evidence_source(record, policy))
    return enriched


def tier_rank(record: dict[str, Any]) -> int:
    return {"A": 0, "B": 1, "C": 2, "D": 3}.get(str(record.get("evidence_tier") or "D"), 3)
