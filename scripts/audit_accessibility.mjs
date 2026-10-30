// Fixed DOM audit evaluated in the isolated browser, never supplied by a model.
// This intentionally limited audit is not a WCAG conformance certification.
export function auditAccessibility() {
  const findings=[];
  const add=(rule,element)=>{if(findings.length<100)findings.push({rule,tag:element.tagName.toLowerCase(),id:element.id.slice(0,100)});};
  const visible=e=>Boolean(e.getClientRects().length)&&getComputedStyle(e).visibility!=='hidden';
  const name=e=>{
    const refs=(e.getAttribute('aria-labelledby')||'').split(/\s+/).filter(Boolean);
    if(refs.length)return refs.map(id=>document.getElementById(id)?.textContent||'').join(' ').trim();
    return (e.getAttribute('aria-label')||Array.from(e.labels||[]).map(l=>l.textContent).join(' ')||e.getAttribute('alt')||e.textContent||'').trim();
  };
  if(!document.documentElement.lang.trim())add('document-language',document.documentElement);
  if(!document.title.trim())add('document-title',document.documentElement);
  if(!document.querySelector('main,[role="main"]'))add('main-landmark',document.body);
  if(!Array.from(document.querySelectorAll('h1,[role="heading"][aria-level="1"]')).some(visible))add('level-one-heading',document.body);
  const seen=new Set();
  for(const element of document.querySelectorAll('[id]')){
    if(seen.has(element.id))add('duplicate-id',element);
    seen.add(element.id);
  }
  for(const element of document.querySelectorAll('input,select,textarea,button,a[href],[role="button"],[role="checkbox"]')){
    if(!visible(element)||element.matches('input[type="hidden"]'))continue;
    const inputButton=element.matches('input[type="submit"],input[type="button"],input[type="reset"]');
    if(!(inputButton?element.value.trim():name(element)))add('control-accessible-name',element);
    if(Number(element.getAttribute('tabindex'))>0)add('positive-tabindex',element);
    if(element.matches('[role="button"],[role="checkbox"]')&&!element.matches('button,input,a[href]')&&!element.hasAttribute('tabindex'))add('custom-control-keyboard-focus',element);
  }
  for(const element of document.querySelectorAll('img'))if(visible(element)&&!element.hasAttribute('alt'))add('image-alt',element);
  return {passed:findings.length===0,findings,scope:'Basic structural/name/focus rules only; contrast, screen-reader behavior and full WCAG conformance are not audited'};
}
