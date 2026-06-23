// Adds a clear label when a card is priced from a non-standard Keepa price track.
(function () {
  function injectStyles() {
    if (document.getElementById("price-source-card-styles")) return;

    const style = document.createElement("style");
    style.id = "price-source-card-styles";
    style.textContent = `
      .price-source-pill {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 0.25rem 0.55