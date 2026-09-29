#!/bin/bash
# Run one A7 case: compile to /tmp zig, report stage outcomes.
# Usage: run_a7.sh <case.a7>
set -u
REPO=/home/cx89/Projects/pl-dev/a7-py
CASE="$1"
NAME=$(basename "$CASE" .a7)
OUT=/tmp/a7-glm53-language-audit/out/$NAME.zig
cd "$REPO"
uv run python main.py "$CASE" -o "$OUT" > /tmp/a7-glm53-language-audit/out/$NAME.a7out 2> /tmp/a7-glm53-language-audit/out/$NAME.a7err
EC=$?
LASTERR=$(grep -m1 -E "error|Error" /tmp/a7-glm53-language-audit/out/$NAME.a7out /tmp/a7-glm53-language-audit/out/$NAME.a7err 2>/dev/null | head -1 | cut -c1-160)
echo "== $NAME : a7-exit=$EC ${LASTERR:+| $LASTERR}"
