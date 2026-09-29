# NOREC-0b candidate v2 verification

The frozen patch is `norec0b-v2.patch`. Source snapshots are in `v2/`; `norec0b-v2-hashes.json` records their hashes. No main-tree test or compiler files were edited.

The change follows callable dictionaries through module, class, instance and local storage. Constant subscript/get keys select matching dictionary entries; dynamic keys retain all candidates. Dictionary storage itself does not invoke the stored function.

Lambdas have separate graph nodes. Direct calls, assigned callables, queue removal and synchronous callback parameters retain call edges. The continuation regression checks driver-to-lambda and lambda-to-step edges while proving that scheduling does not create step-to-lambda invocation.

Untyped instance-attribute delegation is unresolved, not assumed to target the owner's class. Conservative scans retain possible candidates. `_Func.parent` no longer participates in generated repr. Scanner self-tests now check recursive dataclass methods, and A7 scans with unresolved edges must agree with ordinary scans.

Verification:
- Expanded scanner suite against v2: 35 passed in 1.68 seconds, `candidate-v2-pytest.log`.
- Same tests against preserved baseline scanner: 15 failed and 20 passed in 1.26 seconds, `before-v2-pytest.log`.
- Current A7 ordinary and unresolved-edge groups agree at 31. The allowlists are unchanged.
- Scanner self-scan reports no function cycles and no recursive generated dataclass methods.

This batch closes the requested concrete NOREC-0b mechanisms. It does not remove compiler recursion or fully model Python dynamic dispatch. Dictionary item-assignment mutation, arbitrary container protocols, singledispatch registrations and inferred callable factory returns remain unsupported and are documented in the scanner header.

Controller clarification after GLM review: the unmodelled forms also include `dict(...)` construction, augmented container assignment such as `queue += [...]`, and `functools.partial`. The main scanner header now lists these limits. The archived v2 source hashes identify the pre-clarification candidate, not the final header.
