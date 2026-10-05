# Stage 4 — Incident Analysis & Root Cause Analysis (RCA)

## Executive recommendation

Stage 4 should be a hybrid diagnostic pipeline, not a single LLM call and not a pure supervised classifier.

Recommended flow:

Incident cluster from Stage 3
→ context/time-window builder
→ telemetry retrieval (logs, metrics, traces)
→ anomaly/event extraction
→ historical incident + known-error retrieval (RAG)
→ dependency/topology graph
→ root-cause candidate ranking
→ evidence aggregation/confidence
→ Claude Sonnet reasoning over the evidence only
→ structured RCA + remediation candidates + evidence citations
→ policy gate / human review

The project brief says Agent 2 reviews logs, metrics, historical incidents and known error patterns; identifies probable root cause; generates remediation/runbook actions; and drafts incident communications.

## 1. What Stage 4 must answer

Stage 3 answers: “Which alerts are one incident?”

Stage 4 answers:
1. What changed or became abnormal?
2. Which service/component/metric is the strongest root-cause candidate?
3. What evidence supports that hypothesis?
4. What historical incident/error pattern is similar?
5. What remediation or runbook action is appropriate?
6. What should be communicated to operators/stakeholders?

The output should be ranked hypotheses, not an unsupported single assertion.

## 2. Final architecture

                 STAGE 3 INCIDENT CLUSTER
                              |
                              v
                 +--------------------------+
                 | 1. Incident Context      |
                 |    Builder               |
                 +------------+-------------+
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
        LOG RETRIEVAL    METRIC RETRIEVAL   TRACE RETRIEVAL
             |                |                |
             v                v                v
       log parsing       anomaly scoring   trace/span analysis
             |                |                |
             +----------------+----------------+
                              v
                  2. Anomalous Evidence Layer
                              |
             +----------------+----------------+
             |                                 |
             v                                 v
      3. Historical/RAG                  4. Topology/
         retrieval                          dependency graph
             |                                 |
             +----------------+----------------+
                              v
                  5. Root-Cause Ranker
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
        temporal          anomaly           dependency
        precedence        strength          propagation
             |                |                |
             +----------------+----------------+
                              v
                    ranked RCA hypotheses
                              |
                              v
                  6. Evidence & Confidence
                              |
                    +---------+---------+
                    |                   |
                 HIGH                    LOW
                    |                   |
                    v                   v
              Claude reasoner      Claude + human
                    |                   |
                    +---------+---------+
                              v
                    7. Structured output
                              |
            +-----------------+----------------+
            |                                  |
            v                                  v
      RCA explanation                    remediation
      + evidence                        + runbook action
            |                                  |
            +-----------------+----------------+
                              v
                     Human/policy gate
                              |
                              v
                         Incident update

## 3. Why not “send incident to Claude”

A root-cause claim in operations should be grounded in observable evidence. A strong design makes Claude synthesize evidence produced by deterministic retrieval, anomaly detection, historical retrieval and system topology. Claude should not be the telemetry search engine or the source of truth.

Amazon Bedrock supports tool use, allowing the application to expose controlled functions that Claude can request; the application executes the tools and returns results. Bedrock structured outputs can constrain the final response to a JSON schema. This is useful for machine-readable RCA and controlled tool invocation.

## 4. Component 1 — Incident Context Builder

Input from Stage 3:
- incident_id
- member alert IDs
- first_seen / last_seen
- client
- predicted service/type/priority
- alert descriptions

Construct a bounded diagnostic window, for example:
T0 = first incident alert
context window = T0 - pre_window through T_last + post_window

The exact window must be tuned; do not hard-code it as truth.

The context builder is important because fetching all system logs and all metrics would create noise and cost.

## 5. Component 2 — Telemetry retrieval

### Logs
Retrieve logs using filters such as:
- time window
- client/environment
- service/resource
- severity
- error/exception signatures
- trace/span IDs when available

OpenTelemetry notes that logs can be correlated with traces through TraceId and SpanId and with telemetry origin through Resource context; time is also a basic correlation dimension.

### Metrics
Retrieve time-series around the incident for:
- latency
- error rate
- request rate
- CPU
- memory
- disk
- connection pool
- queue depth
- database metrics
- saturation indicators

Calculate baseline deviation rather than simply giving raw numbers to the LLM.

Useful first-wave anomaly methods:
- rolling z-score / MAD based thresholding for simple signals
- Isolation Forest for multivariate/tabular anomaly features
- later, time-series-specific models when sufficient telemetry history exists

A 2026 comparative study of anomaly detection and RCA in microservice systems evaluated iForest, KNN, LOF, SVM and clustering-style anomaly methods and found iForest strongest among the tested anomaly detectors in its scenarios; this is evidence for benchmarking, not proof that iForest is universally best.

### Traces
Retrieve:
- trace IDs
- spans
- latency by service
- error spans
- upstream/downstream services
- span timing and status

Trace data is particularly valuable for identifying where a request path first degrades.

## 6. Component 3 — Historical incidents / RAG

Create a historical incident knowledge base containing:
- incident/alert description
- symptoms
- affected services
- root cause
- resolution
- remediation
- runbook reference
- incident timeline
- relevant error signatures

Use semantic retrieval plus metadata filters.

Amazon Bedrock Knowledge Bases supports RAG over proprietary data, vector embeddings, retrieval, source attribution, and reranking; it also exposes a Retrieve operation so retrieval can be separated from response generation.

Do NOT use RAG as a replacement for live telemetry. It is supporting evidence.

## 7. Component 4 — Topology/dependency graph

Represent the production system as a graph:

