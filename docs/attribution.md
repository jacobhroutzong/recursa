# Attribution and component licensing

Recursa applies the method described in *Recursive Language Models* by Alex L. Zhang, Tim Kraska, and Omar Khattab. The upstream runtime supplies the recursive completion loop. [Paper](https://arxiv.org/abs/2512.24601) · [Official RLM repository](https://github.com/alexzhang13/rlm)

| Component | Scope | Upstream license |
| --- | --- | --- |
| RLM runtime, pinned `rlms==0.1.3` | Optional contained inference and integration tests | [MIT](https://github.com/alexzhang13/rlm/blob/main/LICENSE) |
| Qwen3-4B GGUF | Separately obtained local weights | [Apache-2.0](https://huggingface.co/Qwen/Qwen3-4B-GGUF) |
| llama.cpp | Separately obtained local inference server | [MIT](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE) |
| React and React DOM | Optional generated React builds. The build writes their license notices alongside the output | [MIT](https://github.com/facebook/react/blob/main/LICENSE) |
| TypeScript | Optional source verification and build tooling | [Apache-2.0](https://github.com/microsoft/TypeScript/blob/main/LICENSE.txt) |
| Playwright | Optional browser tooling | [Apache-2.0](https://github.com/microsoft/playwright/blob/main/LICENSE) |

The Space packages Recursa's replay code, reviewed public data, and screenshots. It excludes the optional inference SDK, local model weights and binary, and development tool dependencies. Third-party packages retain their upstream licenses and notices. Recursa’s original code and documentation are licensed under Apache 2.0. [License](../LICENSE) · [Notice](../NOTICE)
