1. Objective

Build a Python-based classification system that can take any LLM prompt/response pair and attach three independent but related layers of metadata:
	1.	Topics / aboutness
	•	Based on IAB Content Taxonomy 3.1 (or latest) so it’s interoperable with adtech / contextual systems.
	2.	Commercial industries
	•	A compact, human-usable industry taxonomy (derived from NAICS / GICS) that works:
	•	with brand mentions (e.g. “Barclays”, “Tesco”); and
	•	with generic/unbranded language (“a major UK supermarket”, “our retail banking app”).
	3.	Brand / entity mentions
	•	Robust extraction and normalisation of brands and key entities to a canonical “brand KB” (Barclays vs Barclaycard vs Barclays UK etc).

The outcome: a labelled dataset of prompts and responses that can be sliced by topic, industry and brand for analysis of LLM usage, behaviour, and “share of model” style metrics.

⸻

2. High-level approach

2.1 Conceptual architecture

For each prompt/response pair:
	1.	Ingest & normalise
	•	Separate prompt vs response (and optionally system/assistant messages if available).
	•	Basic clean-up: strip markup, detect language, flag code blocks.
	2.	Entity layer (brands and other entities)
	•	Run NER + entity linking to identify:
	•	Organisations, products, services, places, people.
	•	Map recognised entities to a brand knowledge base:
	•	canonical brand ID
	•	parent group
	•	industry sector(s).
	3.	Topic layer (IAB)
	•	Classify text into IAB Content Taxonomy 3.x categories, multi-label, at Tier 2–3 depth.
	•	Store the top-k labels with confidence for:
	•	prompt
	•	response.
	4.	Industry layer (sector classification)
	•	Use a dedicated classifier to infer industries from text even when no brands are present, using:
	•	domain vocabulary / jargon
	•	IAB labels as weak signals
	•	non-brand entities (e.g. “hospital”, “airline”, “university”).
	•	When brands are present, let the brand → sector mapping act as a strong prior / override.
	5.	Interaction / intent layer (optional but recommended)
	•	FrameNet-inspired small taxonomy capturing how the model is being used:
	•	Ask / explain / inform
	•	Compare / evaluate
	•	Create / rewrite / translate
	•	Plan / recommend
	•	Troubleshoot / debug / optimise
	•	This gives an extra analytic dimension beyond “what is it about?” → “what is the user trying to do?”
	6.	Storage
	•	Persist:
	•	raw text (or hashed, depending on privacy),
	•	labels + scores for each axis,
	•	entities with canonical IDs,
	•	relevant metadata (timestamp, channel, model, etc.).

⸻

3. Methodology and design choices

3.1 Taxonomy choices
	1.	Topics: IAB Content Taxonomy 3.x
	•	Widely used for contextual classification in digital advertising and brand safety.
	•	Hierarchical; supports multi-level aboutness (e.g. “Business & Finance > Banking”) which maps nicely to LLM use cases.
	2.	Industries: compressed NAICS/GICS-derived taxonomy
	•	NAICS is the official US industrial classification with 20 sectors, but very fine-grained at 6 digits.
	•	GICS has 11 sectors and 163 sub-industries used by finance.
	•	Proposal: design a 30–60 bucket taxonomy (e.g. Retail Grocery, Retail General, Retail E-commerce, Retail Banking, Insurance, Telco, Media & Entertainment, Auto OEM, Auto Retail, Government – Central, Government – Local, Healthcare – Provider, Healthcare – Pharma, etc.), each mapped back to NAICS/GICS codes for interoperability.
	3.	Brands: custom brand KB + standard schemas
	•	Use a simple internal schema similar to schema.org/Organization & Product to store canonical brand entities and metadata.
	•	Populate with:
	•	key clients,
	•	big global brands,
	•	long tail via external lists (e.g. stock indices, top advertisers, major retailers).

