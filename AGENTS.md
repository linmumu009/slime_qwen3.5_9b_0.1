# Repository working rules

For every iteration that changes tracked code, configuration, or documentation:

1. Add a concise row to the iteration summary table in `README.md`.
2. Create a new full iteration note under `docs/iterations/` using `docs/iterations/TEMPLATE.md`.
3. Never overwrite an older iteration note. Use the next three-digit iteration number.
4. Record the objective, concrete changes, verification evidence, risks, rollback method, and follow-up work.
5. Keep secrets, private keys, tokens, passwords, and local SSH connection notes out of Git.

These documentation updates are part of the same commit as the implementation they describe.
