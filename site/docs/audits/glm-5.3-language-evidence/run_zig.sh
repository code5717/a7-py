#!/bin/bash
# Build one emitted .zig with zig build-exe (Debug) and run it if build succeeds.
# Usage: run_zig.sh <name>
set -u
NAME="$1"
D=/tmp/a7-glm53-language-audit/out
cd "$D"
zig build-exe "$NAME.zig" -femit-bin="$NAME.bin" > "$NAME.zigout" 2>&1
BEC=$?
if [ $BEC -ne 0 ]; then
  MSG=$(grep -m1 -E "error:" "$NAME.zigout" | cut -c1-140)
  echo "== $NAME : zig-build=FAIL | $MSG"
else
  timeout 5 "./$NAME.bin" > "$NAME.runout" 2>&1
  REC=$?
  OUT=$(head -c 120 "$NAME.runout" | tr '\n' ' ')
  echo "== $NAME : zig-build=OK run-exit=$REC | $OUT"
fi
