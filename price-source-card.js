// Adds a clear label when a card is priced from a non-standard Keepa price track.
(function(){
  if(!document.getElementById("price-source-card-styles")){
    var style=document.createElement("style");
    style.id="price-source-card-styles";
    style.textContent=".price-source-pill{display:inline-flex;align-items:center;width:max-content;margin:0 0 .5rem 0;border-radius:999px;padding:.25rem .55rem;font-size:.78rem;font-weight:700;background:#fff4d6;color:#7a4b00;border:1px solid #f2c766}.price-source-pill+*{margin-top:.1rem}";
    document.head.appendChild(style);
  }
  function decorate(card,deal){
    if(!card||!deal||!deal.price_type_label||deal.price_type_label==="Amazon price")return card;
    var tag=document.createElement("div");
    tag.className="price-source-pill";
    tag.textContent=deal.price_type_label;
    card.prepend(tag);
    return card;
  }
  var original=window.buildCard;
  if(typeof original==="function"){
    window.buildCard=function(deal){return decorate(original(deal),deal);};
  }
}());
