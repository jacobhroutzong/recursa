# Reproduce the evidence

## CPU and replay

Use Python 3.11 or newer. On Windows, run `./scripts/start.ps1` to run the CPU smoke and open the local replay server at port 7860. Pass `-PythonExecutable` to select an installed interpreter, or `-Port` if 7860 is in use. On other platforms, use the following commands.

```sh
python -m recursa.experiments --config configs/smoke.json --output runs
python -m recursa.server --port 7860
```

Run the first command again against the same output directory to reuse the completed checkpoint. Each batch folder contains the manifest, trial results, `metrics.csv`, and `recursa-artifacts.zip`. Import an individual trial's `run.json` in Studio. Run `python -S scripts/verify_checkout.py` for a dependency-free check of checkpointing, export, resume, and replay HTTP.

## Browser and contained model verification

Use the pinned tooling and commands in the [Verification workflow](../.github/workflows/verification.yml). It installs the optional Python lockfile, the locked Node packages, and Playwright Chromium. Run `python scripts/verify.py` for the full offline suite. For local Docker readiness and fresh output directories, see the [container probes](container-sandbox.md) and [contained runner](contained-rlm.md).

The [local model protocol](baseline-protocol.md) specifies the exact weights, reviewed cases, seed blocks and limits. The model server binds to loopback. Its process-local key is supplied through the environment. The [example provider configuration](../configs/live.example.json) shows the budget fields. The CPU batch CLI accepts smoke configurations, and authorized inference uses the separate benchmark or contained-runner entry point.

| Symptom | Check |
| --- | --- |
| Windows opens the Store instead of Python | Select the installed interpreter with `-PythonExecutable`, or use the bundled Python if available. |
| Browser results are unavailable | Install the lockfile in `tooling/browser` and the matching Chromium. On Ubuntu, the CI workflow contains the scoped AppArmor setup needed by the pinned browser. |
| Docker preflight fails | Start the local Linux engine and rebuild the pinned runtime with `python scripts/build_rlm_image.py`. Reports reject stale image and source combinations. |
| A candidate ends without browser measurements | Inspect the model calls, build outcome, and missing metrics in Studio. The benchmark preserves incomplete responses and failed verification. |
| A rerun chooses a new output folder | The configuration, specification, or source changed. Use the original inputs for checkpoint reuse. |
| The embedded Studio is asleep | Use the full-screen link and allow the CPU Space to wake. |

## Interactive Colab CPU acceptance

1. Run `python scripts/package_source.py` locally. Upload `recursa-source.zip` to `MyDrive/Recursa/` and open the [notebook](../notebooks/recursa_colab.ipynb) in Colab.
2. Select a CPU runtime and choose **Run all**. Review and grant the Drive mount in your own account. The notebook extracts the reviewed source and runs the CPU smoke through the same entry point as local execution.
3. Confirm that a batch appears under `MyDrive/Recursa/results` with a complete checkpoint, trial JSON, metrics CSV, and artifact ZIP. Reconnect with a fresh CPU runtime, grant Drive again if prompted, and rerun the notebook against the same source archive and output folder. Confirm the same batch ID and unchanged completed trial file. Import its `run.json` into Studio to confirm compatibility.
4. The local offline suite exercises recovery of an interrupted trial. For a separate Colab recovery probe, use a disposable output directory and retain the observed before-and-after checkpoint status. Keep those artifacts private unless reviewed for release.

This path runs the standard-library CPU benchmark. Colab availability and Drive authorization are verified in the interactive account. [Colab FAQ](https://research.google.com/colaboratory/faq.html)
