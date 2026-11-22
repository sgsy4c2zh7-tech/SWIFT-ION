/** Standalone minimal XLSX writer. No CDN, no external libraries. No XLS macros.
 * Input: [{name,rows:[[string|number|null,...],...]},...].
 * Numeric values are stored as numbers; all other values as inline strings.
 */
const utf=s=>new TextEncoder().encode(s);
const escapeXml=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&apos;');
function ref(col,row){let x=col+1,s='';while(x){x--;s=String.fromCharCode(65+x%26)+s;x=Math.floor(x/26)}return s+row}
export function sheetXml(rows){
 const body=rows.map((row,ri)=>{
  const cells=row.map((v,ci)=>{
   if(v===null||v===undefined||v==='')return '';
   const r=ref(ci,ri+1),style=ri===0?' s="1"':'';
   if(typeof v==='number'&&Number.isFinite(v))return `<c r="${r}"${style}><v>${v}</v></c>`;
   return `<c r="${r}" t="inlineStr"${style}><is><t xml:space="preserve">${escapeXml(v)}</t></is></c>`;
  }).join('');
  return `<row r="${ri+1}">${cells}</row>`;
 }).join('');
 const maxCol=Math.max(1,...rows.map(x=>x.length));
 return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:${ref(maxCol-1,Math.max(1,rows.length))}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetFormatPr defaultRowHeight="17"/><cols><col min="1" max="1" width="27" customWidth="1"/><col min="2" max="32" width="19" customWidth="1"/></cols><sheetData>${body}</sheetData></worksheet>`;
}
function crc32(bytes){let crc=0xffffffff;for(const b of bytes){crc^=b;for(let i=0;i<8;i++)crc=(crc>>>1)^((crc&1)?0xedb88320:0)}return (crc^0xffffffff)>>>0}
const u16=(v)=>[v&255,(v>>>8)&255],u32=(v)=>[v&255,(v>>>8)&255,(v>>>16)&255,(v>>>24)&255];
function zipStore(entries){const chunks=[],dirs=[];let offset=0;
 for(const [filename,content] of entries){const name=utf(filename),data=utf(content),checksum=crc32(data);const local=new Uint8Array([
 ...u32(0x04034b50),...u16(20),...u16(0x800),...u16(0),...u16(0),...u16(0),...u32(checksum),...u32(data.length),...u32(data.length),...u16(name.length),...u16(0),...name]);
 chunks.push(local,data);dirs.push({name,checksum,size:data.length,offset});offset+=local.length+data.length;}
 const start=offset;
 for(const d of dirs){const central=new Uint8Array([...u32(0x02014b50),...u16(20),...u16(20),...u16(0x800),...u16(0),...u16(0),...u16(0),...u32(d.checksum),...u32(d.size),...u32(d.size),...u16(d.name.length),...u16(0),...u16(0),...u16(0),...u16(0),...u32(0),...u32(d.offset),...d.name]);chunks.push(central);offset+=central.length;}
 const end=new Uint8Array([...u32(0x06054b50),...u16(0),...u16(0),...u16(dirs.length),...u16(dirs.length),...u32(offset-start),...u32(start),...u16(0)]);chunks.push(end);
 return new Blob(chunks,{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
}
function sanitize(name){return String(name||'Sheet').replace(/[\\/?*\[\]:]/g,'_').slice(0,31)}
export function workbookBlob(sheets){if(!Array.isArray(sheets)||!sheets.length)throw Error('At least one sheet required');
 const safe=sheets.map((s,i)=>({...s,name:sanitize(s.name||`Sheet${i+1}`)}));
 const names=new Set();for(const s of safe){if(names.has(s.name))throw Error('Duplicate Excel sheet: '+s.name);names.add(s.name)}
 const overrides=safe.map((s,i)=>`<Override PartName="/xl/worksheets/sheet${i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('');
 const files=[
 ['[Content_Types].xml',`<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>${overrides}</Types>`],
 ['_rels/.rels',`<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`],
 ['xl/workbook.xml',`<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${safe.map((s,i)=>`<sheet name="${escapeXml(s.name)}" sheetId="${i+1}" r:id="rId${i+1}"/>`).join('')}</sheets></workbook>`],
 ['xl/_rels/workbook.xml.rels',`<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${safe.map((s,i)=>`<Relationship Id="rId${i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i+1}.xml"/>`).join('')}<Relationship Id="rId${safe.length+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`],
 ['xl/styles.xml','<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Aptos"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Aptos"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF123751"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs></styleSheet>']
 ];safe.forEach((s,i)=>files.push([`xl/worksheets/sheet${i+1}.xml`,sheetXml(s.rows||[])]));return zipStore(files);
}
export function downloadWorkbook(filename,sheets){const blob=workbookBlob(sheets),url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000)}
