# CanopyOS implementation plan

Product baseline: the user's supplied CanopyOS MVP brief. See
`docs/architecture.md` for contracts and explicit implementation assumptions.
The user authorized architecture and development; no additional planning approval
is needed for the specified P0/P1 scope.

1. Verify metrics and rules against hand-labelled masks.
2. Implement secure anonymous scan storage and HTTP contracts.
3. Connect real SegFormer and guarded Jev/Gemma adapters.
4. Build the English mobile capture, progress, report and history flow.
5. Verify browser behavior and real-model inference; prepare deployment docs.

Use single-process local deployment first. Provider credentials, external hosting
access and physical outdoor camera testing remain environment-dependent. Do not
claim provider tests or scientific validity based on mocked tests.
