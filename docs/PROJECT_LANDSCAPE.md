# Adjacent open-source work and RampLab's differentiation

This is a lightweight public-repository scan performed during the November 2026 RampLab planning/build session. It is not an exhaustive market study and repository activity can change.

## Adjacent projects identified

- **LLM-FinSec Lab** — a deliberately vulnerable fintech API and AI security research environment covering API VAPT, authorization and AI tool-use security: https://github.com/Thinkersjnr1/llm-finsec-lab
- **Fintech-API-SecurityLab** — a fintech REST API security lab with vulnerable and secured paths: https://github.com/nahyanej1/Fintech-API-SecurityLab
- **Web3 Vulnerability Labs** — a collection of PoC-backed toy Web3 vulnerability patterns and exploit reasoning: https://github.com/ChargingFoxSec/web3-vulnerability-labs
- **Faillapop** — a vulnerable-by-design Solidity protocol for Web3 security practice: https://github.com/Faillapop/faillapop
- **Vulnerable iBanking Lab** — a deliberately vulnerable local internet-banking lab: https://github.com/bappe-sarker/vulnerable-ibanking-lab

## Positioning consequence

RampLab should not claim to be the first vulnerable fintech API, first vulnerable banking app, first smart-contract lab or first Web3 vulnerability collection.

Its intended differentiator is an integrated, reproducible crypto/fiat ramp workflow that connects:

1. Customer-facing conversion experience.
2. API authorization and quote handling.
3. Off-chain payment callback trust.
4. Multi-currency financial ledger and reconciliation.
5. Local smart-contract mint/redeem and vault logic.
6. Paired vulnerable and hardened implementations with evidence and regression tests.

The 0.1.0 MVP covers the initial simulator and standalone local contract exercises. The API-to-Anvil integration and deeper cross-layer attack chains remain follow-up work.

## How to maintain differentiation

- Prefer workflow-level scenarios over another list of isolated vulnerabilities.
- Make the ledger, transaction state machine and reconciliation invariants first-class.
- Include a learner's evidence and remediation workflow.
- Support African and global financial contexts using synthetic currency fixtures.
- Accept contributor-authored scenarios only when they include a clear business impact, local-only reproduction, hardened comparison and regression test.
