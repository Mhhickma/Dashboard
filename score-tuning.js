// Tune deal score so best-price age matters less.
(function () {
  function num(value) {
    var number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function hoursUntil(value) {
    if (!value) return null;
    var diffMs = new Date(value).getTime() - Date.now();
    return Number.isFinite(diffMs) ? Math.max(0, diffMs / 3600000) : null;
  }

  function dollarSavings(deal) {
    var current = num(deal.current_price);
    var avg7 = num(deal.avg_7_price);
    if (current === null || avg7 === null) return 0;
    return Math.max(0, avg7 - current);
  }

  function bestDays(deal) {
    return num(deal.best_price_days) || 0;
  }

  function tunedDealScore(deal) {
    var drop7 = num(deal.drop_percent) || 0;
    var drop30 = num(deal.drop_30_percent) || 0;
    var freshHours = hoursUntil(deal.expires_at);
    var freshness = freshHours === null ? 0 : Math.max(0, Math.min(24, freshHours)) / 24;
    var rarity = Math.min(bestDays(deal), 90) / 6;
    return (drop7 * 2) + drop30 + Math.min(dollarSavings(deal), 100) + freshness + rarity;
  }

  function tunedQualityLabel(deal) {
    var score = tunedDealScore(deal);
    var days = bestDays(deal);
    var drop = num(deal.drop_percent) || 0;
    if (score >= 120 || (days >= 90 && drop >= 10)) return "Elite";
    if (score >= 80 || (days >= 90 && drop >= 6)) return "Strong";
    if (score >= 55 || days >= 30) return "Good";
    return "Watch";
  }

  window.dealScore = tunedDealScore;

  var originalBuildCard = window.buildCard;
  if (typeof originalBuildCard === "function") {
    window.buildCard = function (deal, isSelected, isSelectedSection) {
      var card = originalBuildCard(deal, isSelected, isSelectedSection);
      var label = tunedQualityLabel(deal);
      var qualityBadge = card.querySelector(".quality-badge");
      var scoreBadge = card.querySelector(".score-badge");

      if (qualityBadge) {
        qualityBadge.className = "quality-badge quality-" + label.toLowerCase();
        qualityBadge.textContent = label;
      }

      if (scoreBadge) {
        scoreBadge.title = "Best deal score uses discount, dollar savings, freshness, and a smaller best-price-age bonus.";
        scoreBadge.textContent = "Deal score " + tunedDealScore(deal).toFixed(1);
      }

      return card;
    };
  }

  if (typeof window.applySearch === "function") {
    setTimeout(function () {
      window.applySearch(false);
    }, 0);
  }
}());
