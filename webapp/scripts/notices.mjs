import {readFile,writeFile,readdir} from 'node:fs/promises';
const lock=JSON.parse(await readFile('package-lock.json','utf8'));const notices=[];
for(const [key,value] of Object.entries(lock.packages)){if(!key||value.dev||value.optional)continue;const pkg=JSON.parse(await readFile(key+'/package.json','utf8'));const names=(await readdir(key)).filter(n=>/^licen[sc]e(?:\.|$)/i.test(n));let content='';for(const name of names)content+='\n'+await readFile(key+'/'+name,'utf8');notices.push(`${pkg.name} ${pkg.version} — ${pkg.license}\n${content}`);}
for(const name of await readdir('node_modules/unpdf/dist/licenses'))notices.push(name+'\n'+await readFile('node_modules/unpdf/dist/licenses/'+name,'utf8'));
await writeFile('ui/third-party.txt','Ritmo web — avisos de componentes JavaScript\nSem DLLs ou runtime Windows neste pacote.\n\n'+notices.join('\n\n--------------------------------\n\n'));
