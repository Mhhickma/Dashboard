// Sort product cards by visible deal tier first: Elite, Strong, Good, Watch.
(function () {
  var tierRank = {
    Elite: 4,
    Strong: 3,
    Good: 2,
    Watch: 1,
    Pass: 0
  };

  function num(value) {
    var number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function dateValue(value) {
    if (!value) return 0;
    var time = new Date(value).getTime();
    return Number.isFinite(time) ? time : 0;
  }

  function postedDateValue(deal) {
    return dateValue(deal.posted_at || deal.first_seen_at || deal.checked_at);
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

  function score(deal) {
    if (typeof window.dealScore === "function") {
      return window.dealScore(deal);
    }

    var drop7 = num(deal.drop_percent) || 0;
    var drop30 = num(deal.drop_30_percent) || 0;
    var savings = dollarSavings(deal);
    var freshHours = hoursUntil(deal.expires_at);
    var bestPriceAge = bestDays(deal);

    return points(drop7, 25, 25) +
      points(drop30, 25, 25) +
      points(savings, 100, 30) +
      points(Math.min(bestPriceAge, 90), 90, 15) +
      (freshHours === null ? 0 : points(Math.min(freshHours, 24), 24, 5));
  }

  function tierLabel(deal) {
    var dealScore = score(deal);
    var days = bestDays(deal);
    var drop = num(deal.drop_percent) || 0;

    if (dealScore >= 85 || (days >= 90 && drop >= 10)) return "Elite";
    if (dealScore >= 70 || (days >= 90 && drop >= 6)) return "Strong";
    if (dealScore >= 50 || days >= 30) return "Good";
    return "Watch";
  }

  function compareNullableNumbers(aValue, bValue, direction) {
    var aNumber = num(aValue);
    var bNumber = num(bValue);

    if (aNumber === null && bNumber === null) return 0;
    if (aNumber === null) return 1;
    if (bNumber === null) return -1;

    return direction === "asc" ? aNumber - bNumber : bNumber - aNumber;
  }

  function compareText(aValue, bValue) {
    return String(aValue || "").localeCompare(String(bValue || ""), undefined, {
      numeric: true,
      sensitivity: "base"
    });
  }

  function hasCreatorCampaign(deal) {
    return Boolean(deal && (deal.has_creator_campaign || deal.creator_campaign || deal.creator_commission_rate));
  }

  function creatorCampaignEndDateValue(deal) {
    var campaign = deal && deal.creator_campaign;
    if (!campaign || !campaign.campaign_end_date) return Number.MAX_SAFE_INTEGER;
    return dateValue(campaign.campaign_end_date) || Number.MAX_SAFE_INTEGER;
  }

  function dollarDrop(deal) {
    var currentPrice = num(deal.current_price);
    var avg7Price = num(deal.avg_7_price);
    if (currentPrice === null || avg7Price === null) return null;
    return Math.max(0, avg7Price - currentPrice);
  }

  function tierSortCompare(a, b) {
    var tierCompare = (tierRank[tierLabel(b)] || 0) - (tierRank[tierLabel(a)] || 0);
    var scoreCompare = compareNullableNumbers(score(a), score(b));
    return tierCompare || scoreCompare || postedDateValue(b) - postedDateValue(a);
  }

  window.sortDeals = function sortDeals(deals) {
    var sortSelect = document.getElementById("sortSelect");
    var sortMode = sortSelect ? sortSelect.value : "tier-rating";
    var sorted = [].slice.call(deals || []);

    sorted.sort(function (a, b) {
      if (sortMode === "tier-rating") return tierSortCompare(a, b);
      if (sortMode === "best-score") return compareNullableNumbers(score(a), score(b)) || postedDateValue(b) - postedDateValue(a);
      if (sortMode === "creator-first") return Number(hasCreatorCampaign(b)) - Number(hasCreatorCampaign(a)) || creatorCampaignEndDateValue(a) - creatorCampaignEndDateValue(b) || compareNullableNumbers(score(a), score(b)) || postedDateValue(b) - postedDateValue(a);
      if (sortMode === "newest") return postedDateValue(b) - postedDateValue(a);
      if (sortMode === "newest-checked") return dateValue(b.last_checked_at || b.checked_at) - dateValue(a.last_checked_at || a.checked_at);
      if (sortMode === "expiring-soon") return dateValue(a.expires_at) - dateValue(b.expires_at);
      if (sortMode === "highest-drop") return compareNullableNumbers(a.drop_percent, b.drop_percent);
      if (sortMode === "highest-30-drop") return compareNullableNumbers(a.drop_30_percent, b.drop_30_percent);
      if (sortMode === "highest-dollar-drop") return compareNullableNumbers(dollarDrop(a), dollarDrop(b));
      if (sortMode === "lowest-price") return compareNullableNumbers(a.current_price, b.current_price, "asc");
      if (sortMode === "highest-price") return compareNullableNumbers(a.current_price, b.current_price);
      if (sortMode === "title-az") return compareText(a.title, b.title);
      if (sortMode === "asin-az") return compareText(a.asin, b.asin);
      return tierSortCompare(a, b);
    });

    return sorted;
  };

  if (typeof window.applySearch === "function") {
    setTimeout(function () {
      window.applySearch(false);
    }, 0);
  }
}());
