#!/usr/bin/env bash
set -Eeuo pipefail
LOCK="/tmp/ep_writer.lock"
if ( set -o noclobber; echo $$ > "$LOCK") 2> /dev/null; then
  trap 'rm -f "$LOCK";' EXIT
  export EP_API_READONLY=1
  source "/Users/user/entertainment planner/venv/bin/activate"
  export PYTHONPATH="/Users/user/entertainment planner/entertainment-planner-api"
  python -m apps.places.workers.gpt_normalizer
else
  echo "Другой писатель уже работает. Выходим."
  exit 0
fi
