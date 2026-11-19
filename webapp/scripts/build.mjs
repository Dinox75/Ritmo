import {build} from 'esbuild';
import {readFile,mkdir,copyFile} from 'node:fs/promises';
await mkdir('dist/server',{recursive:true});await mkdir('dist/.openai',{recursive:true});
await build({entryPoints:['src/worker.mjs'],outfile:'dist/server/index.js',bundle:true,format:'esm',platform:'browser',target:'es2024',conditions:['workerd','worker','browser'],minify:true,legalComments:'eof',metafile:true,plugins:[{name:'raw-assets',setup(b){b.onResolve({filter:/\?raw$/},args=>({path:new URL(args.path.slice(0,-4),new URL('file:///'+args.resolveDir.replace(/\\/g,'/')+'/')).pathname.replace(/^\/([A-Z]:)/,'$1'),namespace:'raw'}));b.onLoad({filter:/.*/,namespace:'raw'},async args=>({contents:`export default ${JSON.stringify(await readFile(decodeURIComponent(args.path),'utf8'))}`,loader:'js'}));}}]}).then(async result=>{await import('node:fs/promises').then(fs=>fs.writeFile('dist/build-inputs.json',JSON.stringify(result.metafile,null,2)));});
await copyFile('.openai/hosting.json','dist/.openai/hosting.json');
console.log('Worker built (no desktop runtime, personal data or auth simulator).');
