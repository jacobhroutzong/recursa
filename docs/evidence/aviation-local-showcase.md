# Aviation Operations verified synthetic showcase

The case uses a fixed fictional fixture with four valid flights, one malformed row, two terminals, and two simulated alerts. Its UTC clock advances in deterministic five-minute exercise steps. It has no operational data source.

Local Qwen3-4B generated the HTML shell, stylesheet and flight, stand, and alert renderers. Host work corrected the document and renderers, supplied the fixture and exercise controller, and adjusted styling. The capture record includes source hashes and the original model-output hash for each generated file. The showcase is separate from the matched benchmark series and used zero paid API calls.

Four independent Chromium scenarios cover 40 steps. They check stable flight ordering and overlapping stands, scoped filters and flight detail, clock pause with acknowledgement persistence and reset, and keyboard summary preparation with the synthetic label at 390 pixels. The summary content and basic accessibility audit passed. Downloaded JSON bytes and full keyboard traversal are outside the declared checks.

The preview and ten replay frames came from the same verified build. Studio serves recorded images and source text. [Studio Artifact explorer](https://jacobroutzong-recursa.hf.space/#artifacts) · [Run evidence](../../apps/studio/generated-aviation.json)
