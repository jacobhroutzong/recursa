// Read only this fixed, pinned trusted package closure. Never evaluate it in Node.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';

const versions={react:'19.3.1','react-dom':'19.3.1',scheduler:'0.28.0'};
const publicImports=new Set(['react','react/jsx-runtime','react/jsx-dev-runtime','react-dom','react-dom/client']);

export async function vendorResolver(directory){
  const roots=new Map();
  const trustedDirectory=await fs.realpath(directory);
  const trustedRequire=createRequire(path.resolve(directory,'../package.json'));
  let available=true;
  for(const [name,version] of Object.entries(versions)){
    try{
      const root=await fs.realpath(path.join(directory,name));
      const info=JSON.parse(await fs.readFile(path.join(root,'package.json'),'utf8'));
      if(info.version!==version||!root.startsWith(trustedDirectory+path.sep))available=false;
      roots.set(name,root);
    }catch{available=false;}
  }
  const virtual=async file=>{
    const actual=await fs.realpath(file);
    for(const [name,root] of roots){
      if(actual.startsWith(root+path.sep))return name+'/'+path.relative(root,actual).split(path.sep).join('/');
    }
    throw Error('Dependency path escapes trusted package roots');
  };
  const fileFor=async id=>{
    const split=id.indexOf('/'), name=id.slice(0,split), relative=id.slice(split+1);
    if(split<0||!roots.has(name)||relative.split('/').some(p=>['','..','.'].includes(p)))throw Error('Invalid vendor path');
    const file=path.join(roots.get(name),relative);
    if(await virtual(file)!==id)throw Error('Vendor symlink escape');
    return file;
  };
  return {
    versions:available?versions:null,
    async licenses(){
      const texts=[];
      for(const [name,version] of Object.entries(versions)){
        const file=await fileFor(name+'/LICENSE');
        texts.push(name+'@'+version+'\n'+await fs.readFile(file,'utf8'));
      }
      return texts.join('\n\n');
    },
    async resolve(args){
      if(args.namespace!=='recursa-vendor'&&!publicImports.has(args.path))return null;
      if(!available)return {errors:[{text:'Pinned React toolchain unavailable'}]};
      try{
        let id;
        if(args.namespace==='recursa-vendor'&&args.path.startsWith('.')){
          id=path.posix.normalize(path.posix.join(path.posix.dirname(args.importer),args.path));
          await fileFor(id);
        }else{
          const allowed=args.namespace==='recursa-vendor'?new Set([...publicImports,'scheduler']):publicImports;
          if(!allowed.has(args.path))throw Error('Unsupported dependency');
          id=await virtual(trustedRequire.resolve(args.path));
        }
        return {path:id,namespace:'recursa-vendor'};
      }catch{return {errors:[{text:'Dependency import is outside the pinned allowlist: '+args.path}]};}
    },
    async load(args){
      const file=await fileFor(args.path);
      if(!/\.(c?js|mjs|json)$/.test(file))throw Error('Unsupported vendor source');
      return {contents:await fs.readFile(file,'utf8'),loader:file.endsWith('.json')?'json':'js'};
    }
  };
}
