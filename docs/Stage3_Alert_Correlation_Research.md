# Stage 3 — Alert Correlation & Noise Reduction

## Executive conclusion

Stage 3 should not be another generic supervised classifier. Its purpose is to transform a stream of individually classified alerts from Stage 2 into incident-level groups by identifying exact duplicates, near-duplicates, and related alerts occurring within the same operational episode.

Recommended architecture:

1. Deterministic normalization and exact deduplication.
2. Alert-family/signature matching.
3. Semantic similarity using embeddings.
4. Temporal and metadata constraints.
5. A correlation score / decision layer.
6. Graph construction and connected components (or clustering) for incident groups.
7. Optional ML ranking/anomaly models only where enough signal exists.
8. Claude only for ambiguous relationship explanation and incident summarization, not as the primary correlator.

## Why this is the next stage

The project brief says Agent 1 should identify alert type, determine severity/business impact/priority, and correlate duplicate or related alerts to reduce noise. Agent 2 then reviews logs, metrics, historical incidents, known error patterns, and generates probable root cause and remediation recommendations. Therefore correlation is the bridge between classification and RCA: it reduces many alert records to a smaller number of incident candidates.

The project brief explicitly describes high alert volumes and manual triage as the operational problem, and places correlation under Agent 1.

## What the historical dataset tells us

The workbook contains 889 records and 21 columns. There are 361 unique short descriptions, but 48 exact descriptions repeat; those repeated descriptions account for 576 records (about 64.8% of all records). The largest exact description occurs 97 times. This means deterministic duplicate/family handling is likely to produce substantial noise reduction before more sophisticated semantic correlation is attempted.

The three clients are Pizza Hut (427), EA Sports (243), and Bridgestone (219). Assignment groups are client-specific in several major queues, so client identity is a useful hard/soft correlation signal and should not be ignored.

The dataset is historical ticket data rather than raw observability telemetry. It has no native logs, metrics, traces, service dependency graph, or incident-parent identifier. Consequently, a real production correlation engine must later consume those signals through an observability/telemetry adapter. For the internship prototype, Stage 3 should operate on the historical alert records and, if desired, synthetic telemetry fixtures.

## Stage 3 input

Do not feed the entire historical ticket row. Use arrival-time data and Stage 2 outputs:

- alert_id
- created_at
- impacted_client
- normalized_description
- alert_type
- predicted_priority
- predicted_assignment_group
- extracted service / system / host / environment where available
- alert signature
- embedding

Do not use post-resolution fields to decide correlation in production-like evaluation, because they create leakage.

## Step 3.1 — Exact duplicate detection

Create a deterministic normalized form of the alert text. Remove or canonicalize:

- timestamps
- dates
- UUIDs
- ticket IDs
- IP addresses when they are dynamic identifiers rather than stable resources
- numeric counters when they are incidental
- whitespace and case differences

Then hash the normalized representation.

Example:

"ELB errors occurred at 11:06:00"
"ELB errors occurred at 11:09:30"

may map to the same alert family if the timestamp is incidental.

This layer is cheap, explainable, and should run before embeddings.

## Step 3.2 — Signature / alert-family matching

Create structured signatures from alert text. Examples:

- source system = Watcher
- client = EA Sports
- family = ELB error
- service = Mulesoft
- condition = error count threshold

A family key can be composed from stable fields:

client + alert_type + source + service + normalized error/event family

This is stronger than raw string equality because operational alerts often change only a timestamp, count, host, or other dynamic value.

## Step 3.3 — Semantic similarity

Use Sentence Transformer or Amazon Titan embeddings to represent alerts in vector space. Compute cosine similarity between a new alert and candidate recent alerts.

Important: similarity alone must not create an incident. Two alerts can use similar wording while belonging to different services or clients.

## Step 3.4 — Temporal correlation

Limit candidate comparisons to a bounded time window.

Start experimentally with windows such as 5, 15, 30, and 60 minutes and choose based on observed precision/recall on labeled correlation pairs. Do not permanently hard-code a window before evaluation.

Temporal proximity should be a feature, not proof of causality.

## Step 3.5 — Metadata constraints

Useful signals include:

