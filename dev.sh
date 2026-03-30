#!/usr/bin/env bash
set -euo pipefail

CMD="${1:-help}"

case "$CMD" in
  test)
    pytest tests/ -v
    ;;
  test-cov)
    pytest tests/ --cov=custom_components.busminder --cov-report=term-missing --cov-fail-under=95
    ;;
  test-single)
    pytest "${2}" -v
    ;;
  lint)
    black --check .
    isort --check-only .
    flake8 .
    pylint custom_components/busminder
    mypy custom_components/busminder
    ;;
  format)
    black .
    isort .
    ;;
  validate)
    bash dev.sh format
    bash dev.sh lint
    bash dev.sh test-cov
    ;;
  install)
    pip install -r requirements-dev.txt
    ;;
  help)
    echo "Usage: ./dev.sh <command>"
    echo ""
    echo "Commands:"
    echo "  test          Run all tests"
    echo "  test-cov      Run tests with coverage (fail under 95%)"
    echo "  test-single   Run a single test file: ./dev.sh test-single tests/test_foo.py"
    echo "  lint          Run black/isort/flake8/pylint/mypy checks"
    echo "  format        Auto-format with black + isort"
    echo "  validate      format + lint + test-cov"
    echo "  install       Install requirements-dev.txt"
    ;;
  *)
    echo "Unknown command: $CMD. Run ./dev.sh help"
    exit 1
    ;;
esac
