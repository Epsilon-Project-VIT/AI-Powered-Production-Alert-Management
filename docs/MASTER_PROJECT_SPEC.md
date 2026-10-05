EPSILON – ACADEMIA AI COLLABORATION

AI-Powered Production
Alert Management
A multi-agent AI framework for alert classification, correlation and root-cause analysis

Ingest

→

Classify

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

→

Correlate

→

Analyze

→

Communicate

1

Business problem & proposed solution
BUSINESS PROBLEM

PROPOSED SOLUTION

 Client teams spend significant time monitoring and manually triaging
production alerts.
 High alert volumes create alert fatigue and increase operational effort.
 Multiple alerts may represent the same underlying incident.

Deploy a Multi-Agent AI Framework to automate the initial
production alert analysis and incident response workflow.

 Engineers must analyze multiple systems to identify probable root causes.
 Delayed incident analysis can impact SLAs, operational costs and business risk.

Agent responsibilities
 Agent 1 — classification, prioritization and correlation of incoming alerts.
 Agent 2 — incident analysis, root-cause analysis, remediation and
communication.

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

2

Overall objective
From raw production noise to an evidence-backed, communicated resolution
Production Alerts
Understand each alert
Correlate related alerts
Analyze incident
Identify probable root cause
Recommend remediation
Draft incident communication
Human / Policy Gate

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

3

Final end-to-end architecture — stage 1 to stage 4
Data / Alert Source

STAGE 1 · ALERT INGESTION & NORMALIZATION
Ingestion

Cleaning

Validation

Normalization

Priority scoring

Routing

Claude fallback

Embeddings + HDBSCAN

Time / client / service check

Incident grouping

RCA ranking (Claude)

Recommendation + comms

STAGE 2 · ALERT UNDERSTANDING & ROUTING
Type / Severity / Impact

STAGE 3 · ALERT CORRELATION & INCIDENT GROUPING
Signature match

STAGE 4 · INCIDENT ANALYSIS, RCA & COMMUNICATION
Context builder

Historical RAG + KB

Human / Policy Gate
Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

4

STAGE 1

Alert data ingestion
INPUT SOURCES

Current prototype
Data Al ert Ti c k e t
( Sour c e dat a )

ACTUAL DATASET EXAMPLE

Segr egati on xl sx

889 historical ServiceNow incidents across Pizza Hut, EA Sports and Bridgestone

Al ert I D:
Cl I ent:

I NC 3528892

BRI DGESTONE

DESCRI PTI ON:

Future production
Live monitoring / observability platform
OpsRamp, ThousandEyes, Data Hub, FRMS — pushed via API / webhook

Stage 1 objective

Convert inconsistent historical / raw alerts into a consistent, machine-readable representation.

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

5

STAGE 1

Cleaning, validation & normalization
PROCESSING PIPELINE

DYNAMIC VALUES NORMALIZED
Read historical records

Timestamps
IP addresses

UUIDs

Request IDs
Large numeric IDs

Remove empty / useless fields

NORMALIZATION EXAMPLE
Validate required fields

Normalize alert information

Raw:
API timeout for request 7f3c8b1d
at 2026-08-06 11:06
Normalized:
api timeout for request <id>
at <timestamp>

Create standardized alert object
Why it matters

Normalization improves consistency for classification and becomes critical for
Stage 3 alert correlation.

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

6

STAGE 1

Standardized alert object
OUTPUT (JSON)

FROM RAW TO STANDARDIZED

{

Raw Alert

"al ert_i d": "I NC3528892",
"created_at": "2026-08-06T...",
"cl i ent": "Bri dgestone",
"descri pti on":
"BGSN batch extract ... FAILURE"

Clean + Validate + Normalize

}
Standardized Alert

Output → Stage 2

The standardized alert becomes the input to the alert-understanding models in
Stage 2.

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

7

STAGE 2

What Agent 1 determines
Standardized Alert

Alert Type

Severity

What kind of technical problem is this?

How technically serious is the alert?

Business Impact

What effect could this have on the client / business?

Priority = Severity + Business Impact + Context

Routing / Assignment Group

Alert Type

Severity

Business Impact

Priority

Routing

What kind of technical problem is
this?

How technically serious is the alert?

What effect on client / business?

How urgently should the team
respond?

Which assignment group handles it?

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

8

STAGE 2

Supervised ML model pipeline
MODELS

Normalized Alert