service A → service B → database C
service A → queue D → worker E

Candidate root causes become graph nodes and dependencies become edges.

This matters because an upstream database or infrastructure fault can create downstream API/application alerts. Pure text similarity cannot reliably distinguish symptom from cause.

Research systems such as MicroRCA and CloudRCA use graph/topology-aware reasoning and multi-source telemetry; CausalRCA explicitly models anomaly propagation as a causal graph and ranks metrics for localization.

## 8. Component 5 — Root-cause ranking

This is the central non-LLM intelligence layer.

For every candidate component/metric/error pattern, create features such as:
- anomaly magnitude
- anomaly start time
- time precedence relative to symptoms
- number of affected downstream services
- log error severity/frequency
- trace failure concentration
- topology centrality / upstream position
- historical similarity
- known error signature match

Then rank candidates.

Recommended first implementation:

Candidate score = weighted evidence aggregation

with weights learned/tuned from a reviewed RCA dataset when possible.

Possible future supervised ranker after enough labels:
- Logistic Regression for explainable baseline
- Gradient-boosted trees for nonlinear feature interactions

Do not begin by fine-tuning a large transformer on the 889-row alert dataset.

## 9. Causal reasoning

Causality should be treated as a later layer, not assumed from correlation.

A strong path is:

anomaly detection
→ temporal ordering
→ topology constraints
→ causal/propagation ranking

CausalRCA research uses causal structure learning among monitoring metrics and ranks root-cause metrics through the resulting graph. CloudRCA combines KPIs, logs and topology with a knowledge-informed hierarchical Bayesian network.

For the internship prototype, a full causal-structure-learning system is optional. A topology-constrained evidence ranker is more practical and easier to validate.

## 10. Component 6 — Claude reasoning layer

Claude should receive the top-ranked evidence bundle, not raw system data indiscriminately.

Example input:

- Incident: INC-1024
- symptoms: API 5xx + latency
- earliest anomaly: database connection saturation at 10:41:12
- downstream symptom begins: API error rate at 10:41:35
- trace evidence: 68% of failed traces pass through DB connection layer
- logs: connection-pool exhaustion errors
- historical match: 0.87 similarity to incident INC-884
- topology: API → service B → database C

Claude's task:
1. compare candidate hypotheses
2. explain evidence for/against each
3. select probable root cause or state that evidence is insufficient
4. suggest evidence still needed
5. map the diagnosis to a known runbook/remediation

It should never be prompted to “guess the root cause.”

## 11. Structured RCA output

Recommended schema:

{
  "incident_id": "INC-1024",
  "status": "DIAGNOSIS_READY",
  "probable_root_cause": {
    "component": "database-connection-pool",
    "failure_type": "connection_exhaustion",
    "confidence": 0.86
  },
  "alternative_hypotheses": [
    {
      "component": "api-service",
      "reason": "downstream symptom",
      "confidence": 0.31
    }
  ],
  "evidence": [
    "metric_anomaly_123",
    "log_signature_881",
    "trace_pattern_442",
    "historical_incident_884"
  ],
  "recommended_actions": [
    "verify connection pool saturation",
    "follow runbook DB-017"
  ],
  "human_review_required": true
}

Bedrock structured outputs support schema-constrained JSON; strict tool use can similarly constrain tool inputs.

## 12. Prototype reality with the current Excel

The current workbook does not contain raw production logs, metrics, traces, runbooks, or a ground-truth root-cause column. Therefore Stage 4 cannot honestly be demonstrated as real production RCA from the Excel alone.

Prototype approach:

1. Use the historical alerts as incident-history/context records.
2. Create a small synthetic/mock telemetry layer:
   - mock logs
   - mock metric time series
   - mock trace/service dependencies
3. Create a small runbook/known-error knowledge base.
4. Build the exact same interfaces that production connectors would later implement.
5. Demonstrate RCA on controlled scenarios where the injected root cause is known.

The interface remains:

Excel/history → incident context → mock telemetry → RCA

and later:

Observability platform → incident context → real telemetry → RCA

## 13. Evaluation

Do not evaluate Stage 4 only on “does the answer sound correct?”

Use:
- Root cause service Top-1 accuracy
- Root cause Top-3 recall
- failure-type accuracy
- evidence precision / evidence coverage
- historical-case retrieval Recall@K
- recommendation correctness
- unsupported-claim/hallucination rate
- escalation rate
- latency and cost per incident

For the synthetic prototype, the known injected fault provides ground truth.

## 14. Recommended Stage 4 stack

Python
LangGraph
FastAPI
PostgreSQL + pgvector
OpenTelemetry-compatible telemetry model
Prometheus-compatible metrics adapter for production-style prototype interfaces
log search adapter
trace query adapter
Sentence Transformers / Amazon Titan Embeddings for retrieval
AWS Bedrock Knowledge Bases or custom pgvector RAG
Claude Sonnet via Bedrock
scikit-learn for initial anomaly detection/ranking experiments
NetworkX for dependency graph prototype
MLflow for experiment tracking
Docker/AWS deployment

## 15. Final architecture decision

STAGE 4 =

Telemetry retrieval
+ anomaly detection
+ historical/RAG retrieval
+ topology/dependency reasoning
+ root-cause candidate ranking
+ Claude evidence synthesis
+ structured output
+ human/policy gate

The central design principle is:

LLM = reasoning and synthesis
ML/statistics = anomaly/candidate ranking
RAG = historical/known-issue knowledge
Graph = system dependency structure
Telemetry = current evidence
Human = final authority for consequential remediation

This is the recommended bridge from Stage 3 incident groups into Stage 5 remediation/communication.
