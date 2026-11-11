# Security reference baseline

RampLab challenges should reference established security taxonomies rather than inventing vulnerability names.

## OWASP Smart Contract Top 10:2026

The current OWASP Smart Contract Top 10:2026 is explicitly forward-looking. OWASP describes it as using 2025 incident and survey information to forecast the risks expected to be most significant in 2026. It is an awareness baseline, not proof that every challenge maps one-to-one to a production finding.

Relevant categories for RampLab include:

- SC01: Access Control Vulnerabilities
- SC02: Business Logic Vulnerabilities
- SC03: Price Oracle Manipulation
- SC04: Flash Loan–Facilitated Attacks
- SC05: Lack of Input Validation
- SC06: Unchecked External Calls
- SC07: Arithmetic Errors
- SC08: Reentrancy Attacks
- SC09: Integer Overflow and Underflow
- SC10: Proxy and Upgradeability Vulnerabilities

Official references:

- <https://scs.owasp.org/sctop10/>
- <https://scs.owasp.org/SCWE/>
- <https://scs.owasp.org/sctop10/Web3-Attack-Vectors-Top15/>

## Foundry and Anvil

The Solidity exercises use Foundry. Anvil is the Foundry local Ethereum node for development and testing. RampLab's initial contract exercise uses Foundry's local test runner and does not require a public chain or fork.

Official reference: <https://getfoundry.sh/anvil/>

**Safety note:** Anvil development accounts and default mnemonic are public knowledge. Never reuse them outside a disposable local environment.