Primary: TF-IDF + Logistic Regression
Benchmark: TF-IDF + SVM · Embeddings + LR · Embeddings + SVM

Feature Extraction

TF-IDF + LR

TF-IDF + SVM

Embeddings + LR

Model Benchmarking
Calibration / Confidence

Confident → Accept

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

Uncertain → Claude fallback

LABEL AVAILABILITY
Alert Type

Requires labeling

Severity

Requires labeling

Business Impact

Requires labeling

Priority

Historical target exists

Routing

Historical Assignment Group exists

9

STAGE 2

Example: Bridgestone batch failure alert
INPUT

ILLUSTRATIVE MODEL PREDICTION

Al ert ID:

I NC3528892

Cl i ent:

Br i dgestone

Alert Type

BATCH / WORKFLOW

0.91

Descr i pt i on:

Severity

HIGH

0.87

Data Hub Al ert ( WORKFLOW): P1BGSN –
BGSN_Batch_Extract_Poi nt_Redemption_Delta_AZREWARDS FAILURE

Business Impact

HIGH

0.82

Note

Priority

2 - High

0.72

Assignment Group

Client Support Subscription Services –
Bridgestone

0.93

Confidence values are illustrative until the trained models produce real scores.

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

10

STAGE 3

From alert noise to incident

889

361

48

576 (~64.8%)

total records

unique short descriptions

exact descriptions repeated

records belong to repeated descriptions

Stage 2 processes

Stage 3 processes

ONE alert → ONE understanding

MANY alerts → are they related? → ONE incident

Important interpretation

A repeated description is evidence of a recurring alert pattern, but it does not automatically mean all occurrences belong to the same incident — Stage 3 needs semantic +
temporal + contextual correlation.

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

11

STAGE 3

Alert correlation & incident grouping
Many Enriched Alerts

Exact / Signature Match

Embeddings + HDBSCAN

Candidate Clusters

Time Proximity

Client Match

Service Match

Correlation Score

Confident → Incident Group

Ambiguous → Claude Adjudication

ONE INCIDENT

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

12

STAGE 3

Example: repeated Pizza Hut alert pattern
REAL DATASET EXAMPLE

STAGE 3 PROCESSING

Client: Pizza Hut PZHT_WATCHER_ALERT
PROD_[P1PZHT UNIFIED-ALERT]
Warning: SLA extracts are not yet delivered to
Pizza Hut...

Normalized signature

Same alert family

Embedding similarity

97
occurrences of this exact alert description in the dataset

HDBSCAN candidate cluster

Validate cluster

Same client? Close in time? Same service? Same family?

Incident grouping

Critical point

The repeated 97 occurrences indicate a recurring alert pattern, not one single incident. Temporal validation prevents incorrect merging.

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

13

STAGE 3

ML discovery + operational validation
Alert A

Alert B

Pizza Hut – API timeout

Alert C

Pizza Hut – API timeout

EA Sports – API timeout

Semantic similarity may be high, but the client differs — HDBSCAN alone is insufficient.

→

HDBSCAN

Candidate cluster

→

Temporal + client + service
validation

→

Correlation score

→

Final incident group

INCIDENT-1007

Alert A

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

Alert B

Alert C

Alert D

14

STAGE 4

Incident context & evidence extraction
INCIDENT-1007 + Related Alerts

Incident Context Builder

Logs

Metrics

Traces

Patterns

Anomalies

Dependencies

Evidence Store

The consolidated evidence store feeds directly into Stage 4b: RCA ranking & reasoning.

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

15

STAGE 4

RCA candidate ranking & reasoning
Evidence Store

Historical Incident RAG

Known Errors / Runbooks KB

RCA Candidate Ranking

Claude Reasoning

Root Cause + Evidence + Recommendation

This structured RCA output feeds directly into remediation recommendations and incident communication drafting.

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

16

STAGE 4

From historical alert to probable root cause
I NC3528891

Cl i ent:

EA Sports

CRI TI CAL_Aut oTi cket: EASS_WATCHER_ALERT

ALERT - P1EASS_ELB_ERRCHECK — 8 ELB errors occurred

ILLUSTRATIVE TELEMETRY RETRIEVED
LOGS

METRICS

TRACES

 DB connection timeout

 DB connections → 100%

 DB → Mulesoft → ELB

 DB pool exhausted

 API latency → 2700 ms
 ELB error rate → 17%

DB anomaly

DB timeout logs

DB precedes downstream failures

Historical similarity

