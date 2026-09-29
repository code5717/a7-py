#!/bin/bash
set -u
REPO=/home/cx89/Projects/pl-dev/a7-py
CASE="$1"
NAME=$(basename "$CASE" .a7)
OUT=/tmp/a7-glm53-match-closure/out/$NAME.zig
cd "$REPO"
uv run python main.py "$CASE" -o "$OUT" > /tmp/a7-glm53-match-closure/out/$NAME.a7out 2>&1
EC=$?
MSG=$(grep -m1 "^error:" /tmp/a7-glm53-match-closure/out/$NAME.a7out | cut -c1-110)
ZIGE=$([ -f "$OUT" ] && echo zig-written || echo no-zig-file)
echo "== $NAME : a7-exit=$EC | $MSG | $ZIGE"
if [ $EC -eq 0 ] && [ -f "$OUT" ]; then
  cd /tmp/a7-glm53-match-closure/out
  zig build-exe "$NAME.zig" -femit-bin="$NAME.bin" > "$NAME.zigout" 2>&1
  if [ $? -ne 0 ]; then echo "   zig-build=FAIL | $(grep -m1 'error:' $NAME.zigout | cut -c1-110)"
  else timeout 5 "./$NAME.bin" > "$NAME.runout" 2>&1; echo "   zig-build=OK run-exit=$? | $(head -c 80 $NAME.runout | tr '\n' ' ')"; fi
fi
