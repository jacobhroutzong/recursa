# Section 5 — optional pinned TypeScript verification

The optional compiler lives under `tooling/typecheck` and is pinned to TypeScript 5.9.3 in its npm lockfile. Install with `npm ci --ignore-scripts --prefix tooling/typecheck`. The development environment reused the package already cached for the portfolio; no model or GPU resource was used.

`recursa.typecheck.check_types` verifies artifact paths and writes only TypeScript sources into a temporary checking directory. It creates its own trusted tsconfig with `noEmit`, `strict`, `noResolve` and an explicit file list. It does not load generated tsconfig files, package scripts or compiler plugins. It clears inherited Node preload options and applies a process timeout. Source is parsed/typechecked, not executed. This is not a sandbox for untrusted source or a production build.

`check_sources(..., typescript_directory=..., scratch_directory=...)` combines these checks with JavaScript/JSON parsing. The local RLM adapter accepts an optional `typescript_compiler_directory` configuration pointing at the pinned compiler package; the default replay server never loads it. Missing/mismatched compiler versions stay unmeasured. Global or file-specific compiler errors remain failures. Functional success and build success remain null.

Actual offline tests accepted a typed task contract, rejected a string assigned to a number with TS2322, verified that a source-level throw was never executed, and treated timeouts/unavailable compilers correctly. These fixtures are human-authored tests, not genuine generated applications. External dependency resolution and full app assembly/build/browser verification are still pending.
