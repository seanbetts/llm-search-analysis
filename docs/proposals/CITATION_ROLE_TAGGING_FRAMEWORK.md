# Citation Role Tagging Framework

> TL;DR  
> - Tracks exactly which spans in a model response each citation supports.  
> - Classifies the rhetorical role, stance, and provenance of every source.  
> - Enables quantitative audits of grounding quality, coverage, and bias.

This document describes the tag system we use to analyse how external citations shape large-language-model responses. The framework draws on [Rhetorical Structure Theory](https://en.wikipedia.org/wiki/Rhetorical_structure_theory) (Mann & Thompson, 1988) and argumentation research to create a systematic, multi-label tagging approach that works across any type of prompt, answer or citation.

## 1. What We Are Trying to Achieve

When a model produces an answer that includes citations, those sources are not all doing the same job. Some provide hard evidence, some add context, some explain mechanisms, some highlight limitations, and some offer opinion.

Our aim is to:

- Identify exactly which part of the answer each citation supports.
- Classify what rhetorical function the citation serves.
- Understand how models choose sources and how those sources influence the content.
- Enable large-scale quantitative analysis of model grounding behaviour.

This creates a structured view of how external information shapes model reasoning.

## 2. How the System Works

For every grounded citation, we capture three components:

1. **Claim span** – the exact substring in the model’s output that the citation supports.
2. **Source metadata** – URL, domain, rank, publication date, and provenance.
3. **Tags** – descriptive labels specifying the role the citation plays.

We use three tagging categories:

- `function_tags` – rhetorical roles (RST-derived)
- `stance_tags` – how the source stands relative to the claim
- `provenance_tags` – taken directly from `ref_type`

## 3. JSON Schema for Tags

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/citation-tags.schema.json",
  "title": "CitationTags",
  "description": "Controlled vocabularies for tagging the rhetorical, evidential and provenance roles of citations.",
  "type": "object",
  "properties": {
    "function_tags": {
      "type": "array",
      "description": "RST-inspired functional roles describing how a source is used to support a specific claim span.",
      "items": {
        "type": "string",
        "enum": [
          "evidence",
          "elaboration",
          "background",
          "justification",
          "cause_or_reason",
          "condition",
          "contrast",
          "concession",
          "evaluation",
          "solution_or_answer",
          "enablement",
          "limitation_or_risk",
          "speculation_or_rumour"
        ]
      },
      "uniqueItems": true
    },
    "stance_tags": {
      "type": "array",
      "description": "Optional stance indicators describing how the source relates to the claim.",
      "items": {
        "type": "string",
        "enum": [
          "supports",
          "refutes",
          "nuances_or_qualifies",
          "neutral_context"
        ]
      },
      "uniqueItems": true
    },
    "provenance_tags": {
      "type": "array",
      "description": "Source provenance tags taken directly from metadata.ref_id.ref_type.",
      "items": {
        "type": "string",
        "enum": [
          "news",
          "reference",
          "community",
          "official",
          "review",
          "other"
        ]
      },
      "uniqueItems": true
    }
  }
}
```

## 4. Tag Definitions

### Function Tags

| Tag | Description |
| --- | --- |
| `evidence` | Provides concrete support for the claim (facts, data, quotes, specifications). |
| `elaboration` | Adds detail, examples, clarification or definition without changing the core claim. |
| `background` | Supplies contextual or historical information needed to understand the claim. |
| `justification` | Gives reasons or motivations that explain why a recommendation or statement is made. |
| `cause_or_reason` | Explains why something happened or why a state holds. |
| `condition` | Specifies prerequisites, constraints, or if–then relationships affecting the claim. |
| `contrast` | Highlights differences, trade-offs or alternatives. |
| `concession` | Acknowledges counterpoints or drawbacks alongside a supported claim. |
| `evaluation` | Provides subjective judgement, interpretation or opinion. |
| `solution_or_answer` | Directly supplies or confirms the answer to a question or the fix to a problem. |
| `enablement` | Supplies instructions or procedural guidance enabling a task. |
| `limitation_or_risk` | Highlights constraints, weaknesses, risks or safety issues relevant to the claim. |
| `speculation_or_rumour` | Contains unverified, speculative or rumour-like information. |

### Stance Tags

| Tag | Description |
| --- | --- |
| `supports` | Evidence directly supports the claim span. |
| `refutes` | Evidence contradicts the claim span. |
| `nuances_or_qualifies` | Evidence partially supports but adds caveats or constraints. |
| `neutral_context` | Provides context without taking a stance. |

### Provenance Tags

| Tag | Description |
| --- | --- |
| `official` | First-party or institutional sources (company sites, product docs, government, regulators, standards bodies). |
| `news` | Journalism and reporting (newspapers, tech press, trade publications). |
| `reference` | Neutral encyclopaedic/reference content (Wikipedia, encyclopaedias, dictionaries, manuals). |
| `review` | Evaluative or opinionated assessments (product reviews, editorial roundups, critique pieces). |
| `community` | User-generated discussion or Q&A (Reddit, Stack Overflow, forums, GitHub issues). |
| `academic` | Scholarly or research outputs (journals, conference proceedings, arXiv/preprints, institutional labs). |
| `documentation` | Technical/procedural documentation that isn’t strictly marketing (API docs, developer guides, RFCs, SDK references). |
| `blog` | Individual or company-authored posts that aren’t formal news/documentation (engineering blogs, Medium, thought leadership). |
| `legal_or_policy` | Formal legal, regulatory, or policy text (legislation, rulings, terms of service, privacy policies). |

## 5. Example

```json
{
  "claim_span": "Steam Frame is launching in early 2026 as a streaming-first standalone VR headset.",
  "url": "https://www.uploadvr.com/valve-steam-frame-official-announcement-features-details/",
  "domain": "uploadvr.com",
  "rank": 3,
  "pub_date": "2025-11-20T14:10:28Z",
  "function_tags": ["evidence", "elaboration"],
  "stance_tags": ["supports"],
  "provenance_tags": ["news"]
}
```

## 6. Output and Benefits

The output is a structured dataset linking text spans to citations and their rhetorical roles. This enables:

- Quantitative grounding analysis across thousands of model responses.
- Understanding domain bias, evidence quality and citation behaviour.
- Measuring how models use sources for evidence, context, justification or opinion.
- Identifying claims lacking evidence or reliant on speculative sources.

This tagging framework forms the foundation for evaluating the interpretability, trustworthiness and reasoning structure of model-generated content.

## 7. Implementation Plan

To integrate this framework into the current stack we focus on web captures (network logs). API-only interactions don’t expose citation spans, so tagging remains disabled there.

### Backend schema + models

- Extend `SourceUsed` with `function_tags`, `stance_tags`, and `provenance_tags` JSON columns (default empty lists). Write an Alembic migration so existing data stays readable.
- Update the core `Citation` dataclass and FastAPI responses to include the three tag arrays. Providers can initially emit empty lists.
- When saving web captures, persist tags directly on each `SourceUsed` row (in addition to current metadata like start/end indices and snippets).

### Service + ingestion workflow

- Implement a tagging module that runs for `data_source == "web"` responses. It receives `(claim_span, citation metadata)` pairs and returns the three tag lists.
- Use an LLM (guided prompt + JSON schema) to classify each citation. The prompt should include the response text, citation span, and tag definitions to ensure structured output.
- Add an offline script to iterate through historical web captures and backfill tags using the same LLM-powered module. This keeps legacy data comparable to future runs.
- Before wiring the tagger into ingestion, sample existing web captures and run the LLM classification script across them. Review outputs, adjust prompts/tag definitions, and track accuracy metrics so we know the tags are trustworthy.
- Run a benchmarking pass with several OpenAI and Google API models: feed representative prompts/citations through each provider, capture latency/cost, and evaluate tagging quality. Use those results to choose the default tagger model (or maintain per-provider prompts if necessary).

### API + frontend exposure

- Surface tags via the `/interactions` APIs so history/interactive tabs can display them. Update the frontend builders and components to render the new fields (e.g., chips beneath each citation).
- Because tags are stored on the backend, downstream analytics (history charts, exports) can filter or aggregate by rhetorical function without extra work.

### Summary

1. Schema update + migration (add JSON columns on `sources_used`).
2. Provider/service contract updates to carry tag arrays.
3. LLM-driven tagging pipeline (web-only) plus a retrofit script and evaluation run on existing records.

## 8. Benchmarking & Model Selection

To pick a production tagger we benchmarked six models (OpenAI GPT‑5.1 / GPT‑5-mini / GPT‑5-nano and Gemini 2.5 Pro / Flash / Flash-Lite) against a fixed dataset of 20 API responses (129 citations). Each run produced:
- Tag quality metrics (coverage of function, stance, provenance tags).
- Influence summaries (single sentence explaining how the source shaped the claim).
- Token usage and estimated cost per citation.

**Findings**
- GPT‑5.1 and Gemini 2.5 Pro delivered the richest tagging (≈1.9 function tags per citation) but cost ~$0.0026–$0.0033 per citation.
- Gemini 2.5 Flash matched tag accuracy while cutting cost to ~$0.00074 per citation.
- Gemini 2.5 Flash-Lite was ultra-cheap (~$0.0002) but occasionally misclassified direct evidence as “background.”
- GPT‑5-mini tagged every citation with solid accuracy (avg 1.58 function tags, consistent provenance) and produced clear influence summaries, at ~$0.00061 per citation.
- GPT‑5-nano was the cheapest (~$0.00016) but often dropped provenance tags and produced simplistic function tags.

**Decision**
- Adopt **GPT‑5-mini** as the default citation tagger. It is ~17.5% cheaper than Gemini 2.5 Flash while maintaining consistent quality across tags and summaries.
- Reserve GPT‑5.1 or Gemini 2.5 Pro for premium audits where maximum tagging richness is required.
- Keep Gemini 2.5 Flash(-Lite) as backup options if we need cost-sensitive alternatives or non-OpenAI providers.

The benchmarking artefacts (CSV/JSON per model) are stored in `data/bench_<model>.{csv,json}` and can be rerun via `scripts/run_citation_tagging_benchmark.py --response-data data/citation_benchmark_responses.json`.
4. API/client changes so tags appear in the UI and data exports.

This staged approach delivers immediate visibility for web analyses while keeping the door open to expand tagging quality over time.
