#!/usr/bin/env bash
set -euo pipefail

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
./venv/bin/pre-commit install
echo "Venv ready. Run: source venv/bin/activate"
