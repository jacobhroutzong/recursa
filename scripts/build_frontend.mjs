// Trusted build helper: generated modules are parsed, never evaluated.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {vendorResolver} from './react_vendor.mjs';

const require = createRequire(import.meta.url);
let text = '';
for await (const chunk of process.stdin) text += chunk;
const input = JSON.parse(text);
const esbuild = require(path.resolve(process.argv[2], 'esbuild/lib/main.js'));
if (esbuild.version !== '0.28.2') throw Error('Expected pinned esbuild 0.28.2');
const sources = new Map(input.artifacts.map(a => [a.path, a.content]));
const extensions = ['.ts', '.tsx', '.js', '.jsx', '.json', '.css'];
const outdir = path.resolve('recursa-output');
const vendor = await vendorResolver(path.resolve(process.argv[2]));

function resolve(request, importer, entry) {
  if (typeof request !== 'string' || request.includes('\\') || request.includes(':') || request.includes('\0') || request.startsWith('//')) return null;
  let candidate;
  if (entry) candidate = request.replace(/^\.\//, '');
  else if (request.startsWith('/')) candidate = request.slice(1);
  else if (request.startsWith('.')) candidate = path.posix.join(path.posix.dirname(importer), request);
  else return null; // No node_modules, remote resources, or automatic installation.
  candidate = path.posix.normalize(candidate);
  if (candidate === '..' || candidate.startsWith('../') || candidate.startsWith('/')) return null;
  const candidates = [candidate, ...extensions.map(e => candidate + e), ...extensions.map(e => candidate + '/index' + e)];
  return candidates.find(name => sources.has(name)) ?? null;
}

const plugin = {name: 'validated-artifacts-only', setup(build) {
  build.onResolve({filter: /.*/}, async args => {
    const dependency=await vendor.resolve(args);
    if(dependency)return dependency;
    const found = resolve(args.path, args.importer, args.kind === 'entry-point');
    return found ? {path: found, namespace: 'recursa'} : {errors: [{text: 'Import is missing or outside the allowed artifact set: ' + args.path}]};
  });
  build.onLoad({filter: /.*/, namespace: 'recursa-vendor'}, args=>vendor.load(args));
  build.onLoad({filter: /.*/, namespace: 'recursa'}, args => {
    if (!sources.has(args.path)) return {errors: [{text: 'Unknown artifact'}]};
    const suffix = path.posix.extname(args.path).slice(1);
    if (!['ts','tsx','js','jsx','json','css'].includes(suffix)) return {errors: [{text: 'Unsupported source loader'}]};
    return {contents: sources.get(args.path), loader: suffix};
  });
}};

try {
  const result = await esbuild.build({entryPoints: input.entries, outdir, bundle: true,
    write: false, metafile: true, minify: true, format: 'esm', platform: 'browser',
    target: ['es2022'], logLevel: 'silent', tsconfigRaw: {compilerOptions: {}},
    plugins: [plugin], legalComments: 'none', jsx:'automatic', jsxImportSource:'react',
    define:{'process.env.NODE_ENV':'"production"'}});
  const usesVendor=Object.keys(result.metafile.inputs).some(name=>name.startsWith('recursa-vendor:'));
  const outputs=result.outputFiles.map(file => ({path: path.relative(outdir, file.path).split(path.sep).join('/'), content_base64: Buffer.from(file.contents).toString('base64')}));
  if(usesVendor)outputs.push({path:'THIRD_PARTY_LICENSES.txt',content_base64:Buffer.from(await vendor.licenses()).toString('base64')});
  process.stdout.write(JSON.stringify({status: 'passed', version: esbuild.version,
    outputs, metadata: result.metafile, dependencies: usesVendor?vendor.versions:{},
    warnings: result.warnings.map(w => ({text:w.text, path:w.location?.file?.replace(/^recursa:/,'') ?? '<project>'}))}));
} catch (error) {
  const errors = (error.errors ?? [{text:'Bundler failed'}]).map(e => ({text:e.text,
    path:e.location?.file?.replace(/^recursa:/,'') ?? '<project>', line:e.location?.line ?? null}));
  const unavailable=errors.some(e=>e.text==='Pinned React toolchain unavailable');
  process.stdout.write(JSON.stringify({status:unavailable?'unavailable':'failed',version:esbuild.version,errors}));
  process.exitCode = 1;
} finally {
  esbuild.stop();
}