3.2 Modelling strategy
	1.	NER + Entity Linking (Brands)
	•	Start with a strong modern NER model (transformer-based) and fine-tune or prompt an LLM to:
	•	identify organisation and product mentions;
	•	map them to canonical brands using fuzzy matching + heuristic features (country, industry, context terms).
	•	Use an entity linking approach similar in spirit to standard EL work where surface forms are mapped to KB entries based on lexical similarity and contextual embeddings.
	2.	Topic classification to IAB
	•	Use a multi-label classifier (fine-tuned transformer or LLM-in-the-loop) that maps text to IAB codes, inspired by existing IAB text classifiers used for contextual ads.
	•	Outputs:
	•	list of IAB nodes
	•	probability/confidence per node.
	3.	Industry classification independent of brands
	•	Build a text → sector classifier, using:
	•	labelled firm descriptions / web text mapped to NAICS/GICS from public datasets, as in BEACON and similar systems.
	•	research using BERT/LLM-based models for industry classification from textual disclosures as a conceptual guide.
	•	At inference:
	•	Always run the sector classifier on the prompt/response text.
	•	When brands are present:
	•	combine the sector classifier’s distribution with brand-derived sector priors (e.g. via simple Bayesian or weighted averaging).
	•	When brands are absent:
	•	rely purely on the sector classifier (optionally nudged by IAB verticals).
	4.	Interaction / intent classification (FrameNet-inspired)
	•	Use FrameNet primarily as a conceptual guide: it catalogues frames like Commerce_buy, Questioning, Statement, Judgment etc.
	•	Define 10–20 interaction labels and train a classifier using:
	•	manually labelled prompts,
	•	simple pattern features (e.g. “write”, “explain”, “compare”, “debug”, “design”, “optimise”),
	•	optional supervision from off-the-shelf frame-semantic parsers where they add value.

⸻

4. Implementation plan (Python application)

Phase 0: Scoping and taxonomy design (1–2 weeks)
	1.	Lock the taxonomies
	•	Finalise:
	•	IAB tier depth (e.g. Tier 2–3).
	•	30–60 industry sectors with mappings to NAICS/GICS.
	•	Brand KB schema and initial population strategy.
	•	Interaction / intent label set.
	2.	Non-functional requirements
	•	Volume (prompts/day), latency targets, privacy constraints (hashing, PII handling), deployment environment (local, cloud, Docker).

Deliverables:
	•	Taxonomy spec (topics, sectors, brands schema, interaction types).
	•	High-level architecture diagram.

⸻

Phase 1: Data and ground truth (2–4 weeks)
	1.	Data collection
	•	Assemble a representative sample of prompts/responses (anonymised as needed) across:
	•	multiple sectors,
	•	multiple use cases (research, coding, creative, planning, etc.),
	•	branded and unbranded language.
	2.	Labelling guidelines
	•	Create concise guidelines for annotators (internal or yourself):
	•	how to assign IAB labels,
	•	how to assign sectors,
	•	how to mark brands and entities,
	•	how to label interaction type.
	3.	Manual annotation
	•	Label a few thousand examples, stratified by sector and channel.
	•	Use this as your evaluation + training set for lightweight models and for validating LLM prompts.

Deliverables:
	•	Annotated dataset.
	•	Labelling guidelines.

⸻

Phase 2: Core Python pipeline (4–6 weeks)

