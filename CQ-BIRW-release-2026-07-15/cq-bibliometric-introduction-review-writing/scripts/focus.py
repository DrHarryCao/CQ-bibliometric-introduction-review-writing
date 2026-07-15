#!/usr/bin/env python3
"""Domain-neutral, deterministic screening driven by an approved task plan."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re
from typing import Any


FOCUS_CLASSES = ("core", "theory-supplement", "needs-review", "excluded")


def focus_plan_template(search_plan: dict[str, Any]) -> dict[str, Any]:
    """Return a host-fillable plan without inventing a domain vocabulary."""
    queries = search_plan.get("queries") or []
    direct = [str(q.get("id")) for q in queries if q.get("id") and q.get("family") in {"core", "direct"}]
    theory = [str(q.get("id")) for q in queries if q.get("id") and q.get("family") in {"extended", "frontier", "theory"}]
    return {
        "schema_version": 1,
        "status": "draft-not-approved",
        "approved": False,
        "topic_label": search_plan.get("title_or_idea") or search_plan.get("title_en") or search_plan.get("title_zh") or "",
        "core_groups": [
            {"id": "G01", "label": "当前研究主题的必要概念组（由宿主补全）", "terms": [], "required": True},
        ],
        "minimum_core_groups": 1,
        "adjacent_terms": [],
        "mechanism_terms": [],
        "exclusion_terms": [],
        "direct_query_ids": direct,
        "theory_query_ids": theory,
        "match_fields": ["title", "abstract", "keywords"],
        "unmatched_action": "needs-review",
        "low_confidence_policy": "needs-review",
        "notes": "宿主须依据当前任务补全中英文概念；脚本只执行已批准规则，不含领域默认词表。",
    }


def validate_focus_plan(plan: dict[str, Any]) -> dict[str, Any]:
    errors, warnings = [], []
    if not plan.get("approved") or plan.get("status") not in {"approved", "validated"}:
        errors.append("聚焦计划尚未获用户确认")
    groups = plan.get("core_groups") or []
    usable = [g for g in groups if g.get("id") and [x for x in g.get("terms") or [] if str(x).strip()]]
    if not usable: errors.append("至少需要一个含中英文术语的核心概念组")
    required = [g for g in usable if g.get("required")]
    minimum = int(plan.get("minimum_core_groups") or 1)
    if minimum < 1 or minimum > len(usable): errors.append("minimum_core_groups 超出可用概念组范围")
    if not required: warnings.append("没有 required 核心组；将按 minimum_core_groups 判断")
    if plan.get("unmatched_action", "needs-review") not in {"needs-review", "excluded"}:
        errors.append("unmatched_action 只能是 needs-review 或 excluded")
    if plan.get("unmatched_action") == "excluded":
        warnings.append("未命中记录会被排除；必须在计划说明中给出这一决定的理由")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "usable_core_groups": len(usable), "required_core_groups": len(required)}


def _field_texts(record: dict[str, Any], fields: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for field in fields:
        value = record.get(field, "")
        if isinstance(value, list):
            value = " ".join(str(x.get("name") if isinstance(x, dict) else x) for x in value)
        values[field] = re.sub(r"\s+", " ", str(value or "")).casefold()
    return values


def _term_hits(field_texts: dict[str, str], terms: list[str]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for raw in terms:
        term = str(raw).strip()
        if not term: continue
        needle = term.casefold()
        for field, text in field_texts.items():
            if needle in text:
                hits.append({"term": term, "field": field})
    return hits


def classify_record(record: dict[str, Any], plan: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    fields = list(plan.get("match_fields") or ["title", "abstract", "keywords"])
    texts = _field_texts(record, fields)
    query_ids = set(str(x) for x in record.get("query_ids") or [])
    exclusion_hits = _term_hits(texts, list(plan.get("exclusion_terms") or []))
    group_hits: dict[str, list[dict[str, str]]] = {}
    groups = plan.get("core_groups") or []
    for group in groups:
        group_hits[str(group.get("id") or "")] = _term_hits(texts, list(group.get("terms") or []))
    hit_groups = {gid for gid, hits in group_hits.items() if hits}
    required_groups = {str(g.get("id")) for g in groups if g.get("required")}
    minimum = int(plan.get("minimum_core_groups") or 1)
    adjacent_hits = _term_hits(texts, list(plan.get("adjacent_terms") or []))
    mechanism_hits = _term_hits(texts, list(plan.get("mechanism_terms") or []))
    direct_queries = query_ids & set(str(x) for x in plan.get("direct_query_ids") or [])
    theory_queries = query_ids & set(str(x) for x in plan.get("theory_query_ids") or [])
    reasons: list[str] = []
    if exclusion_hits:
        classification = "excluded"
        reasons.append("命中明确排除概念")
    elif required_groups and required_groups.issubset(hit_groups) and len(hit_groups) >= minimum:
        classification = "core"; reasons.append("满足全部必要概念组")
    elif not required_groups and len(hit_groups) >= minimum:
        classification = "core"; reasons.append(f"命中至少 {minimum} 个核心概念组")
    elif adjacent_hits and (mechanism_hits or theory_queries):
        classification = "theory-supplement"; reasons.append("相邻对象与机制/理论查询共同命中")
    elif direct_queries and hit_groups:
        classification = "needs-review"; reasons.append("直接查询命中但必要概念不完整")
    elif not any(texts.values()):
        classification = "needs-review"; reasons.append("题名、摘要和关键词不足")
    else:
        classification = str(plan.get("unmatched_action") or "needs-review")
        reasons.append("未满足核心或理论补充规则")
    confidence = "high" if classification in {"core", "excluded"} and (exclusion_hits or required_groups.issubset(hit_groups)) else "medium" if classification == "theory-supplement" else "low"
    detail = {
        "plan_schema_version": plan.get("schema_version", 1), "classification": classification,
        "confidence": confidence, "reasons": reasons, "matched_core_groups": sorted(hit_groups),
        "core_group_hits": group_hits, "adjacent_hits": adjacent_hits, "mechanism_hits": mechanism_hits,
        "exclusion_hits": exclusion_hits, "query_ids": sorted(query_ids),
        "direct_query_hits": sorted(direct_queries), "theory_query_hits": sorted(theory_queries),
    }
    return classification, detail


def focus_records(records: list[dict[str, Any]], plan: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    validation = validate_focus_plan(plan)
    if not validation["valid"]:
        raise ValueError("无效聚焦计划：" + "；".join(validation["errors"]))
    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in FOCUS_CLASSES}
    reasons = Counter()
    for raw in records:
        record = deepcopy(raw)
        classification, detail = classify_record(record, plan)
        record["focus_screening"] = detail
        status_map = {"core": "included_core", "theory-supplement": "supplementary_theory", "needs-review": "needs_review", "excluded": "excluded_focus"}
        record["inclusion"] = {"status": status_map[classification], "reasons": detail["reasons"]}
        buckets[classification].append(record)
        reasons[detail["reasons"][0]] += 1
    report = {
        "focus_schema_version": 1, "topic_label": plan.get("topic_label", ""), "input_records": len(records),
        "core_records": len(buckets["core"]), "theory_pool_records": len(buckets["theory-supplement"]),
        "needs_review_records": len(buckets["needs-review"]), "excluded_records": len(buckets["excluded"]),
        "reason_counts": dict(reasons), "domain_hardcoding": False, "plan_validation": validation,
    }
    return buckets["core"], buckets["theory-supplement"], buckets["needs-review"], buckets["excluded"], report
