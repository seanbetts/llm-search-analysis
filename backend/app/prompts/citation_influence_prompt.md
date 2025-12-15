You explain, in one concise sentence (maximum 30 words), how a cited source influenced the model's specific claim.

Consider:
- Claim span text, citation snippet, and metadata.
- Assigned function, stance, and provenance tags.
- Prompt and full model response for context.

Guidelines:
- Describe the relationship between the claim and the source (e.g., what evidence/context it provides, what limitation it highlights).
- Refer to the source generically (e.g., "news report", "official documentation") instead of repeating the URL.
- Do not restate the tags explicitly; use them as reasoning signals.
- Output a single sentence only.

### Context
- **Prompt**: {prompt}
- **Model Response (full)**:
{response_text}

### Claim
- **Claim Span Text**: {claim_span}

### Citation Metadata
- URL: {citation_url}
- Title: {citation_title}
- Domain: {citation_domain}
- Rank: {citation_rank}
- Snippet: {citation_snippet}
- Ref Type: {citation_ref_type}
- Published: {citation_published_at}

### Assigned Tags
- Function tags: {function_tags}
- Stance tags: {stance_tags}
- Provenance tags: {provenance_tags}

Return only the single-sentence description.
