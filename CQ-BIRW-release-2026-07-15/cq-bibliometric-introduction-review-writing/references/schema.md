# 统一语料模式

权威文件是 UTF-8 `02_corpus/corpus.jsonl`，每行一篇文献。

## 关键字段

- `record_id`：从 DOI、OpenAlex/PMID 或题名-年份-首位作者生成的稳定 ID。
- `ids`：`doi/openalex/pmid/pmcid/s2` 等，不覆盖互异 ID。
- `authors`：结构化作者，允许 `name/orcid/openalex/institutions`。
- `citation_counts`：按来源分别存储，例如 `openalex`、`wos`，禁止把不同口径静默相加。
- `citation_counts_by_year`：OpenAlex 等来源提供的年度被引历史；缺失时保持空对象，不从总被引数推造年度序列。
- `references`：可为 OpenAlex ID、DOI、结构化对象或原始参考文献字符串。
- `oa`：OA 状态、许可、落地页和直达 PDF 地址。
- `fulltext`：本地路径、哈希、提取质量和访问层级。
- `query_ids`：命中哪些查询，用于相关性与覆盖审计。
- `inclusion`：`candidate/included/excluded` 和理由。
- `publication_type_normalized`：规范化出版类型，如 `journal-article/thesis/conference-paper/preprint`。
- `peer_review_status`、`evidence_tier`、`tier_reason`、`claim_use_roles`：写作证据分层与允许用途；不改变计量分析纳入。
- `provenance`：来源与检索时间；`raw` 保存源记录。

## 合并规则

匹配优先级：DOI＋题名/年份一致性 → 稳定数据库 ID → 高相似题名且年份相差不超过一年，并核对首位作者。DOI不是无条件身份键：同一 DOI 若对应明显不同题名，标记 `doi-scope-conflict` 并保留独立记录；中间相似度进入确认队列。期刊整期、专著或会议集 DOI 不得覆盖文章/章节身份。摘要保留信息更完整者，冲突写入日志；关键词、作者、参考文献和来源做稳定去重并集。不得因字段空缺而删除记录。

## 聚焦计划

聚焦规则保存为任务级 `00_plan/focus_plan.json`，分为 `core/theory-supplement/needs-review/excluded`。规则由当前研究问题生成，脚本不得内置或回退到任何领域词表。信息不足或规则冲突默认进入 `needs-review`；只有命中明确排除条件或用户确认的未命中策略才能进入 `excluded`。

## 导入边界

支持 RIS、ENW、NBIB/MEDLINE、BibTeX、WoS tagged text、NET、CSV/TSV、XLSX 和 JSON/JSONL。表格列无法可靠映射时，先输出建议并征求确认，不按位置猜测。