- same client
- same service/application
- same host/container/node where available
- same environment
- same alert family
- same source/monitor
- Stage 2 alert type compatibility
- Stage 2 routing compatibility

Hard constraints should prevent obviously unrelated alerts from being merged. For example, the same error text from two different clients should not automatically become one incident.

## Step 3.6 — Correlation scoring

Use a transparent composite score rather than a black-box cluster immediately.

Illustrative starting score:

CorrelationScore =
0.35 * semantic_similarity
+ 0.20 * client_match
+ 0.15 * service_match
+ 0.15 * family_match
+ 0.15 * temporal_proximity

These weights are hypotheses for prototyping, not learned truth. Tune them using manually labeled related/unrelated alert pairs.

Suggested decision policy:

- high score + strong metadata agreement -> same incident
- medium score -> ambiguous; retain as candidate relationship
- low score or hard constraint violation -> separate incident

## Step 3.7 — Build an alert graph

Rather than clustering the entire dataset blindly, represent alerts as a graph.

Node = alert.
Edge = sufficiently strong evidence that two alerts are related.

Then connected components become candidate incident clusters.

This is often more natural for alert correlation than forcing every alert into one global clustering algorithm because relationships are pairwise and can be created incrementally as new alerts arrive.

A cluster should retain:

- cluster_id
- client
- first_seen
- last_seen
- alert_count
- highest_priority
- alert_types
- affected services
- representative alert
- member alert IDs
- correlation evidence

## Should we use DBSCAN?

DBSCAN is useful as an offline experiment because it can discover arbitrary-shaped groups and does not require the number of clusters in advance. It can therefore be tested on embeddings plus engineered metadata.

However, DBSCAN should not automatically become the production correlation engine. Real alert streams are incremental, density varies by alert family, and operational correlation usually has meaningful pairwise constraints. A graph-based, rule-plus-similarity approach is easier to explain and tune for this project.

Use DBSCAN/Agglomerative Clustering as benchmark experiments, not as the only mechanism.

## Is this supervised learning?

Not initially.

The first production-quality Stage 3 implementation should be hybrid unsupervised/deterministic:

exact match -> signature -> embedding similarity -> temporal/metadata gating -> correlation score -> graph cluster

If later you obtain labels such as:

(alert A, alert B) -> related / unrelated

then Stage 3 can become a supervised pairwise-ranking or classification problem.

Potential later models:

- Logistic Regression over pairwise features
- Gradient-boosted trees over engineered pairwise features
- Siamese/contrastive embedding model if a sufficiently large labeled pair dataset exists

With only 889 historical tickets and no relationship labels, do not start there.

## Where anomaly detection fits

Anomaly detection is related but not identical to correlation.

Correlation asks:
"Do these alerts belong to the same incident?"

Anomaly detection asks:
"Is this alert/event pattern unusual?"

Anomaly detection can be added later for telemetry signals, but it should not replace correlation. CloudWatch, for example, supports anomaly-detection alarms and composite alarms; composite alarms are explicitly intended to aggregate multiple alarm states and reduce notification noise.

## Production telemetry path

The project brief says the future system consumes monitoring/observability signals and Agent 2 reviews logs and metrics. In a real deployment, telemetry should be correlated using shared context where possible.

OpenTelemetry documents three major correlation dimensions for logs: time, trace/execution context, and resource context. Trace IDs and span IDs allow direct linking between logs and traces, while resource attributes identify the producing entity. Context propagation is therefore a powerful hard signal whenever telemetry is instrumented.

Production ingestion could look like:

Monitoring sources
 -> event bus / ingestion adapter
 -> normalized alert envelope
 -> Stage 2 predictions
 -> telemetry/context lookup
 -> Stage 3 correlation
 -> incident cluster
 -> Stage 4 RCA

## Stage 3 output

Instead of returning 10 separate alerts to Stage 4, return one incident object:

{
  "incident_id": "INC-00042",
  "client": "EA Sports",
  "first_seen": "2026-08-06T11:04:12Z",
  "last_seen": "2026-08-06T11:18:31Z",
  "alert_count": 7,
  "highest_priority": "2 - High",
  "alert_types": ["API", "INFRASTRUCTURE"],
  "services": ["ELB", "Mulesoft"],
  "representative_alert_id": "ALT-10291",
  "members": ["ALT-10291", "ALT-10292", "ALT-10293"],
  "correlation_confidence": 0.91,
  "evidence": [
    "same client",
    "same alert family",
    "high semantic similarity",
    "within 15 minute window"
  ]
}

