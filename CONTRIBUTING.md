# Contributing to RampLab

Thank you for helping improve a community security-learning environment.

## Ways to contribute

- Add or improve a challenge with a concrete fintech/Web3 scenario.
- Add a hardened counterpart and regression test for every new vulnerable example.
- Improve lab instructions, hints, facilitator notes or remediation explanations.
- Add API, ledger, concurrency or smart-contract tests.
- Improve accessibility, setup reliability or platform support.
- Review terminology and examples for African and global fintech contexts.

## Rules for vulnerability submissions

Every deliberate weakness must:

1. Be confined to a local lab route, contract or fixture.
2. Be marked clearly in source and documentation.
3. Have a challenge ID, objective, scope and reset procedure.
4. Include a hardened counterpart or a documented reason why a direct counterpart is unsuitable.
5. Include a test that demonstrates the vulnerable behaviour and a test for the expected secure behaviour.
6. Avoid real credentials, third-party targets, live payment services and public-chain deployment instructions.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
```

For contracts, install Foundry and run `cd contracts && forge test -vv`.

## Pull requests

- Keep PRs focused and explain the learning objective.
- Include tests and update the relevant docs/backlog.
- Do not commit `.env`, database files, private keys, seed phrases, screenshots containing personal data or real payment information.
- Explain whether the change affects the intentionally vulnerable path, the hardened path or both.
- Request review from a maintainer familiar with the affected area.

## Data and privacy

Do not submit real victim messages, personal data or private identifiers without explicit project approval and a documented lawful basis, minimisation plan and review. Synthetic examples are preferred. Report potentially sensitive material privately rather than opening a public issue.

By contributing, you agree that your contribution is provided under the repository's MIT licence unless a file states otherwise.
