#!/usr/bin/env bash

set -e

PROJECT_NAME=scrape-cineco
export PYENV_VERSION=3.12

# Check that pyenv is installed
if ! command -v pyenv &> /dev/null
then
    echo "Install pyenv"
    exit 1
fi

# Create venv
python -m venv .venv \
    --clear \
    --prompt $PROJECT_NAME

# Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate

# Install dependencies
# shellcheck disable=SC2102
python -m pip install \
    --constraint pyproject.lock \
    --editable .[all]

# Install pre-commit hooks
pre-commit install --install-hooks
