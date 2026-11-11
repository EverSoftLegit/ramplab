# Security policy

## Scope

RampLab is intentionally vulnerable in named training routes and contracts. Those deliberate weaknesses are not security bugs in the context of the lab. Unexpected issues that leak host data, escape the intended lab boundary, corrupt contributors' environments or affect non-lab functionality are in scope.

## Reporting

Do not publish sensitive details in a public issue. Use GitHub's private vulnerability reporting feature when available, or contact the repository maintainers through a verified private channel listed in the repository profile.

Include:
- affected version/commit;
- affected component and environment;
- concise reproduction steps using only a local copy;
- impact and any containment concerns;
- suggested fix, if known.

Do not include real customer data, secrets, seed phrases, private keys or third-party targets.

## Support expectations

This is a community project without a guaranteed response SLA. Maintainers will triage reports as capacity permits. Please do not test against any hosted environment unless its owner has explicitly authorised it.

## Deployment warning

RampLab must not be deployed to the public internet. The repository contains intentionally exploitable routes and contracts. A report that demonstrates exploitation of a deliberately vulnerable lab challenge is expected and should be submitted as a learning contribution, not a security disclosure.