Implement as a modular Python package + CLI/REST API:
	1.	Project skeleton
	•	src/ structured into:
	•	ingest/ (I/O, cleaning, language detection),
	•	ner/ (entity extraction and linking),
	•	topics/ (IAB classifier),
	•	industry/ (sector classifier + combination logic),
	•	intent/ (interaction classifier),
	•	kb/ (brand knowledge base access),
	•	api/ (FastAPI app if you want HTTP access),
	•	cli/ (batch processing for files / streams).
	2.	Brand KB and NER
	•	Build brand KB (e.g. SQLite/Postgres or JSON-to-start):
	•	tables: brands, aliases, sectors, groups.
	•	Integrate a transformer-based NER model (or an LLM call wrapper) with:
	•	post-processing to normalise text,
	•	fuzzy alias matching to KB,
	•	disambiguation rules for common words (“Apple”, “Orange”, “Shell”, “Target”).
	3.	IAB topic classification
	•	Implement a classifier function:
	•	Option A: fine-tuned open model.
	•	Option B: call out to an LLM with a constrained prompt that maps to IAB codes, then normalise to your schema.
	•	Integrate into the pipeline with config for:
	•	top-k labels,
	•	minimum confidence threshold.
	4.	Industry classification
	•	Implement the sector classifier as a separate module:
	•	either a fine-tuned transformer on NAICS/GICS-derived data, collapsed to your 30–60 sectors;
	•	or an LLM prompt that outputs sector labels from your taxonomy.
	•	Combine:
	•	sector classifier distribution,
	•	brand-derived sector priors,
	•	optional IAB-derived nudges.
	5.	Intent classification
	•	Implement initial version using simpler techniques:
	•	rules + small ML model or LLM prompt to output one or more interaction labels.
	6.	Persistence
	•	Choose storage:
	•	simple: write JSONL with full classification result for each interaction;
	•	richer: DB with tables for interactions, labels, entities.

Deliverables:
	•	Working Python package.
	•	Simple API + CLI to classify a file / stream.

⸻

Phase 3: Evaluation, tuning and QA (3–4 weeks)
	1.	Metrics and tests
	•	For each axis (topics, sectors, brands, intent):
	•	precision, recall, F1 on the labelled dataset,
	•	confusion matrices (e.g. “Retail vs E-commerce vs CPG” confusions).
	2.	Human-in-the-loop review
	•	Run the pipeline on fresh data; spot-check:
	•	misclassified industries (e.g. “Fintech” going to “Generic tech”),
	•	missing or wrong brands,
	•	nonsensical IAB labels,
	•	intent labels that don’t reflect how prompts are used.
	3.	Refinement
	•	Update:
	•	brand KB (more aliases, more brands),
	•	sector mapping rules,
	•	IAB classifier thresholds,
	•	intent label definitions.

Deliverables:
	•	Evaluation report.
	•	Refined models/config.

⸻

Phase 4: Productisation and integration (2–4 weeks)
	1.	Operationalising
	•	Containerise with Docker.
	•	Add monitoring/logging hooks:
	•	throughput, latency, error rates,
	•	distributions of label outputs (for drift detection).
	2.	Integration points
	•	Define how upstream systems send data:
	•	e.g. event stream from your LLM logging stack,
	•	batch files, or message queue (Kafka, Pub/Sub).
	•	Define downstream consumers:
	•	warehouse tables for BI,
	•	dashboards for “share of model”, brand usage, sector-level analytics.
	3.	Documentation
	•	Developer docs: how to run, extend, deploy.
	•	Analyst docs: how to interpret labels, example queries.

Deliverables:
	•	Docker image / deployment scripts.
	•	Docs and examples.

⸻

5. Risks and mitigations
	1.	Ambiguous language and sectors
	•	Risk: “tech company” with no more detail.
	•	Mitigation: allow multi-label sector outputs + “Unknown / Generic Tech” bucket; use brand priors when available.
	2.	Brand ambiguity and hallucinations
	•	Risk: “Orange”, “Target”, or hallucinated brands in responses.
	•	Mitigation: only accept brand matches above a similarity threshold and where KB metadata matches surrounding context; track an “uncertain entity” flag.
	3.	Taxonomy drift / maintenance
	•	Risk: taxonomies get stale as new sectors or brands emerge.
	•	Mitigation: periodic KB updates; simple admin tooling to add brands, sectors, and alias rules.
	4.	Cost / latency if using LLM-in-the-loop
	•	Risk: expensive to classify everything via an external LLM.
	•	Mitigation: start with LLM prototyping, then distil into local transformer models for high-volume paths.