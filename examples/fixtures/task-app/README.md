# Human-authored application fixture

This small task application is test input for Recursa's assembly, compiler,
functional-verification and repair pipeline. It was authored during engineering;
it is **not an RLM-generated application or research result**.

The independent scenarios exercise the acceptance criteria in
`examples/specs/tasks.json`. No inference provider is used. Source is bundled into
a fresh output directory; browser checks use a separate loopback origin and a
clean browser context with external network access blocked.
