(() => {
  function numericValue(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function hoursUntil(value) {
    if (!value) return null;
    const diffMs = new Date(value).getTime() - Date.now();
    if (!Number.isFinite(diffMs)) return null;
    return Math.max(0, diffMs / (1000 * 60 * 60));
  }

  function fallbackDollarDrop(deal) {
    const currentPrice = numericValue(deal.current_price);
    const avg7Price = numericValue(deal.avg_7_price);

    if (currentPrice === null || avg7Price === null) return null;
    return Math.max(0, avg7Price - currentPrice);
  }

  function fallbackDealScore(deal) {
    const dropPercent = numericValue(deal.drop_percent) || 0;
    const drop30Percent = numericValue(deal.drop_30_percent) || 0;
    const savings = fallbackDollarDrop(deal) || 0;
    const freshnessHours = hoursUntil(deal.expires_at);
    const freshnessBonus = freshnessHours === null ? 0 : Math.max(0, Math.min(24, freshnessHours)) / 24;

    return (dropPercent * 2) + drop30Percent + Math.min(savings, 100) + freshnessBonus;
  }

  function getDealScore(deal) {
    if (typeof window.dealScore === "function") {
      return window.dealScore(deal);
    }

    return fallbackDealScore(deal);
  }

  function formatDealScore(deal) {
    return getDealScore(deal).toFixed(1);
  }

  const originalBuildCard = window.buildCard;
  if (typeof originalBuildCard !== "function") return;

  window.buildCard = function buildCardWithDealScore(deal, isSelected, isSelectedSection) {
    const card = originalBuildCard(deal, isSelected, isSelectedSection);
    const topRow = card.querySelector(".card-top-row");
    if (!topRow || card.querySelector(".score-badge")) return card;

    let metrics = topRow.querySelector(".deal-metrics");
    if (!metrics) {
      metrics = document.createElement("div");
      metrics.className = "deal-metrics";

      const badge = topRow.querySelector(".badge");
      if (badge) metrics.appendChild(badge);

      topRow.insertBefore(metrics, topRow.firstChild);
    }

    const scoreBadge = document.createElement("span");
    scoreBadge.className = "score-badge";
    scoreBadge.title = "Best deal score uses 7-day discount, 30-day discount, dollar savings, and freshness.";
    scoreBadge.innerHTML = `Deal score <strong>${formatDealScore(deal)}</strong>`;
    metrics.appendChild(scoreBadge);

    return card;
  };
})();