RCA candidate ranking (illustrative)
ELB failure

0.24

Mulesoft service failure

0.55

DB connection-pool exhaustion

0.89
0

0.1

0.2

0.3

0.4

0.5

0.6

0.7

0.8

0.9

1

EA Sports alert = real dataset. Logs, metrics, traces and RCA = illustrative prototype telemetry.

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

17

STAGE 4

Evidence → RCA → recommendation
Anomaly Detection
Layer 1
→

Metrics

→

Rolling stats / Z-score / MAD + Isolation Forest

Anomaly score

Historical Similarity
Layer 2
Current Incident

→

Sentence Embedding

→

→

Vector Search

Similar Historical Incidents

RCA Candidate Ranking (initial: weighted ranker → later: Logistic Regression / Gradient Boosting)
Layer 3
Multi-source evidence

→

→

Evidence features

Candidate causes

→

Ranking

Claude Reasoning
Layer 4
Evidence + hypotheses + context

→

Claude

→

Structured RCA

ML detects and ranks · retrieval provides evidence · Claude reasons and synthesizes.
Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

18

STAGE 4

RCA output & remediation recommendation
RCA OUTPUT
Probable root cause

REMEDIATION FLOW

Root Cause

Database connection-pool exhaustion
Confidence: High

Supporting evidence

 DB metric anomaly

Runbook / Known Error Retrieval

DB-017

 DB timeout logs
 Trace ordering
 Historical incident similarity

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

Recommended Action
This recommendation is generated from structured RCA evidence and retrieved
runbook history — execution requires human approval.

19

STAGE 4

Incident communication
Support-team communication

Stakeholder communication

Incident:
INC-1007

EA Sports is currently experiencing elevated API failures.

Impact:
EA Sports API requests are experiencing elevated failures.
Probable cause:
Database connection-pool exhaustion.
Evidence:
Database saturation and timeout errors preceded downstream service failures.

The incident is under investigation. Initial analysis indicates a database
connectivity issue affecting downstream services.
The support team is validating the issue and following the approved remediation
procedure.
Next update: after remediation validation.

Recommended action:
Validate connection-pool saturation and follow DB-017.
Status:
Investigation / remediation pending approval.

Claude drafts the communication, grounded in structured RCA evidence and incident context — delivered to both support teams and stakeholders.

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

20

Business impact mapping
How the four-stage architecture delivers every outcome in the business ask
01 Operational Efficiency

02 Service Reliability

Automated triage → routing → correlation → RCA

Correlation → evidence → RCA → remediation

Automates alert ingestion, classification, prioritization, routing, correlation and initial RCA
instead of requiring manual triage for every alert.

Correlates related alerts, analyzes logs, metrics and traces, identifies the probable root
cause and recommends remediation.

MAIN STAGES

MAIN STAGES

Stage 1

Stage 2

Stage 3

Stage 4

Stage 3

Stage 4

03 Cost Optimization

04 Customer & Business Experience

Fewer duplicate investigations, less escalation

Business-impact-aware prioritization + communication

Reduces analyst and engineer time spent on repetitive alerts, duplicate investigations and
initial diagnosis — an outcome of automation, not a separate model.

Determines business impact to drive prioritization, accelerates incident understanding and
drafts stakeholder and support-facing incident communications.

MAIN STAGES

MAIN STAGES

Stage 2

Stage 3

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

Stage 4

Stage 2

Stage 4

22

Final architecture — what each stage produces
Stage

Input

Processing

Output

Stage 1

Raw / historical alert

Ingestion, cleaning, normalization

Standardized Alert

Stage 2

Standardized Alert

Type, severity, business impact, priority, routing

Enriched Alert

Stage 3

Multiple enriched alerts

Exact match, embeddings, HDBSCAN, time / context validation

Incident Group

Stage 4

Incident Group

Logs, metrics, traces, RAG, anomaly detection, RCA ranking, Claude

RCA + Recommendation + Communication

DATA LINEAGE
Raw Alert

→

Standardized Alert

→

Enriched Alert

→

Incident Group

RCA

→

Remediation Recommendation

→

Incident Communication

→

Human / Policy Gate

Epsilon – Academia AI Collaboration | AI-Powered Production Alert Management

21

FINAL TAKEAWAY

The system progressively converts noisy production alerts into evidencebacked incident intelligence and actionable support communication.

Ingest

Epsilon – Academia AI Collaboration

→

Classify

→

Correlate

→

Analyze

→

Communicate

