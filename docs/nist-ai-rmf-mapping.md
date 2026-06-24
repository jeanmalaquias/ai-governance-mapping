# NIST AI RMF → unified controls

**Source:** [NIST AI Risk Management Framework 1.0](https://www.nist.gov/itl/ai-risk-management-framework)
(NIST AI 100-1, Jan 2023) and the
[Generative AI Profile](https://doi.org/10.6028/NIST.AI.600-1) (NIST-AI-600-1,
Jul 2024). The framework is organized into four functions: **GOVERN, MAP,
MEASURE, MANAGE**.

Mappings are interpretive aids, not a NIST conformance claim.

<!-- AUTOGEN:START -->
| Control | Citation |
| --- | --- |
| AIGOV-001 AI risk assessment before deployment | GOVERN 1.1; MAP 1.1 |
| AIGOV-002 Data governance and provenance | MAP 2.1; MEASURE 2.2 |
| AIGOV-003 Encryption at rest | MANAGE 2.2 |
| AIGOV-004 Data retention and minimization | GOVERN 1.2; MAP 3.4 |
| AIGOV-005 Human oversight | GOVERN 3.2; MANAGE 4.1 |
| AIGOV-006 Prompt-injection and input moderation | MEASURE 2.7; MANAGE 2.3 |
| AIGOV-007 Output handling and content safety | MEASURE 2.6; MANAGE 2.3 |
| AIGOV-008 Transparency and model documentation | GOVERN 1.3; MAP 5.1 |
| AIGOV-009 Audit logging of AI interactions | MEASURE 1.1; MANAGE 4.1 |
| AIGOV-010 Access control and least privilege | GOVERN 1.5 |
| AIGOV-011 Evaluation and drift monitoring | MEASURE 2.3; MANAGE 4.1 |
| AIGOV-012 Incident response and post-market monitoring | MANAGE 4.1; MANAGE 4.3 |
| AIGOV-013 Supply-chain and model provenance | MAP 4.1 |
| AIGOV-014 PII detection and sensitive-data handling | MAP 3.4; MEASURE 2.10 |
| AIGOV-015 Rate limiting and resource controls | MANAGE 2.2 |
| AIGOV-016 Bias and fairness testing | MEASURE 2.11; GOVERN 5.1 |
<!-- AUTOGEN:END -->

The **Generative AI Profile** (NIST-AI-600-1) sharpens MEASURE/MANAGE for LLM
risks — prompt injection, data leakage, and harmful content — which map to
AIGOV-006, AIGOV-007, AIGOV-009, and AIGOV-014.
