#! /usr/bin/env bash 
poetry run autoflake --remove-unused-variables --remove-all-unused-imports --ignore-init-module-imports --recursive --in-place .
poetry run isort .
poetry run black .
poetry run mypy pyrefchecker tests
