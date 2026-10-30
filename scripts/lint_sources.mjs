// Trusted, fixed AST rules. No application module or config is evaluated.
import {createRequire} from 'node:module';
import path from 'node:path';
const require=createRequire(import.meta.url);
let raw=''; for await(const chunk of process.stdin) raw+=chunk;
const {artifacts,compiler}=JSON.parse(raw);
const ts=require(path.join(compiler,'lib/typescript.js'));
if(ts.version!=='5.9.3')throw Error('Pinned compiler required');
const checks=[];
for(const artifact of artifacts){
  if(!/\.[jt]sx?$/.test(artifact.path))continue;
  const file=ts.createSourceFile(artifact.path,artifact.content,ts.ScriptTarget.Latest,true);
  const diagnostics=[];
  const add=(node,rule)=>diagnostics.push({rule,line:file.getLineAndCharacterOfPosition(node.getStart(file)).line+1});
  function visit(node){
    if(node.kind===ts.SyntaxKind.DebuggerStatement)add(node,'no-debugger');
    if(ts.isVariableDeclarationList(node)&&!(node.flags&(ts.NodeFlags.Let|ts.NodeFlags.Const)))add(node,'no-var');
    if(ts.isBinaryExpression(node)&&[ts.SyntaxKind.EqualsEqualsToken,ts.SyntaxKind.ExclamationEqualsToken].includes(node.operatorToken.kind))add(node,'strict-equality');
    if(ts.isCallExpression(node)&&ts.isIdentifier(node.expression)&&node.expression.text==='eval')add(node,'no-direct-eval');
    ts.forEachChild(node,visit);
  }
  visit(file);
  for(const error of file.parseDiagnostics)diagnostics.push({rule:'parse-error',line:file.getLineAndCharacterOfPosition(error.start||0).line+1});
  checks.push({path:artifact.path,kind:'lint',status:diagnostics.length?'failed':'passed',diagnostics,diagnostic:diagnostics.map(d=>`${d.rule} at line ${d.line}`).join('; ').slice(0,2000)});
}
process.stdout.write(JSON.stringify({status:checks.some(c=>c.status==='failed')?'failed':'passed',checks,lint_success:checks.length?checks.every(c=>c.status==='passed'):null,scope:'Fixed AST rules only: parse errors, no-var, no-debugger, strict-equality, no-direct-eval'}));
