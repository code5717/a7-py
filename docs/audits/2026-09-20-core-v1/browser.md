# Browser verification limit

Date: 2026-09-20. Desktop and mobile browser acceptance is incomplete.

The reviewer read and announced the `browser-harness` skill. Local connection
checks returned:

```text
browser-harness --doctor
[ok  ] chrome running
[FAIL] daemon alive
[FAIL] active browser connections — 0
```

A normal harness invocation requesting `current_tab()` and `list_tabs()` exited
with code 1:

```text
browser-harness: daemon default didn't come up
```

Its local daemon log at
`/home/cx89/.config/browser-harness/tmp/bu-default.log` reported:

```text
fatal: chrome-not-running: no supported Chromium-family browser is running -- start Chrome, then retry
```

The doctor and daemon disagree about browser availability, but no usable
connection was established. The controlling agent independently checked the
CUA browser inventory and reported `apps=[]` and `browsers=[]`. That fallback
also had no available browser. This inventory result comes from the controller,
not a second tool call by this reviewer.

No cloud browser, installation, browser
reconfiguration, publication or paid service was used.

At the last gate-log check, native release example verification was still
running. This reviewer did not inspect the new site build, start a preview
server, capture screenshots, or verify rendered navigation/search. Existing
static checks do not replace those checks.

## Remaining acceptance

With a working local browser, inspect the newly built get-started, compiler and
release pages at desktop and mobile widths. Confirm the new commands and
profile/version requirements render correctly, navigate between those pages,
and search for `doctor`, `check`, `build` and `run`. Capture and inspect actual
screenshots. Record overflow, clipping, navigation and search results separately
from source-content validation.
