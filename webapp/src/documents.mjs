import {Unzip,UnzipInflate} from 'fflate';
import {XMLParser,XMLValidator} from 'fast-xml-parser';
import {getDocumentProxy} from 'unpdf';
import {need,LIMITS,Problem} from './domain.mjs';

const decoder=new TextDecoder('utf-8',{fatal:true});
export async function bounded(stream,max){const chunks=[];let size=0;const reader=stream.getReader();try{for(;;){const {done,value}=await reader.read();if(done)break;size+=value.length;need(size<=max,'Arquivo ou pedido grande demais.',413);chunks.push(value);}}finally{await reader.cancel().catch(()=>{});}const result=new Uint8Array(size);let at=0;for(const c of chunks){result.set(c,at);at+=c.length;}return result;}
export async function sha(bytes){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');}
export function base64(bytes){let s='';for(let i=0;i<bytes.length;i+=8192)s+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(s);}
export function from64(value){need(typeof value==='string'&&value.length<=Math.ceil(LIMITS.file/3)*4,'Original inválido.',413);try{return Uint8Array.from(atob(value),x=>x.charCodeAt(0));}catch{throw new Problem('Original em base64 inválido.');}}
function blocksFrom(text){need(text.length<=LIMITS.text,'Texto extraído excede 120 mil caracteres.',413);need(!text.includes('\u0000'),'Texto contém bytes nulos.');const blocks=[];for(const p of text.replace(/\r\n/g,'\n').split(/\n\s*\n/)){const clean=p.trim();for(let i=0;i<clean.length;i+=3000)blocks.push(clean.slice(i,i+3000));}need(blocks.length>0,'O arquivo não contém texto legível. PDFs escaneados exigem OCR, indisponível neste piloto.');return blocks;}
function unzipDocx(bytes){let total=0,entries=0,document,failed;const zip=new Unzip(file=>{entries++;need(entries<=512,'DOCX tem entradas demais.',413);need(!file.name.includes('..')&&!file.name.startsWith('/')&&!file.name.includes('\\'),'Caminho inseguro dentro do DOCX.');need(file.originalSize===undefined||file.originalSize<=LIMITS.expanded,'Expansão DOCX excessiva.',413);const target=file.name==='word/document.xml';const chunks=[];file.ondata=(err,chunk,final)=>{if(err){failed=err;return;}total+=chunk.length;need(total<=LIMITS.expanded,'Expansão DOCX excessiva.',413);if(target)chunks.push(chunk);if(target&&final){let size=chunks.reduce((n,c)=>n+c.length,0);document=new Uint8Array(size);let at=0;for(const c of chunks){document.set(c,at);at+=c.length;}}};file.start();});zip.register(UnzipInflate);try{for(let offset=0;offset<bytes.length;offset+=512){zip.push(bytes.subarray(offset,Math.min(bytes.length,offset+512)),offset+512>=bytes.length);if(failed)throw failed;}}catch(error){if(error instanceof Problem)throw error;throw new Problem('DOCX compactado inválido.');}need(!failed&&document,'DOCX sem word/document.xml válido.');return decoder.decode(document);}
export async function extract(bytes,filename){
 need(bytes.length>0&&bytes.length<=LIMITS.file,'Importe um arquivo de até 2 MiB.',413);need(typeof filename==='string'&&filename.length<=180&&!/[\x00-\x1f/\\]/.test(filename),'Nome de arquivo inválido.');const ext=filename.split('.').at(-1).toLowerCase();need(['txt','docx','pdf'].includes(ext),'Use TXT UTF-8, DOCX ou PDF com texto.');
 if(ext==='txt'){let value;try{value=decoder.decode(bytes);}catch{throw new Problem('TXT deve usar codificação UTF-8.');}return {format:'txt',blocks:blocksFrom(value),pages:null};}
 if(ext==='docx'){
  need(bytes[0]===80&&bytes[1]===75,'Assinatura DOCX inválida.');let xml;try{xml=unzipDocx(bytes);}catch(error){if(error instanceof Problem)throw error;throw new Problem('Não foi possível extrair o DOCX.');}
  need(!/<!\s*(?:DOCTYPE|ENTITY)/i.test(xml),'XML com DTD ou entidades não é aceito.');need(XMLValidator.validate(xml)===true,'XML DOCX inválido.');
  const parsed=new XMLParser({ignoreAttributes:true,removeNSPrefix:true,preserveOrder:true,processEntities:false,parseTagValue:false}).parse(xml);
  function walk(nodes){let out='';for(const node of nodes){for(const [key,value] of Object.entries(node)){if(key==='#text')out+=value;else if(Array.isArray(value)){out+=walk(value);if(key==='p')out+='\n\n';if(key==='tab')out+='\t';if(key==='br')out+='\n';}}}return out;}
  return {format:'docx',blocks:blocksFrom(walk(parsed)),pages:null};
 }
 need(new TextDecoder().decode(bytes.subarray(0,5))==='%PDF-','Assinatura PDF inválida.');let pdf;
 try{pdf=await getDocumentProxy(bytes.slice(),{isEvalSupported:false,disableFontFace:true,useSystemFonts:false,maxImageSize:0,stopAtErrors:true,useWorkerFetch:false,verbosity:0});need(pdf.numPages<=LIMITS.pages,'PDF excede 100 páginas.',413);const blocks=[];let count=0;
  for(let p=1;p<=pdf.numPages;p++){const page=await pdf.getPage(p);const content=await page.getTextContent();let out='';for(const item of content.items){if(typeof item.str==='string'){out+=item.str+(item.hasEOL?'\n':' ');count+=item.str.length+1;need(count<=LIMITS.text,'Texto PDF excessivo.',413);}}if(out.trim())blocks.push(...blocksFrom(out).map(text=>({text,page:p})));page.cleanup();}
  need(blocks.length,'PDF sem texto. OCR não está disponível.');return {format:'pdf',blocks,pages:pdf.numPages};
 }catch(error){if(error instanceof Problem)throw error;throw new Problem('Não foi possível extrair este PDF: pode estar protegido, corrompido ou exceder os recursos do piloto.');}finally{await pdf?.loadingTask?.destroy();}
}
