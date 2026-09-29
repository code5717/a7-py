#!/bin/bash
set -u
REPO=/home/cx89/Projects/pl-dev/a7-py
CASE="$1"
NAME=$(basename "$CASE" .a7)
OUT=/tmp/a7-glm53-repair-review/out/$NAME.zig
cd "$REPO"
uv run python main.py "$CASE" -o "$OUT" > /tmp/a7-glm53-repair-review/out/$NAME.a7out 2> /tmp/a7-glm53-repair-review/out/$NAME.a7err
EC=$?
MSG=$(grep -m1 -E "error:" /tmp/a7-glm53-repair-review/out/$NAME.a7out /tmp/a7-glm53-repair-review/out/$NAME.a7err 2>/dev/null | head -1 | sed 's/.*out://' | cut -c1-130)
echo "== $NAME : a7-exit=$EC ${MSG:+| $MSG}"
