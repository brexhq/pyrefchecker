#! /usr/bin/env bash 

# Format the code, and then run checks and tests

set -euo pipefail

poetry run autoflake --remove-unused-variables --remove-all-unused-imports --ignore-init-module-imports --recursive --in-place .
poetry run isort .
poetry run black .
poetry run mypy pyrefchecker tests
poetry run pyrefchecker .
poetry run pytest
