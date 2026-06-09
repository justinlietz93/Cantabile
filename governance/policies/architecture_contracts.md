# Architecture contracts

Enforced mechanically by `.importlinter` (run `lint-imports`).

- `domain` imports nothing from other layers. Pure types and rules.
- `ports` may import `domain` only. Contracts, no concrete code.
- `application` may import `domain` and `ports`. Never `adapters`.
- `adapters` may import `domain` and `ports`. Never `application`/`presentation`.
- `presentation` is the composition root and may wire any adapter.
- `shared` is a leaf: cross-cutting utilities, no business rules.

If you need `application` to use a new capability, add a port and an adapter.
Do not import the adapter into `application`.
