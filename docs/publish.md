# Repository publishing

The public repository is [DDDYT24/DocTreeQA](https://github.com/DDDYT24/DocTreeQA).
The default branch is `main`.

## Validate and push changes

```sh
uv sync --locked --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pytest
git add .
git commit -m "Describe the change"
git push origin main
```

Inspect the **checks** workflow on the repository's **Actions** tab for the
pushed commit. It runs Ruff and pytest with the locked Python dependencies.
`reports/publication.json` records publication status; `reports/ci_status.json`
records an observed hosted run and the exact commit it tested.

After updating the saved publication or CI evidence, regenerate the delivery
records with:

```sh
uv run python scripts/update_readme_results.py
uv run python scripts/prepare_delivery.py
```

Keep personal `.xlsm` review copies local. They are ignored by Git. Windows
Excel acceptance is recorded separately in `docs/windows_acceptance.md`;
publication and a passing Python workflow do not establish VBA execution.
