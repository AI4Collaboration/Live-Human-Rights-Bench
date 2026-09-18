#!/bin/bash
#SBATCH --job-name=summary_6models
#SBATCH --account=def-zhijing
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=summary_6models_%j.log

set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$ROOT"
export PYTHONUNBUFFERED=1
: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY in the environment}"
exec bash scripts/run_roster.sh
