#!/usr/bin/env python3
"""Task-scoped expansion of content evidence without changing the analytic corpus.

The host writes a domain-specific plan.  This module only executes the plan,
keeps provenance, and compiles host-approved records.  It contains no domain
vocabulary and never promotes adjacent evidence to focal/direct evidence.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common import deduplicate, load_jsonl, read_json, utc_stamp, write_json, write_jsonl
from evidence_hierarchy import enrich_evidence_source
from sources import CachedClient, OpenAlexClient


def search_expansion(root: Path, refresh: bool = False) -> dict[str, Any]:
    plan_path = root / "00_plan/writing_evidence_expansion_plan.json"
    plan = read_json(plan_path, {})
    queries = plan.get("queries") or []
    if not queries:
        raise RuntimeError("writing_evidence_expansion_plan.json 缺少 queries。")
    client = OpenAlexClient(CachedClient(root / "01_sources/cache"))
    rows: list[dict[str, Any]] = []
    query_report = []
    for index, query in enumerate(queries, 1):
        qid = str(query.get("id") or f"WE{index:02d}")
        found, report = client.search(
            str(query.get("query") or ""), qid,
            filters=str(query.get("filter") or ""),
            limit=int(query.get("limit") or 100), refresh=refresh,
        )
        rows.extend(found); query_report.append(report)
    # Reuse already identified theory supplements as candidates, while keeping
    # their original query provenance.
    rows.extend(load_jsonl(root / "02_corpus/theory_supplement_pool.jsonl"))
    unique, merges = deduplicate(rows)
    core_ids = {x.get("record_id") for x in load_jsonl(root / "02_corpus/corpus.jsonl")}
    candidates = [enrich_evidence_source(x) for x in unique if x.get("record_id") not in core_ids]
    write_jsonl(root / "02_corpus/writing_evidence_expansion_candidates.jsonl", candidates)
    report = {
        "status": "host-selection-required", "queries": query_report,
        "raw_records": len(rows), "unique_candidates": len(candidates),
        "deduplication_events": len(merges), "generated_at": utc_stamp(),
        "rule": "Candidates are not writing evidence until the host verifies relevance and assigns a use role.",
    }
    write_json(root / "07_logs/writing_evidence_expansion_search.json", report)
    return report


def compile_selection(root: Path) -> dict[str, Any]:
    selection_path = root / "05_evidence/writing_evidence_selection.jsonl"
    decisions = load_jsonl(selection_path)
    if not decisions:
        raise RuntimeError("缺少 writing_evidence_selection.jsonl 宿主复核结果。")
    candidates = {x.get("record_id"): x for x in load_jsonl(root / "02_corpus/writing_evidence_expansion_candidates.jsonl")}
    selected, rejected, missing = [], 0, []
    for decision in decisions:
        rid = decision.get("record_id")
        record = candidates.get(rid)
        if not record:
            missing.append(rid); continue
        if decision.get("decision") != "include":
            rejected += 1; continue
        item = dict(record)
        item["writing_evidence_role"] = decision.get("role") or "adjacent-mechanism"
        item["writing_evidence_topics"] = decision.get("topics") or []
        item["writing_evidence_reason"] = decision.get("reason") or ""
        item["directness"] = decision.get("directness") or "adjacent"
        selected.append(item)
    write_jsonl(root / "02_corpus/supplemental_writing_evidence.jsonl", selected)
    report = {
        "status": "compiled", "selected": len(selected), "rejected": rejected,
        "missing_candidate_ids": missing,
        "direct": sum(x.get("directness") == "direct" for x in selected),
        "adjacent": sum(x.get("directness") != "direct" for x in selected),
        "rule": "Supplemental evidence expands mechanisms and outcome chains; it does not enter NMF or replace focal LARP evidence.",
    }
    write_json(root / "07_logs/writing_evidence_expansion_compile.json", report)
    return report
