#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH="${1:-configs/english.yaml}"

python -m scam_baseline.cli --config "$CONFIG_PATH" audit
python -m scam_baseline.cli --config "$CONFIG_PATH" prepare
python -m scam_baseline.cli --config "$CONFIG_PATH" train --models nb svm charcnn

