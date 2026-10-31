# Controlled React builds

Section 5's local source/build lane now supports React 19.3.1, React DOM 19.3.1 and scheduler 0.28.0, with TypeScript 5.9.3 and declarations pinned to `@types/react`/`@types/react-dom` 19.3.0 and csstype 3.2.2. Exact versions and registry integrity records are stored in `tooling/frontend/package-lock.json`. Install once with:

```powershell
npm ci --ignore-scripts --prefix tooling/frontend
```

No application package installation occurs during synthesis or verification. Generated package scripts, Vite configuration, TypeScript configuration and plugins are ignored. This extends the existing esbuild lane; a separate Vite toolchain is not implemented.

## Resolution and execution boundaries

Application bare imports are limited to `react`, `react/jsx-runtime`, `react/jsx-dev-runtime`, `react-dom` and `react-dom/client`. The production bundler uses esbuild's automatic JSX transform and replaces `process.env.NODE_ENV` with `production`. Runtime implementation files are parsed from the fixed React/React DOM/scheduler closure. Private package paths, direct scheduler imports, arbitrary npm packages, URLs and host modules remain blocked. Files must resolve inside the pinned package roots, including realpath checks against symlink escapes. The bundler never evaluates application or React code in Node.

The plugin uses the documented [esbuild resolution/load hooks](https://esbuild.github.io/plugins/). The human-authored counter uses React's documented [client root API](https://react.dev/reference/react-dom/client/createRoot). Runtime execution occurs only in the existing isolated-browser lane. This does not provide a filesystem/network sandbox for the upstream Python REPL.

Typechecking copies only a fixed list of trusted declaration files into a temporary verification directory. A fixed paths map and explicit source-file list bind imports to those files; generated declarations/configuration do not control dependency discovery. If the pinned runtime or declarations are unavailable, the relevant check is unmeasured, not functional success or a source error to repair.

React bundles include `THIRD_PARTY_LICENSES.txt`. Distribute the complete built directory, including this notice. Build reports list the pinned runtime closure only when vendor modules were included. Source/config hashes now cover TSX/JSX, helper scripts and the frontend/browser lockfiles, and source ZIP packaging includes these fixtures.

## Measured offline evidence

`examples/fixtures/react-counter` is human-authored engineering input, not model output. It passes actual strict TypeScript checking, a production bundle, browser increment/reset interactions and a basic accessibility audit. A wrong component prop fails the real compiler. Forbidden package/host/URL imports fail before browser execution. A missing-tool regression keeps build success null. These checks establish this narrow offline path only; genuine model-backed synthesis, broader packages and containerized RLM integration remain open.
