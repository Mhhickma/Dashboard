// One explicit click schedules one retailer post; nothing schedules on page load.
(function () {
  var main=document.querySelector('main');
  if(!main)return;
  var base='http://127.0.0.1:8766';
  var panel=document.createElement('section');panel.className='engagement-posts';
  var title=document.createElement('h2');title.textContent='Home Depot & Lowe’s Daily Post';
  var info=document.createElement('p');info.textContent='Post now schedules matching colored-background posts to the woodworking group and Woodworking Deals Page 30 minutes–4 hours from your click, with the same caption and all four link comments on each.';
  var status=document.createElement('p');status.setAttribute('role','status');status.textContent='Checking posting service…';
  var caption=document.createElement('p');
  var actions=document.createElement('div');actions.style.cssText='display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:14px 0';
  var post=document.createElement('button');post.type='button';post.textContent='Post now';post.disabled=true;
  post.style.cssText='padding:12px 24px;background:#1473e6;color:white;border:0;border-radius:10px;font-size:16px;font-weight:700';
  var cancel=document.createElement('button');cancel.type='button';cancel.textContent='Cancel scheduled post';cancel.hidden=true;
  actions.append(post,cancel);
  var links=document.createElement('details');var summary=document.createElement('summary');summary.textContent='Four comments, in order';links.append(summary);
  var list=document.createElement('ol');
  [
    ['Home Depot deals for today only.','https://brandcycle.shop/n26ik'],
    ['Home Depot Pro Deals for Today.','https://brandcycle.shop/z3wjo'],
    ['Lowes Tool Deals','https://shoplowes.me/4nQp6Rk'],
    ['Lowes Daily Deals','https://shoplowes.me/3Q6wL1x']
  ].forEach(function(item){var li=document.createElement('li');var a=document.createElement('a');a.href=item[1];a.textContent=item[0];a.target='_blank';a.rel='noopener';li.append(document.createTextNode('#ad  '),a);list.append(li);});
  links.append(list);panel.append(title,info,status,caption,actions,links);
  main.prepend(panel);
  var active=null,busy=false,requestKey='daily-retailer-pending-request';
  async function request(path,body){
    var controller=new AbortController();var timer=setTimeout(function(){controller.abort();},8000);
    try{
      var options={signal:controller.signal};
      if(body){options.method='POST';options.headers={'Content-Type':'application/json'};options.body=JSON.stringify(body);}
      var response=await fetch(base+path,options);var value=await response.json();
      if(!response.ok)throw new Error(value.error||'Unable to schedule.');return value;
    }finally{clearTimeout(timer);}
  }
  function draw(items){
    var today=new Date().toLocaleDateString('en-CA',{timeZone:'America/New_York'});
    active=items.find(function(i){return ['queued','running','failed','needs_review'].includes(i.state);})||items.find(function(i){return i.state==='complete'&&i.day===today;})||null;
    post.disabled=busy||!!active;cancel.hidden=!active||active.state!=='queued';cancel.disabled=busy;
    caption.textContent=active?'Caption ('+active.deal.text.length+'/128): “'+active.deal.text+'”':'';
    if(!active){status.textContent='Ready. Each click schedules today’s post once. Keep this PC awake.';return;}
    if(active.state==='queued')status.textContent='Scheduled: '+new Date(active.due*1000).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})+' Eastern. Browser or scanner delays may make it later.';
    if(active.state==='running')status.textContent='Posting to the group and Page. Adding all four comments to each…';
    if(active.state==='complete')status.textContent='Posted successfully with all four comments. Ready again tomorrow.';
    if(active.state==='needs_review')status.textContent='This daily post needs review. Other queued posts can continue. '+String(active.error||'').split('\n')[0].slice(0,180);
    if(active.state==='failed')status.textContent='Needs review: '+(active.error||'The last attempt did not finish. Check Facebook before retrying.');
  }
  async function refresh(){
    if(busy)return;
    try{draw((await request('/daily-retailer')).items);}
    catch(error){status.textContent='Daily post service unavailable. Check that the posting queue is running and this browser allows local network access.';post.disabled=true;}
  }
  post.addEventListener('click',async function(){
    if(busy||active)return;busy=true;post.disabled=true;
    var id=localStorage.getItem(requestKey)||crypto.randomUUID();localStorage.setItem(requestKey,id);
    status.textContent='Choosing a caption and random posting time…';
    try{var response=await request('/daily-retailer',{request_id:id});localStorage.removeItem(requestKey);draw([response.item]);}
    catch(error){status.textContent='Scheduling was not confirmed. Checking for an existing request before you retry.';}
    finally{busy=false;await refresh();}
  });
  cancel.addEventListener('click',async function(){
    if(!active||busy)return;busy=true;cancel.disabled=true;
    try{await request('/daily-retailer/cancel',{id:active.id});localStorage.removeItem(requestKey);}
    catch(error){status.textContent=error.message;}
    finally{busy=false;await refresh();}
  });
  refresh();setInterval(refresh,10000);
}());

