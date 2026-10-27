"""生成本地人工标注页面；只嵌入空模板及原图file引用，绝不嵌入模型预测点。"""
import json


def page(template):
    payload = json.dumps(template, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    return HTML.replace('__TEMPLATE__', payload)


HTML = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>固定120人物：人工COCO17盲标与独立复核</title>
<style>body{font:15px system-ui;margin:20px;color:#18242b;background:#f6f7f8}button,select,input{font:inherit;margin:4px;padding:6px}
main{display:grid;grid-template-columns:minmax(400px,960px) minmax(300px,460px);gap:18px}canvas{display:block;width:900px;max-width:100%;height:auto;background:#222;cursor:crosshair}
section{padding:12px;background:white;border:1px solid #ccd4d8;border-radius:8px}.joint{display:flex;align-items:center;gap:5px;border-bottom:1px solid #ddd;padding:4px}.active{background:#e2f2ff}.joint span{min-width:115px}
small{color:#52626b}#message{white-space:pre-wrap;color:#873b00}h1{font-size:22px}.warn{background:#fff1d6;padding:12px}button.current{background:#c4e6ff}</style>
<h1>固定120人物：人工COCO17盲标与独立复核</h1>
<p class="warn">本页面无模型预测点、无模型预填。左右按人物自身方向；看不清请标不可判定并保留原因，不删难例。图外指完整原图，不是ROI外。请先读同目录INSTRUCTIONS.md。JSON/点击日志不能证明真人身份或独立性；实际来源须由root核验。本工具不计算PCK、OKS或准确率。</p>
<div><button id="prev">上一样本</button><button id="next">下一样本</button><b id="progress"></b>
<button id="view">显示完整原图</button><button id="save">导出当前JSON</button><label>继续已有记录 <input id="load" type="file" accept="application/json"></label></div>
<main><section><div id="source"></div><canvas id="board"></canvas><p><small>点击图像设置当前点，坐标始终保存为完整原图像素。ROI仅为原选框的放大上下文。没有自动保存，离开前请导出JSON。</small></p>
<p id="message"></p></section><section>
<div><label>模式 <select id="mode"><option value="annotate">人工标注</option><option value="review">另一人独立复核</option></select></label></div>
<label>当前操作人ID <input id="actor" placeholder="填写真实标注/复核人员标识"></label>
<div><label>目标判断 <select id="target"><option value="pending">尚未判断</option><option value="person_confirmed">可确认的人体</option><option value="not_a_person">不是人体</option><option value="target_ambiguous">目标无法确认</option></select></label></div>
<div><label>点击后的点状态 <select id="pointmode"><option value="visible">可见、可定位 v2</option><option value="occluded_localizable">遮挡但可定位 v1</option></select></label></div>
<div><label>不可判定原因 <select id="reason"><option value="">请选择原因</option><option value="too_small">过小</option><option value="blur">模糊</option><option value="occluded_not_localizable">遮挡且不可定位</option><option value="landmark_ambiguous">部位无法确定</option><option value="other">其他（须备注）</option></select></label></div>
<div id="joints"></div>
<p><label><input id="claim" type="checkbox">本人为人工操作；未查看模型关键点或拷贝预测。复核时还声明独立于原标注人。</label></p>
<button id="submit">提交当前人工标注</button><button id="reviewsubmit">提交当前独立复核</button>
<p><small>复核需不同ID、逐点接受或要求修订；没有“一键接受全部”。改点会重置旧审核。</small></p>
</section></main>
<script id="seed" type="application/json">__TEMPLATE__</script><script>
'use strict';let data=JSON.parse(document.getElementById('seed').textContent),index=0,joint=0,full=false,img=new Image(),view=[0,0,1,1];
const $=id=>document.getElementById(id),names=['鼻','左眼','右眼','左耳','右耳','左肩','右肩','左肘','右肘','左腕','右腕','左髋','右髋','左膝','右膝','左踝','右踝'];
const now=()=>new Date().toISOString(),sample=()=>data.samples[index],clone=x=>JSON.parse(JSON.stringify(x));
function actor(){let id=$('actor').value.trim();if(!id)throw Error('请先填写真实操作人ID');return id;}
function event(kind,extra={}){let e={event_id:data.interaction_log.length+1,sample_id:sample().sample_id,actor_id:actor(),time_utc:now(),kind,image_displayed:img.complete&&img.naturalWidth>0,image_natural_wh:[img.naturalWidth,img.naturalHeight],...extra};data.interaction_log.push(e);return e;}
function warn(e){$('message').textContent=String(e.message||e);}
function imageReady(){let wh=sample().source.image_wh;if(!img.complete||img.naturalWidth!==wh[0]||img.naturalHeight!==wh[1])throw Error('请先确认正确原图已完整载入，不可在空画面标注或复核');}
function blankReview(){return {status:'pending',reviewer_id:'',declared_human:false,independent_of_annotator:null,model_predictions_viewed:null,prediction_copy:null,reviewed_at_utc:null,annotation_digest:null,points_checked:[]};}
function edit(){imageReady();let s=sample(),a=s.annotation,id=actor();if(a.annotator_id&&a.annotator_id!==id)throw Error('继续标注须原标注人；另一人请使用独立复核模式');a.annotator_id=id;a.started_at_utc=a.started_at_utc||now();a.submitted_at_utc=null;a.status='in_progress';s.review=blankReview();data.claimed_complete=false;}
function setJoint(j,p,kind){edit();sample().joints[j]=p;event(kind,{joint_id:j,joint:clone(p),input_method:kind==='set_point'?'pointer':'status_selection'});renderJoints();draw();}
function unknown(j,outside){try{if($('mode').value!=='annotate')throw Error('复核模式不直接改标注；要求原标注人修订');let reason=outside?'outside_full_image':$('reason').value,note='';
if(!reason)throw Error('请先明确选择不可判定原因');if(reason==='other'){note=prompt('请描述不可判定原因')||'';if(!note.trim())throw Error('其他原因必须有备注');}
let p={...sample().joints[j],status:outside?'out_of_frame':'unjudgeable',xy_image_px:null,coco_v:0,reason,note};setJoint(j,p,'set_status');}catch(e){warn(e);}}
function reviewPoint(j,decision){try{imageReady();if($('mode').value!=='review'||sample().annotation.status!=='submitted')throw Error('只有已提交人工标注才能独立复核');if(actor().toLowerCase()===sample().annotation.annotator_id.toLowerCase())throw Error('复核人须不同于标注人');let r=sample().review;r.reviewer_id=actor();r.status='pending';r.points_checked=r.points_checked.filter(p=>p.joint_id!==j);r.points_checked.push({joint_id:j,decision});event('review_decision',{joint_id:j,decision,joint:clone(sample().joints[j]),annotation_submitted_at_utc:sample().annotation.submitted_at_utc});renderJoints();}catch(e){warn(e);}}
function renderJoints(){let box=$('joints');box.textContent='';sample().joints.forEach((p,j)=>{let row=document.createElement('div');row.className='joint'+(j===joint?' active':'');let select=document.createElement('button');select.textContent=(j+1)+'. '+names[j];select.onclick=()=>{joint=j;renderJoints();draw();};row.append(select);let state=document.createElement('span');state.textContent=p.status+(p.xy_image_px?' '+p.xy_image_px.map(x=>x.toFixed(1)).join(','):'');row.append(state);
let actions=$('mode').value==='review'?[['接受',()=>reviewPoint(j,'accepted')],['需修订',()=>reviewPoint(j,'needs_revision')]]:[['不可判定',()=>unknown(j,false)],['图外',()=>unknown(j,true)]];for(let [label,fn]of actions){let b=document.createElement('button');b.textContent=label;b.onclick=fn;row.append(b);}let decision=sample().review.points_checked.find(x=>x.joint_id===j);if(decision){let v=document.createElement('small');v.textContent=decision.decision;row.append(v);}box.append(row);});}
function draw(){if(!img.complete||!img.naturalWidth)return;let s=sample(),[w,h]=s.source.image_wh,[x,y,bw,bh]=s.source.roi_bbox_xywh_px;
view=full?[0,0,w,h]:[Math.max(0,x-bw*.6),Math.max(0,y-bh*.4),Math.min(w,x+bw*1.6)-Math.max(0,x-bw*.6),Math.min(h,y+bh*1.4)-Math.max(0,y-bh*.4)];
let c=$('board');c.width=Math.max(1,Math.ceil(view[2]));c.height=Math.max(1,Math.ceil(view[3]));let ctx=c.getContext('2d');ctx.drawImage(img,...view,0,0,c.width,c.height);ctx.strokeStyle='#ffb300';ctx.lineWidth=Math.max(1,c.width/400);ctx.strokeRect((x-view[0])/view[2]*c.width,(y-view[1])/view[3]*c.height,bw/view[2]*c.width,bh/view[3]*c.height);
for(let p of s.joints){if(!p.xy_image_px)continue;let [a,b]=p.xy_image_px;ctx.fillStyle=p.joint_id===joint?'#ff0033':'#00e5ff';ctx.beginPath();ctx.arc((a-view[0])/view[2]*c.width,(b-view[1])/view[3]*c.height,Math.max(1.5,c.width/180),0,7);ctx.fill();}}
function render(){let s=sample();$('message').textContent='';$('claim').checked=false;$('target').value=s.target_state;$('progress').textContent=`${index+1}/120 · 已提交${data.samples.filter(s=>s.annotation.status==='submitted').length} · 独立复核${data.samples.filter(s=>s.review.status==='reviewed').length}`;$('source').textContent=`${s.source.sequence} / 原帧${s.source.frame_number} · ${s.source.image_wh.join('×')} · ${s.annotation.status} / ${s.review.status}`;renderJoints();img=new Image();img.onload=()=>{if(img.naturalWidth!==s.source.image_wh[0]||img.naturalHeight!==s.source.image_wh[1])return warn(Error('原图尺寸与冻结元数据不一致，停止标注'));draw();};img.onerror=()=>warn(Error('原图引用打不开；禁止换图/跳样，交给root核查文件路径。'));img.src=s.source.image_file_url;}
$('board').addEventListener('click',e=>{try{if($('mode').value!=='annotate')throw Error('独立复核模式请逐点接受或要求修订');if(sample().target_state!=='person_confirmed')throw Error('先判断目标是否为可确认人体');let r=$('board').getBoundingClientRect(),xy=[view[0]+(e.clientX-r.left)/r.width*view[2],view[1]+(e.clientY-r.top)/r.height*view[3]].map(v=>Math.round(v*1000)/1000),[w,h]=sample().source.image_wh;if(xy[0]<0||xy[0]>=w||xy[1]<0||xy[1]>=h)throw Error('点击超出完整原图');let status=$('pointmode').value,p={...sample().joints[joint],status,xy_image_px:xy,coco_v:status==='visible'?2:1,reason:'',note:''};setJoint(joint,p,'set_point');}catch(e){warn(e);}});
$('target').onchange=()=>{try{if($('mode').value!=='annotate')throw Error('复核模式不改目标判断');edit();let s=sample();s.target_state=$('target').value;event('set_target',{target_state:s.target_state});if(['not_a_person','target_ambiguous'].includes(s.target_state)){s.joints.forEach((p,j)=>{s.joints[j]={...p,status:'unjudgeable',xy_image_px:null,coco_v:0,reason:s.target_state,note:''};event('set_status',{joint_id:j,joint:clone(s.joints[j]),input_method:'status_selection'});});}renderJoints();draw();}catch(e){warn(e);$('target').value=sample().target_state;}};
$('claim').onchange=()=>{try{if(!$('claim').checked)return;let declaration={declared_human:true,model_predictions_viewed:false,prediction_copy:false};if($('mode').value==='review'){declaration.independent_of_annotator=true;Object.assign(sample().review,declaration,{reviewer_id:actor()});event('review_declaration',{declaration});}else{edit();Object.assign(sample().annotation,declaration);event('annotator_declaration',{declaration});}}catch(e){warn(e);$('claim').checked=false;}};
$('submit').onclick=()=>{try{let s=sample();if($('mode').value!=='annotate'||!$('claim').checked||s.annotation.annotator_id!==actor())throw Error('请由标注人完成明确人工/盲标声明');if(s.target_state==='pending'||s.joints.some(p=>p.status==='pending'))throw Error('须保留并处理全部17点；不清楚请标不可判定');s.annotation.status='submitted';let e=event('submit_annotation');s.annotation.submitted_at_utc=e.time_utc;render();}catch(e){warn(e);}};
function stable(v){if(Array.isArray(v))return v.map(stable);if(v&&typeof v==='object')return Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])]));return v;}
async function annotationDigest(s){if(!crypto.subtle)throw Error('浏览器缺WebCrypto，保持pending，不可伪造审核摘要');let v={};for(let k of ['sample_id','source','target_state','joints','annotation'])v[k]=s[k];let bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(stable(v))));return [...new Uint8Array(bytes)].map(x=>x.toString(16).padStart(2,'0')).join('');}
$('reviewsubmit').onclick=async()=>{try{let s=sample(),r=s.review;if($('mode').value!=='review'||!$('claim').checked||s.annotation.status!=='submitted'||actor()===s.annotation.annotator_id)throw Error('需另一真实人员独立复核并声明');if(r.points_checked.length!==17)throw Error('17点全部须分别复核，不能只填审核字段');if(r.points_checked.some(p=>p.decision!=='accepted')){r.status='needs_revision';render();return;}r.reviewer_id=actor();r.annotation_digest=await annotationDigest(s);let e=event('submit_review',{annotation_digest:r.annotation_digest});r.reviewed_at_utc=e.time_utc;r.status='reviewed';render();}catch(e){warn(e);}};
$('prev').onclick=()=>{index=Math.max(0,index-1);joint=0;render();};$('next').onclick=()=>{index=Math.min(119,index+1);joint=0;render();};$('view').onclick=()=>{full=!full;$('view').textContent=full?'显示ROI上下文':'显示完整原图';draw();};$('mode').onchange=()=>render();
$('save').onclick=()=>{data.claimed_complete=data.samples.every(s=>s.annotation.status==='submitted'&&s.review.status==='reviewed');let blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='pose_manual_quality_annotations.json';a.click();URL.revokeObjectURL(a.href);};
$('load').onchange=async e=>{try{let x=JSON.parse(await e.target.files[0].text());if(x.schema!==data.schema||x.source_manifest_sha256!==data.source_manifest_sha256||x.samples.length!==120||x.samples.some((s,i)=>s.sample_id!==data.samples[i].sample_id))throw Error('记录不是当前固定120范围；不能混入其他样本');data=x;index=0;render();}catch(e){warn(e);}};
window.addEventListener('beforeunload',e=>{e.preventDefault();e.returnValue='离开前请导出人工记录JSON';});render();
</script></html>'''
