'use strict';
const catalogue=JSON.parse(document.getElementById('catalogue').textContent);
const $=id=>document.getElementById(id);
let current, mode='pair';
function node(tag,text,cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;}
function chooseMap(map){current=map;$('comparison').hidden=false;$('map-title').textContent=map.name;$('map-description').textContent=map.description;
  $('snapshot').replaceChildren(...map.snapshots.slice().reverse().map(s=>{const label=s.id.endsWith('-baseline')?'Baseline':s.id.endsWith('-vertex-paint')?'Recovered paint':s.id.endsWith('-area-survey')?'Area survey':s.id.endsWith('-scenery-fill')?'Scenery recovery':s.id.endsWith('-ui-atlas-survey')?'Expanded areas and UI fix':s.id.endsWith('-initial-ports')?'First native preview':s.id.endsWith('-source-features-lighting')?'Source features and lighting':s.id.endsWith('-water-fog-glow')?'Rejected colour candidate':s.id.endsWith('-water-fog-glow-final')?'Water, haze and glow':s.id;const o=node('option',label+' · v'+s.version);o.value=s.id;return o;}));
  $('snapshot').value=map.latest;$('notes').textContent=map.notes;$('install').textContent='Launch '+map.target_map+' in Northstar. Current local build: '+map.version+'.';
  $('modes').replaceChildren(...map.modes.map(m=>node('span',m)));$('download').replaceChildren();
  if(map.download){const url=new URL(map.download,location.href);if(['https:','http:'].includes(url.protocol)||url.origin===location.origin){const a=node('a','Download Northstar mod ↗');a.href=url.href;$('download').append(a);}}
  else $('download').textContent='Release download pending.';
  refreshShots();history.replaceState(null,'','#'+map.id);$('comparison').scrollIntoView({behavior:'smooth',block:'start'});
}
function snapshot(){return current.snapshots.find(s=>s.id===$('snapshot').value);}
function refreshShots(){const selected=$('shot').value;$('shot').replaceChildren(...snapshot().shots.map(s=>{const o=node('option',s.name.replaceAll('-',' '));o.value=s.name;return o;}));if(snapshot().shots.some(s=>s.name===selected))$('shot').value=selected;render();}
function render(){const s=snapshot().shots.find(s=>s.name===$('shot').value);for(const [id,key,label] of [['source','r5r','Original Apex'],['target','northstar','Titanfall 2 port']]){$(id).src=s[key].image;$(id).alt=label+' — '+current.name+', '+s.name.replaceAll('-',' ');}
  $('capture-note').textContent='Same camera, '+s.fov+'° FOV · '+s.r5r.width+' × '+s.r5r.height+' native captures. Lighting and HUDs differ between engines.';
  $('observations').hidden=!s.findings?.length;$('finding-list').replaceChildren(...(s.findings||[]).map(text=>node('li',text)));
  $('metadata').textContent=JSON.stringify({source:current.source_map,port:current.target_map,port_camera:s.origin,source_offset:current.source_offset,angles:s.angles,fov:s.fov,captures:{r5r:s.r5r,northstar:s.northstar}},null,2);blend();
}
function blend(){const n=Number($('blend').value);$('viewer').className='viewer '+mode;$('target-figure').style.opacity=mode==='overlay'?n/100:'';$('target-figure').style.clipPath=mode==='wipe'?'inset(0 0 0 '+n+'%)':'';$('blend-value').value=n+'%';$('blend-label').hidden=mode==='pair';$('blend-text').textContent=mode==='wipe'?'Comparison split':'Northstar opacity';}
$('count').textContent=catalogue.maps.length+' MAP PORTS';
for(const map of catalogue.maps){const card=node('article',undefined,'card'),image=node('img');image.src=map.snapshots.find(s=>s.id===map.latest).shots[0].northstar.image;image.alt=map.name+' in Titanfall 2';image.loading='lazy';const body=node('div',undefined,'card-body'),title=node('div',undefined,'card-title');title.append(node('h3',map.name),node('span',map.status,'badge'));body.append(title,node('p',map.description));const button=node('button');button.append(node('span','Explore & compare'),node('span','↗'));button.addEventListener('click',()=>chooseMap(map));body.append(button);card.append(image,body);$('cards').append(card);}
$('snapshot').addEventListener('change',refreshShots);$('shot').addEventListener('change',render);$('blend').addEventListener('input',blend);
document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{mode=button.dataset.mode;document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));blend();}));
const initial=catalogue.maps.find(m=>location.hash==='#'+m.id);if(initial)chooseMap(initial);
