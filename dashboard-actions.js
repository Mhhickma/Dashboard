// Apply Telegram's shared Hide 24h / Remove ASIN actions in every dashboard browser.
(function(){
  if(typeof removeQueueAsins!=='function'||typeof activeHiddenMap!=='function')return;
  var removed=new Set(),key='dashboard-shared-actions-cache';
  var original=removeQueueAsins;
  removeQueueAsins=function(){var values=original();removed.forEach(function(asin){values.add(asin);});return values;};
  function apply(items){
    var hidden=activeHiddenMap(),changed=false,nextRemoved=new Set();
    items.forEach(function(item){
      if(item.action==='removed')nextRemoved.add(item.asin);
      else if(item.action==='hidden'&&item.until>Date.now()&&Number(hidden[item.asin]||0)<item.until){hidden[item.asin]=item.until;changed=true;}
      if(item.action==='removed'||item.until>Date.now())removeFromSelectedForPosting(item.asin);
    });
    if([...nextRemoved].join(',')!==[...removed].join(','))changed=true;
    removed=nextRemoved;
    if(changed){writeHiddenMap(hidden);applySearch(false);}
  }
  async function refresh(){
    try{
      var response=await fetch('http://127.0.0.1:8766/dashboard-actions');
      if(!response.ok)return;
      var data=await response.json();apply(data.items||[]);
      localStorage.setItem(key,JSON.stringify(data.items||[]));
    }catch(error){}
  }
  try{apply(JSON.parse(localStorage.getItem(key)||'[]'));}catch(error){}
  refresh();setInterval(refresh,15000);
}());