## Where Claude belongs

Claude should receive the compact incident dossier after correlation, not millions of raw events.

Good uses:

- explain why alerts were grouped
- resolve genuinely ambiguous relationships
- produce a human-readable incident summary
- select a representative alert
- prepare the context package for Stage 4

Bad use:

"Send every incoming alert to Claude and ask which other alerts are related."

That is expensive, less deterministic, and harder to evaluate.

## Recommended Stage 3 stack

Python 3.12+
scikit-learn
Sentence Transformers for prototype embeddings
Amazon Titan Text Embeddings V2 for AWS-native embedding experiments
PostgreSQL + pgvector for persistent vectors and candidate retrieval
LangGraph for orchestration/state transitions
FastAPI for service API
pytest for tests
MLflow for experiments/threshold/weight tracking
Docker for reproducibility
AWS EventBridge/SNS/SQS or equivalent event transport in a real deployment
OpenTelemetry-compatible telemetry adapters for logs/metrics/traces when real observability access exists
Claude Sonnet via Amazon Bedrock for ambiguity/explanation, not primary correlation

## Evaluation plan

Because the current dataset contains no ground-truth correlation labels, Stage 3 needs a small annotation exercise.

Create a pairwise or cluster-level evaluation set:

Alert A | Alert B | related? | reason

Then measure:

- pairwise precision
- pairwise recall
- F1
- false-merge rate
- false-split rate
- noise reduction ratio
- average alerts per incident
- percentage of alerts safely grouped
- percentage routed to manual review

False merges are particularly important: combining two genuinely different production incidents is more dangerous than failing to merge a few duplicates.

## Recommended implementation sequence

Phase 1: normalization + exact duplicate hashing.

Phase 2: alert-family signatures + metadata gating.

Phase 3: embeddings + candidate retrieval.

Phase 4: correlation score and threshold tuning.

Phase 5: graph-based incident clustering.

Phase 6: benchmark against DBSCAN/Agglomerative clustering.

Phase 7: add telemetry correlation using trace/resource/time context when real telemetry becomes available.

Phase 8: Claude ambiguity/explanation layer.

## Final architecture

STAGE 1
Historical alert ingestion / cleaning / normalization
        |
        v
STAGE 2
Alert type + priority + routing
        |
        v
STAGE 3
Alert correlation & noise reduction
  |-- exact duplicate
  |-- signature/family
  |-- embeddings
  |-- temporal gate
  |-- metadata gate
  |-- correlation score
  |-- graph clustering
  |-- optional Claude adjudication
        |
        v
Incident cluster / incident dossier
        |
        v
STAGE 4
Incident analysis & RCA
  |-- logs
  |-- metrics
  |-- traces
  |-- historical incidents
  |-- runbooks / KB
  |-- causal / statistical evidence
  |-- Claude synthesis
        |
        v
Human review / remediation

## Key sources

1. Epsilon–Academia AI Collaboration, “Business Ask – AI-Powered Production Alert Management (Multi-Agent Framework),” uploaded project brief, pp. 7–8.
2. OpenTelemetry, “OpenTelemetry Logging” — log correlation by time, trace context, and resource context.
3. OpenTelemetry, “Context propagation” — correlation across traces, metrics, and logs.
4. Amazon CloudWatch, “Composite alarms” — aggregation of alarm states to reduce notification noise.
5. Pinjia He et al., “Drain: An Online Log Parsing Approach with Fixed Depth Tree,” IEEE ICWS 2017 — online parsing for large-scale log streams.
6. scikit-learn documentation — DBSCAN and clustering methods for offline experimentation.
7. 2026 research: Log-Insight — neuro-symbolic production incident diagnosis emphasizing reduction of raw telemetry into compact evidence before LLM synthesis.
8. 2026 research: AMER-RCL — agentic memory and recursive reasoning for root-cause localization, supporting reuse of prior reasoning within incident windows.
