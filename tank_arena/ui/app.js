'use strict';
const $ = id => document.getElementById(id);
const canvas = $('board'), ctx = canvas.getContext('2d');
let live = null, replay = null, replayIndex = 0, lastRevision = -1, fxTime = 0, lastTurnKey = '', selected = 1;
const txt = (id, value) => { $(id).textContent = value; };
function toast(message) { txt('toast',message); $('toast').style.display='block'; clearTimeout(toast.timer); toast.timer=setTimeout(()=>{$('toast').style.display='none';},5000); }
async function control(action, extra={}) {
  try { const r=await fetch('/api/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...extra})});const data=await r.json();if(!r.ok)throw Error(data.error);replay=null;await poll(); } catch(e){toast(e.message);}
}
function start(mode, stage=1) { selected=stage; control('start',{mode,stage,seed:Number($('seed').value)||0}); }
$('exam').onclick=()=>start('exam');
$('retry').onclick=()=>start(live?.run.mode||'practice',selected);
$('pause').onclick=()=>control('pause');$('step').onclick=()=>control('step');
$('speed').onchange=()=>control('speed',{speed:Number($('speed').value)});
$('send').onclick=()=>control('command',{command:$('command').value});
$('command').onkeydown=e=>{if(e.key==='Enter')$('send').click();};
$('help').onclick=()=>$('help-dialog').showModal();$('close-help').onclick=()=>$('help-dialog').close();
$('live').onclick=()=>{replay=null;render();};
$('export').onclick=async()=>{const data=replay||await(await fetch('/api/replay')).json();const a=document.createElement('a');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.href=url;a.download='tank-arena-replay.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('replay-file').onchange=async e=>{try{const data=JSON.parse(await e.target.files[0].text());if(data.format!=='tank-arena-replay-v1'||!Array.isArray(data.history)||!data.history.length||data.history.length>200000)throw Error('지원하지 않는 리플레이');for(const h of data.history){if(!h.state||!Array.isArray(h.state.grid)||h.state.grid.length>64||!h.state.grid.length||h.state.grid.some(r=>!Array.isArray(r)||r.length>64)||!h.state.units?.M)throw Error('잘못된 리플레이 상태');}replay=data;replayIndex=0;$('replay-slider').max=data.history.length-1;$('replay-slider').value=0;render();}catch(e){toast(e.message);}};
$('replay-slider').oninput=e=>{replayIndex=Number(e.target.value);render();};
function buildStages(stages) { $('stage-list').replaceChildren();for(const s of stages){const b=document.createElement('button');b.className='stage-button';b.dataset.stage=s.stage;b.disabled=s.available===false;const n=document.createElement('span');n.className='stage-number';n.textContent=String(s.stage).padStart(2,'0');const name=document.createElement('span');name.className='stage-title';name.textContent=s.name;const skill=document.createElement('span');skill.className='stage-skill';skill.textContent=s.skill;name.append(skill);b.append(n,name);b.onclick=()=>start('practice',s.stage);$('stage-list').append(b);} }
function render() {
 if(!live)return;
 const run=replay?replay.summary:live.run, entry=replay?replay.history[replayIndex]:null, state=entry?entry.state:live.state;
 const stage=entry?entry.stage:run.stage, attempt=entry?entry.attempt:run.attempt;
 txt('profile-note',run.profile==='private'?'개인 PC 전용 참조 프로필 · 정적 분석에 근거하며 원본 전체 실기 동일성은 미검증입니다.':'독립 창작 맵에서 연습하는 로컬 평가 시뮬레이터 · 공식 맵 및 점수와의 동일성은 미검증입니다.');txt('sand-legend',`모래 −${state.rules.sand_damage}HP`);
 selected=stage;
 for(const b of $('stage-list').children)b.classList.toggle('active',Number(b.dataset.stage)===stage);
 txt('mode-label',`${replay?'REPLAY':run.mode.toUpperCase()} / ${run.profile==='private'?'PRIVATE LOCAL REFERENCE':'ORIGINAL PRACTICE MAPS'}`);
 txt('stage-name',`Stage ${stage} · ${(replay?replay.scenarios:live.stages)[stage-1]?.name||''}`);
 const status=replay?'리플레이':run.finished?(run.failure?'Fail':'Success'):live.connected?(live.paused?'Paused':'진행 중'):'연결 대기';
 txt('status',status);$('status').classList.toggle('fail',!!run.failure);
 $('attempt-track').replaceChildren();for(let i=0;i<(run.mode==='exam'?12:1);i++){const bar=document.createElement('i');if(i<run.completed_attempts)bar.className='done';if(i===run.completed_attempts&&!run.finished)bar.className='current';if(run.failure&&i===run.completed_attempts-1)bar.className='failed';bar.title=`Stage ${Math.floor(i/2)+1} / ${i%2+1}차`;$('attempt-track').append(bar);}
 const me=state.units.M;txt('turn',`${state.turn} / ${state.rules.max_turns}`);txt('hp',me.hp);txt('normal',me.normal);txt('mega',me.mega);txt('direction',me.direction);
 txt('dimensions',`${state.grid.length} × ${state.grid[0].length} / ATTEMPT ${attempt}`);
 txt('profile-label',run.profile==='private'?'PRIVATE LOCAL PROFILE':'PRACTICE RULES · UNVERIFIED PARITY');
 txt('bot-command',`python examples/bot_exam_general.py${live.tcp_port===8747?'':` --port ${live.tcp_port}`}`);txt('endpoint',`TCP 127.0.0.1:${live.tcp_port}`);
 txt('connection-title',live.connected?'Python 클라이언트 연결됨':run.finished?'실행 결과를 확인하세요':'Python 봇을 연결하세요');txt('nickname',run.nickname||'Waiting for a player…');txt('connections',`${run.connections} connection`);
 txt('total',run.total_stars);txt('max-stars',run.mode==='exam'?'/ 18 STARS':'/ 3 STARS');txt('run-result',run.finished?(run.failure?'FAIL':'COMPLETE'):live.connected?'RUNNING':'READY');
 $('scores').replaceChildren();for(const row of run.scores){const tr=document.createElement('tr');const vals=[String(row.stage).padStart(2,'0'),...Array.from({length:2},(_,i)=>{const a=row.attempts[i];return a?`${a.stars}★ · ${a.turns}T`:'—';}),row.provisional?'대기':row.attempts.length?`${row.stars}★`:'—'];for(const v of vals){const td=document.createElement('td');td.textContent=v;tr.append(td);}$('scores').append(tr);}
 txt('result-detail',run.failure?`Stage ${run.stage} / ${run.attempt}차 종료: ${run.failure}`:run.finished?`${run.completed_attempts}회 완료 · seed ${run.seed} · ${run.total_stars}★`:`seed ${run.seed} · ${run.completed_attempts}/ ${run.mode==='exam'?12:1}회 완료`);
 txt('replay-path',replay?'로컬 리플레이 파일을 보고 있습니다.':live.replay_path);
 txt('raw',entry?.raw||entry?.input||live.raw);txt('events',JSON.stringify(state.events,null,2));
 txt('logs',live.logs.slice(-12).map(x=>`[${x.kind}] ${x.message}`).join('\n'));
 const timeline=replay?replay.history.slice(Math.max(0,replayIndex-10),replayIndex+1).filter(x=>x.type==='turn').map(x=>({...x,events:x.state.events})):live.timeline.slice(-8);
 $('timeline').replaceChildren();for(const t of [...timeline].reverse()){const div=document.createElement('div');div.className='timeline-entry';const n=document.createElement('span');n.textContent=`S${t.stage}.${t.attempt} T${t.turn}`;const command=document.createElement('code');command.textContent=t.command;const event=document.createElement('span');event.textContent=t.events.map(e=>e.kind).join(' / ');div.append(n,command,event);$('timeline').append(div);}
 txt('last-command',`COMMAND ${entry?.command||timeline.at(-1)?.command||'—'}`);
 const disabled=live.run.mode==='exam'||!!replay;
 for(const id of ['pause','step','speed'])$(id).disabled=disabled||live.run.finished;
 for(const id of ['send','command'])$(id).disabled=disabled||live.connected||live.run.finished;
 txt('pause',live.paused?'▶ Resume':'Ⅱ Pause');
 $('replay-slider').disabled=!replay;txt('replay-caption',replay?`${replayIndex+1}/${replay.history.length} · S${stage}.${attempt} T${state.turn}`:'');
 const turnKey=`${stage}:${attempt}:${state.turn}:${run.seed}:${replayIndex}`;if(turnKey!==lastTurnKey){lastTurnKey=turnKey;fxTime=performance.now();}
 draw(state,performance.now());
}
function draw(s, now) {
 const W=canvas.width,H=canvas.height,rows=s.grid.length,cols=s.grid[0].length;
 const tile=Math.min((W-90)/cols,(H-70)/rows),ox=(W-cols*tile)/2,oy=(H-rows*tile)/2;
 ctx.clearRect(0,0,W,H);ctx.fillStyle='#0b1420';ctx.fillRect(0,0,W,H);
 ctx.font='12px Consolas';ctx.textAlign='center';ctx.fillStyle='#586f84';for(let c=0;c<cols;c++)ctx.fillText(String(c),ox+(c+.5)*tile,oy-13);
 for(let r=0;r<rows;r++){ctx.fillStyle='#586f84';ctx.fillText(String(r),ox-20,oy+(r+.58)*tile);for(let c=0;c<cols;c++){
 const t=s.terrain[r][c],x=ox+c*tile,y=oy+r*tile,p=tile*.13;
 ctx.fillStyle={G:'#233d37',S:'#ad9562',W:'#21516d',R:'#283748',T:'#233d37',F:'#1e354b'}[t]||'#233d37';ctx.fillRect(x+1,y+1,tile-2,tile-2);
 if(t==='G'){ctx.fillStyle='#365348';ctx.fillRect(x+tile*.21,y+tile*.67,2,2);ctx.fillRect(x+tile*.74,y+tile*.25,2,2);}
 if(t==='S'){ctx.fillStyle='#6c5c3b';for(let i=0;i<5;i++)ctx.fillRect(x+((i*17+9)%38)/45*tile,y+((i*11+6)%38)/45*tile,2,2);}
 if(t==='W'){ctx.strokeStyle='#4383a3';ctx.lineWidth=1.5;for(let i=1;i<4;i++){ctx.beginPath();ctx.moveTo(x+p,y+tile*i/4);ctx.lineTo(x+tile-p,y+tile*i/4);ctx.stroke();}}
 if(t==='R'){ctx.fillStyle='#657786';ctx.beginPath();ctx.moveTo(x+p,y+tile*.3);ctx.lineTo(x+tile*.55,y+p);ctx.lineTo(x+tile-p,y+tile*.4);ctx.lineTo(x+tile*.8,y+tile-p);ctx.lineTo(x+tile*.2,y+tile*.8);ctx.closePath();ctx.fill();ctx.strokeStyle='#81939d';ctx.stroke();}
 if(t==='T'){ctx.fillStyle='#152d29';ctx.fillRect(x+tile*.45,y+tile*.5,tile*.13,tile*.4);for(let k=2;k>=0;k--){ctx.fillStyle=['#63a97f','#438a64','#2d6b50'][k];ctx.beginPath();ctx.moveTo(x+tile*.5,y+tile*(.12+k*.15));ctx.lineTo(x+tile*(.17-k*.025),y+tile*(.5+k*.13));ctx.lineTo(x+tile*(.83+k*.025),y+tile*(.5+k*.13));ctx.closePath();ctx.fill();}}
 if(t==='F'){ctx.fillStyle='#466b9b';ctx.fillRect(x+p,y+p,tile-2*p,tile-2*p);ctx.strokeStyle='#9cc8ff';ctx.lineWidth=tile*.07;ctx.strokeRect(x+tile*.3,y+tile*.3,tile*.4,tile*.4);ctx.beginPath();ctx.moveTo(x+tile*.5,y+tile*.2);ctx.lineTo(x+tile*.5,y+tile*.8);ctx.moveTo(x+tile*.2,y+tile*.5);ctx.lineTo(x+tile*.8,y+tile*.5);ctx.stroke();}
 }}
 for(const u of Object.values(s.units)){if(u.hp<=0)continue;const movement=u.symbol==='M'?(s.events||[]).find(e=>e.kind==='move'):null;const progress=Math.min(1,Math.max(0,(now-fxTime)/220));const visualRow=movement?movement.origin[0]+(u.row-movement.origin[0])*progress:u.row,visualCol=movement?movement.origin[1]+(u.col-movement.origin[1])*progress:u.col;const x=ox+(visualCol+.5)*tile,y=oy+(visualRow+.5)*tile,isMe=u.symbol==='M',enemy=u.symbol.startsWith('E')||u.symbol==='X',color=enemy?'#f28b91':isMe?'#75e9c0':'#82aff5';ctx.save();ctx.translate(x,y);if(u.symbol==='X'||u.symbol==='H'){ctx.fillStyle=enemy?'#733d4b':'#375875';ctx.fillRect(-tile*.36,-tile*.36,tile*.72,tile*.72);ctx.strokeStyle=color;ctx.lineWidth=2;ctx.strokeRect(-tile*.3,-tile*.3,tile*.6,tile*.6);ctx.fillStyle=color;ctx.beginPath();ctx.arc(0,0,tile*.15,0,Math.PI*2);ctx.fill();ctx.fillRect(-tile*.04,-tile*.35,tile*.08,tile*.35);}else{ctx.rotate({U:0,R:Math.PI/2,D:Math.PI,L:-Math.PI/2}[u.direction]||0);ctx.fillStyle='#101a22';ctx.fillRect(-tile*.33,-tile*.3,tile*.14,tile*.62);ctx.fillRect(tile*.19,-tile*.3,tile*.14,tile*.62);ctx.fillStyle=color;ctx.fillRect(-tile*.21,-tile*.28,tile*.42,tile*.55);ctx.fillStyle=enemy?'#72373d':'#215848';ctx.beginPath();ctx.arc(0,0,tile*.14,0,Math.PI*2);ctx.fill();ctx.fillStyle=color;ctx.fillRect(-tile*.05,-tile*.46,tile*.1,tile*.45);}ctx.restore();ctx.font=`bold ${Math.max(9,tile*.17)}px Consolas`;ctx.fillStyle='#f0f5fc';ctx.fillText(u.symbol,x,y+tile*.43);if(isMe){ctx.strokeStyle='#6ce4c070';ctx.lineWidth=1;ctx.strokeRect(x-tile*.47,y-tile*.47,tile*.94,tile*.94);}}
 const age=(now-fxTime)/650;
 if(age>=0&&age<1){for(const e of s.events||[]){if(e.kind==='shot'&&e.path.length){const end=e.path[Math.min(e.path.length-1,Math.floor(age*e.path.length*1.5))];ctx.strokeStyle=e.ammo==='mega'?'#ffa77a':'#fff3b2';ctx.lineWidth=4;ctx.globalAlpha=1-age;ctx.beginPath();ctx.moveTo(ox+(e.origin[1]+.5)*tile,oy+(e.origin[0]+.5)*tile);ctx.lineTo(ox+(end[1]+.5)*tile,oy+(end[0]+.5)*tile);ctx.stroke();ctx.globalAlpha=1;}if((e.kind==='destroy'||e.kind==='tree_destroy')&&e.position){ctx.globalAlpha=1-age;ctx.fillStyle='#ffb25b';ctx.beginPath();ctx.arc(ox+(e.position[1]+.5)*tile,oy+(e.position[0]+.5)*tile,tile*(.1+age*.65),0,Math.PI*2);ctx.fill();ctx.globalAlpha=1;}}}
}
async function poll(){try{const r=await fetch('/api/state');if(!r.ok)throw Error('서버 응답 오류');const data=await r.json();if(!live)buildStages(data.stages);live=data;if(data.revision!==lastRevision){lastRevision=data.revision;render();}}catch(e){toast('로컬 서버 연결을 확인하세요: '+e.message);}}
function animate(now){if(live){const s=replay?replay.history[replayIndex].state:live.state;draw(s,now);}requestAnimationFrame(animate);}
poll();setInterval(poll,200);requestAnimationFrame(animate);
