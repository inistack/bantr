#!/usr/bin/env bash
# Run the same checks CI runs. Usage: bash scripts/check.sh
set -euo pipefail
poetry run ruff check .
poetry run ruff format --check .
poetry run flask --app wsgi db check
poetry run pytest -q --cov=app