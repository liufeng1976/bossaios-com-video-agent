# BossAI Video Agent · Commercialization Boundary

## Goal

Turn the recovered upstream capability set into a BossAI-owned customer product without redistributing third-party or recovered proprietary artifacts whose commercial redistribution rights are not documented.

## Allowed as the commercial product source of truth

- BossAI-owned product naming, UI, customer workflow and documentation.
- Reconstructed capability contracts and API behavior used as implementation references.
- New BossAI commercial frontend and license/entitlement integration.
- Components whose licenses explicitly permit commercial use and redistribution, subject to their notice requirements.

## Not allowed in a customer package until rights are documented

- The legacy upstream launcher binary.
- The legacy upstream Electron production renderer/bundle.
- Proprietary or unknown-license model weights.
- `HeyVideo/key.txt` or any copied activation/provider secret.
- Original user data, cookies, sessions, activation files or customer data.

## Commercial release gates

1. BossAI brand/UI is the only customer-facing product identity.
2. BossAI-owned license/entitlement replaces the legacy upstream authentication dependency.
3. Every redistributed model/runtime has a recorded commercial license and required notices.
4. Customer installer contains no recovered credentials or source-machine state.
5. Enabled publishing platforms pass real-account UAT; unsupported platforms fail closed.
6. A clean build can be reproduced without relying on the formal proprietary launcher/renderer.

## Current status

The recovered runtime is a validated engineering/reference baseline and can be used internally for compatibility testing. It is not yet the customer-distributable commercial package.
