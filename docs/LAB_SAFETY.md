# Lab safety and containment policy

RampLab intentionally includes exploitable application routes and Solidity contracts. The following rules are mandatory for contributors and users.

1. Run the application on a workstation or disposable VM that you control.
2. Keep the host binding at `127.0.0.1`. Never publish it through a public reverse proxy, tunnel or shared server.
3. Use Docker Compose's internal network profile as provided. Do not attach the vulnerable app to a general-purpose network.
4. Do not connect public RPC endpoints, production wallets, real tokens, payment providers, banks or card processors.
5. Use only Alice/Bob seed data, mock payment callbacks and local development keys.
6. Never place private keys, seed phrases, credentials, personal data, real transaction references or identity documents in the repository, issues, screenshots or pull requests.
7. Keep vulnerable examples explicitly named, scoped and paired with remediation guidance.
8. Do not use the code as a template for a real exchange, wallet, payment service or custody system.
9. For workshops, give each learner an isolated VM/container and reset state between participants.
10. If you discover an issue that affects RampLab users outside the deliberately vulnerable exercise, follow `SECURITY.md`.

The Docker configuration reduces accidental exposure but cannot stop a user from intentionally changing it. A local-only design is part of the product's security model, not a marketing disclaimer.
