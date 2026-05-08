---
name: default
description: Universal default memory for arbitrary agentic input
purpose: factual
schema:
  content: str
recall_hints:
  typical_query: Free-text lookup across saved default memories
  recency_matters: true
lifecycle:
  importance: medium
  forgettable: true
---

# Default Memory

Use this memory for simple text notes or stringified JSON payloads that do not fit a more specific memory type.
