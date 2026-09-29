# Installed CLI artifact checks

Integration update: the patch is applied to the active verifier. The second
combined release gate passed wheel and source-distribution checks. GLM review 3
passed the installed workflows and a tampered-metadata negative control.
The following records the earlier isolated experiment.

Files from the isolated experiment remain under `tmp/installed-cli-patch/`.
The patch and successful log also have copies beside this report as
`installed-workflows.patch` and `installed-workflows-isolated.log`.

Original files:

- `installed-workflows.patch` changes `scripts/verify_wheel_install.py`.
- `verify_wheel_install.py` is the patched standalone copy.
- `source/` is a copy of the current Python package and build metadata.
- `fresh-artifacts/` holds distributions built from that isolated source.
- `fresh-verification.log` records successful wheel and source-distribution checks.
- `verification.log` records rejection of the earlier copied wheel.

The patch keeps legacy token and file-first Zig generation checks. It checks
installed package metadata and `a7.__version__` against wheel metadata, then
checks the installed `--version` output. Doctor must recognize Zig 0.16.0. On
the V1 target it must succeed; elsewhere it must return 2 and explicitly report
the unsupported environment. This does not qualify another platform.

Valid and invalid installed `check --format json` calls must have expected
status, exit codes and empty artifact reports. The test also compares the
project directory contents before and after each check. The temporary project
path includes spaces.

The previous two direct Zig builds are replaced by installed `a7 build` using
the debug profile, execution of that binary, and installed `a7 run` using the
release profile. Both must print exactly `wheel smoke 42\n` with exit code 0
and empty stderr. The same checks run for a wheel rebuilt from the extracted
source distribution.

Verification commands:

```bash
uv build --project tmp/installed-cli-patch/source --out-dir "$PWD/tmp/installed-cli-patch/fresh-artifacts"
uv run --locked python tmp/installed-cli-patch/verify_wheel_install.py --skip-build --verify-sdist --dist-dir "$PWD/tmp/installed-cli-patch/fresh-artifacts"
uvx --from bandit==1.9.4 bandit tmp/installed-cli-patch/verify_wheel_install.py -q --skip B404,B603
git apply --check tmp/installed-cli-patch/installed-workflows.patch
```

All four checks passed. No full release gate was run for this patch.

A preliminary run against copies of the earlier `dist` files failed because
the wheel lacked the new `--version` command. ZIP inspection confirmed that its
`a7/cli.py` lacked `package_version` and `--version`. This is a concrete negative
case that the old verifier did not detect. The active release gate was still
running, so these earlier distributions were not treated as its final output.
