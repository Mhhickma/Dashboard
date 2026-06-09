// Add a plain-language explanation of why each product qualifies as a deal.
(function () {
  function number(value) {
    var parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function displayReasons(deal) {
    var reasons = [];
    var drop7 = number(deal.drop_percent);
    var drop30 = number(deal.drop_30_percent);
    var bestDays = number(deal.best_price_days);

    if (drop30 >= 10) {
      reasons.push(drop30.toFixed(1) + "% below its 30-day average");
    }

    if (drop7 >= 7 && drop30 >= 7) {
      reasons.push(
        drop7.toFixed(1) + "% below its 7-day average and " +
        drop30.toFixed(1) + "% below its 30-day average"
      );
    }

    if (bestDays >= 90) {
      reasons.push("Lowest price in at least " + Math.round(bestDays) + " days");
    }

    if (reasons.length === 0 && Array.isArray(deal.qualification_reasons)) {
      reasons = deal.qualification_reasons.slice();
    }

    return reasons;
  }

  function addDealReason(card, deal) {
    var asin = card.querySelector(".asin");
    if (!asin || card.querySelector(".why-deal-box")) return;

    var reasons = displayReasons(deal);
    if (reasons.length === 0) return;

    var box = document.createElement("section");
    box.className = "why-deal-box";
    box.setAttribute("aria-label", "Why this is a deal");

    var heading = document.createElement("strong");
    heading.className = "why-deal-heading";
    heading.textContent = "Why this is a deal";
    box.appendChild(heading);

    var list = document.createElement("ul");
    list.className = "why-deal-list";
    reasons.forEach(function (reason) {
      var item = document.createElement("li");
      item.textContent = reason;
      list.appendChild(item);
    });
    box.appendChild(list);

    asin.insertAdjacentElement("afterend", box);
  }

  var originalBuildCard = window.buildCard;
  if (typeof originalBuildCard !== "function") return;

  window.buildCard = function (deal, isSelected, isSelectedSection) {
    var card = originalBuildCard(deal, isSelected, isSelectedSection);
    addDealReason(card, deal);
    return card;
  };
}());
