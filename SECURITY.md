# Security policy and scope

## Scope

This repository contains **lab-only** material: Dockerised open-source core
networks and a MAP/TCAP message tool that talks to a local mock over TCP.

Accepted use:

- learning how mobile cores and SS7 signalling are structured
- building and testing detections against simulated signalling behaviour
- teaching, research, and conference material that demonstrates the mechanism

Out of scope, and not accepted as contributions:

- code that reaches carrier SS7/Diameter/GTP networks
- interconnect, roaming-hub, or "SS7 access provider" onboarding
- provider or subscriber enumeration
- "locate a number" or SMS-interception workflows
- anything requiring a real subscriber identity, key, or live target

## Reporting a problem

If something here is unsafe or could be misused, please open an issue marked
`security` or contact the maintainers privately through the repository's
security advisory feature (GitHub: *Security → Report a vulnerability*).

Please do **not** open a public issue with working instructions for abusing a
live network.

## Maintainer stance

The lab deliberately stops at the boundary of the simulated network. Requests
to extend it across that boundary will be declined, even if technically
feasible. The value of the project is understanding the mechanism well enough
to defend it, and that does not require a live path.
