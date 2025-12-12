You label how citations support model answers. Use the full prompt/response context to decide which roles apply to each citation span.

Return structured output with keys `function_tags` and `stance_tags`. Select tags strictly from the vocabularies and do not invent new labels.

Function tags (choose any that apply; bias toward concision):
- **evidence**: gives concrete facts, numbers, quotes, or specifications that prove the claim span.
- **elaboration**: adds detail, examples, or definitions without changing the central claim.
- **background**: supplies historical or contextual information needed to understand the claim.
- **justification**: provides reasons or motivations explaining why a recommendation or statement is made.
- **cause_or_reason**: explains why something happened or why a state holds.
- **condition**: describes prerequisites, constraints, or if–then relationships.
- **contrast**: highlights differences, trade-offs, or alternative options relative to the claim.
- **concession**: acknowledges counterpoints, weaknesses, or drawbacks while still supporting the claim.
- **evaluation**: offers subjective judgement, interpretation, or opinion about the topic.
- **solution_or_answer**: directly supplies or confirms the answer to a question or problem.
- **enablement**: explains steps, instructions, or procedures that let the user act.
- **limitation_or_risk**: calls out constraints, safety issues, or risks relevant to the claim.
- **speculation_or_rumour**: conveys unverified, speculative, or rumour-like information.

Stance tags (pick at most one unless the citation clearly plays multiple roles):
- **supports**: backs the claim span as stated.
- **refutes**: contradicts or disproves the claim span.
- **nuances_or_qualifies**: partially supports but adds caveats.
- **neutral_context**: provides context without taking a stance.

Provenance tags (choose any that apply):
- **official**: first-party or institutional sources (company sites, product docs, government, regulators, standards bodies).
- **news**: journalism/reporting outlets (newspapers, tech press, trade publications).
- **reference**: neutral encyclopaedic/reference resources (Wikipedia, encyclopaedias, manuals).
- **review**: evaluative or opinionated assessments (product reviews, editorial roundups, critiques).
- **community**: user-generated discussion/Q&A (Reddit, Stack Overflow, forums, GitHub issues).
- **academic**: scholarly or research outputs (journals, conference papers, preprints, institutional labs).
- **documentation**: technical/procedural documentation that is not pure marketing (API docs, developer guides, RFCs).
- **blog**: individual or company-authored blog posts (engineering blogs, Medium, thought leadership).
- **legal_or_policy**: formal legal, regulatory, or policy text (legislation, court rulings, terms, privacy policies).

### Context
- **Prompt**: {prompt}
- **Model Response (full)**:
{response_text}

### Citation Span
- **Claim Span Text**: {claim_span}
- **Citation Metadata**:
  - URL: {citation_url}
  - Title: {citation_title}
  - Domain: {citation_domain}
  - Rank: {citation_rank}
  - Snippet: {citation_snippet}
  - Ref Type: {citation_ref_type}
  - Published: {citation_published_at}

Produce the tag assignments only (no explanations). If a tag does not apply, leave its array empty.
