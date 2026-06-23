// Adds a clear label when a card is priced from a non-standard Keepa price track.
(function(){
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
