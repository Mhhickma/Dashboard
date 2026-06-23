// Adds a clear label when a card is priced from a non-standard Keepa price track.
(function () {
  function injectStyles() {
    if (document.getElementById("price-source-card-styles")) return;
    var style = document.createElement("style");
    style.id = "price-source-card-styles";
    style.textContent = ".price-source-pill{display:inline-flex;align-items:center;border-radius:999px;padding:.25rem .55rem;font-size:.78rem;font-weight:700;background:#fff4d6;color:#7a4b00;border:1px solid #f2c76