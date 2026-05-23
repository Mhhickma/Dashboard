// Tune deal score to a true 100-point scale.
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

  function points(value, maxValue, maxPoints) {
    if (!value || value <= 0) return 0;
    return Math.min(maxPoints, (value / maxValue) * maxPoints);
  }

  function tunedDealScore(deal) {
    var drop7 = num(deal.drop_percent) || 0;
    var drop30 = num(deal.drop_30_percent) || 0;
    var savings = dollarSavings(deal);
    var freshHours = hoursUntil(deal.expires_at);
    var bestPriceAge = bestDays(deal);

    var drop7Points = points(drop7, 25, 25);
    var drop30Points = points(drop30, 25, 25);
    var savingsPoints = points(savings, 100, 30);
    var rarityPoints = points(Math.min(bestPriceAge, 90), 90, 15);
    var freshnessPoints = freshHours === null ? 0 : points(Math.min(freshHours, 24), 24, 5);

    return drop7Points + drop30Points + savingsPoints + rarityPoints + freshnessPoints;
  }

  function tunedQualityLabel(deal) {
    var score = tunedDealScore(deal);
    var days = bestDays(deal);
    var drop = num(deal.drop_percent) || 0;
    if (score >= 85 || (days >= 90 && drop >= 10)) return "Elite";
    if (score >= 70 || (days >= 90 && drop >= 6)) return "Strong";
    if (score >= 50 || days >= 30) return "Good";
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
        scoreBadge.title = "100-point score: 25 points for 7-day drop, 25 for 30-day drop, 30 for dollar savings, 15 for best-price age, and 5 for freshness.";
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
