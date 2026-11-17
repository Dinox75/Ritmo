"""Representative contrast and keyboard checks; not a full WCAG/usability audit."""
import argparse
import json
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from qa_packaged_windows import EDGE, launch, authorize, quit_and_verify


MEASURE = """() => {
 const color=s=>{const v=s.match(/[\\d.]+/g).map(Number);return [v[0],v[1],v[2],v.length>3?v[3]:1]};
 const dim=Number(getComputedStyle(document.documentElement).getPropertyValue('--ui-dim')||0);
 const lum=rgb=>rgb.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
 return [...document.querySelectorAll('#view-configuracoes label,#view-configuracoes .hint,#view-configuracoes h2,#view-configuracoes button:not(:disabled)')].filter(e=>e.getClientRects().length&&e.textContent.trim()).map(e=>{
  const style=getComputedStyle(e);let p=e,bg;
  while(p){bg=color(getComputedStyle(p).backgroundColor);if(bg[3]===1)break;p=p.parentElement;}
  if(!p)bg=[255,255,255,1];
  const fg=color(style.color);const a=fg[3];const text=fg.slice(0,3).map((v,i)=>(v*a+bg[i]*(1-a))*(1-dim));bg=bg.slice(0,3).map(v=>v*(1-dim));
  const l1=lum(text),l2=lum(bg);const ratio=(Math.max(l1,l2)+.05)/(Math.min(l1,l2)+.05);
  const large=parseFloat(style.fontSize)>=24||(parseFloat(style.fontSize)>=18.66&&parseInt(style.fontWeight)>=700);
  return {text:e.textContent.trim().slice(0,90),ratio,minimum:large?3:4.5};
 });
}"""


def run(exe,out):
    report={'representative_only':True,'learning_evidence':False,'cases':[]}
    with tempfile.TemporaryDirectory(prefix='ritmo-a11y-',ignore_cleanup_errors=True) as folder:
        root=Path(folder);data=root/'Ritmo';data.mkdir();(data/'.migration_disabled').write_text('1')
        config=json.loads((Path(__file__).resolve().parents[1]/'config/config.json').read_text(encoding='utf8'))
        config['tutor']['model_root']=str(root/'no-models');(data/'config.json').write_text(json.dumps(config),encoding='utf8')
        process=None
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=str(EDGE),headless=True)
            try:
                process,port=launch(exe,root);page=browser.new_page();authorize(page,process,port);page.goto(f'http://127.0.0.1:{port}')
                for theme in ('light','dark'):
                    for width in (390,1366,1920):
                        page.set_viewport_size({'width':width,'height':1000})
                        page.locator('nav a[data-view-target="configuracoes"]').click()
                        page.locator('#experience-theme').select_option(theme)
                        page.locator('#experience-brightness').focus();page.keyboard.press('Home')
                        page.locator('#experience-form button').click()
                        expect(page.locator('html')).to_have_attribute('data-theme',theme)
                        readings=page.evaluate(MEASURE)
                        failures=[r for r in readings if r['ratio']+.01<r['minimum']]
                        sequence=[];page.locator('#experience-theme').focus()
                        for _ in range(12):
                            page.keyboard.press('Tab')
                            item=page.evaluate("()=>{const e=document.activeElement,s=getComputedStyle(e);return {tag:e.tagName,id:e.id,outline:s.outlineStyle,width:parseFloat(s.outlineWidth)}}")
                            assert item['tag']!='BODY' and item['outline']!='none' and item['width']>0,item
                            sequence.append(item)
                        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                        page.screenshot(path=str(out/f'{theme}-{width}.png'),full_page=True)
                        report['cases'].append({'theme':theme,'width':width,'contrast':readings,'failures':failures,'keyboard':sequence})
                        assert not failures,failures
                quit_and_verify(page,process,port);process=None;report['port_released']=True
            finally:
                browser.close()
                if process is not None and process.poll() is None:process.terminate();process.wait(timeout=15)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('executable',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    r=run(a.executable.resolve(),a.output.resolve());(a.output/'qa.json').write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf8');print('Representative keyboard/focus/contrast checks passed in both themes and three widths.')
