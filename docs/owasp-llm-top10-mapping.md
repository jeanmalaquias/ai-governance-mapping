# OWASP Top 10 for LLM Applications (2025) → unified controls

**Source:** [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/llm-top-10/).
These are the most critical security risks for LLM apps; the controls below are
the defensive measures.

<!-- AUTOGEN:START -->
| Control | Citation |
| --- | --- |
| AIGOV-002 Data governance and provenance | LLM04 (Data and Model Poisoning) |
| AIGOV-003 Encryption at rest | LLM02 (Sensitive Information Disclosure) |
| AIGOV-004 Data retention and minimization | LLM02 (Sensitive Information Disclosure) |
| AIGOV-005 Human oversight | LLM06 (Excessive Agency) |
| AIGOV-006 Prompt-injection and input moderation | LLM01 (Prompt Injection) |
| AIGOV-007 Output handling and content safety | LLM05 (Improper Output Handling) |
| AIGOV-008 Transparency and model documentation | LLM09 (Misinformation) |
| AIGOV-009 Audit logging of AI interactions | LLM01; LLM02 |
| AIGOV-010 Access control and least privilege | LLM06 (Excessive Agency) |
| AIGOV-011 Evaluation and drift monitoring | LLM09 (Misinformation) |
| AIGOV-013 Supply-chain and model provenance | LLM03 (Supply Chain) |
| AIGOV-014 PII detection and sensitive-data handling | LLM02 (Sensitive Information Disclosure) |
| AIGOV-015 Rate limiting and resource controls | LLM10 (Unbounded Consumption) |
| AIGOV-016 Bias and fairness testing | LLM09 (Misinformation) |
<!-- AUTOGEN:END -->

**Testing:** the OWASP risks double as a red-team checklist. A red-team suite of
prompt-injection, system-prompt-leak, and unbounded-consumption probes provides
the evidence for AIGOV-006, AIGOV-007, and AIGOV-015.
