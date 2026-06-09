// Add deal explanations and copy-ready Facebook post text to each product card.
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

  function facebookDealDescription(deal) {
    var drop7 = number(deal.drop_percent);
    var drop30 = number(deal.drop_30_percent);
    var bestDays = number(deal.best_price_days);
    var descriptions = [];

    if (bestDays >= 365) {
      descriptions.push("This is one of its lowest prices in years.");
    } else if (bestDays >= 90) {
      descriptions.push("This is one of its lowest prices in months.");
    }

    if (drop7 >= 7 && drop30 >= 7) {
      descriptions.push("It is currently well below both its recent and longer-term average prices.");
    } else if (drop30 >= 10) {
      descriptions.push("It is currently well below its usual recent price.");
    }

    if (descriptions.length === 0) {
      descriptions.push("This item is currently showing a strong deal based on its recent price history.");
    }

    return descriptions.join(" ");
  }

  function facebookPostText(deal) {
    return [
      "Deal alert: " + deal.title,
      "",
      facebookDealDescription(deal),
      "",
      deal.amazon_url,
      "",
      "ad"
    ].join("\n");
  }

  async function copyFacebookPost(text, button) {
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "Copied Facebook Post";
    } catch (error) {
      window.prompt("Copy this Facebook post:", text);
      button.textContent = "Post Ready";
    }

    window.setTimeout(function () {
      button.textContent = "Copy Facebook Post";
    }, 1800);
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

  function addFacebookPost(card, deal) {
    if (card.querySelector(".facebook-post-box")) return;

    var postText = facebookPostText(deal);
    var box = document.createElement("section");
    box.className = "facebook-post-box";
    box.setAttribute("aria-label", "Facebook post text");

    var heading = document.createElement("strong");
    heading.className = "facebook-post-heading";
    heading.textContent = "Facebook Post";
    box.appendChild(heading);

    var preview = document.createElement("p");
    preview.className = "facebook-post-preview";
    preview.textContent = postText;
    box.appendChild(preview);

    var copyButton = document.createElement("button");
    copyButton.className = "copy-facebook-post";
    copyButton.type = "button";
    copyButton.textContent = "Copy Facebook Post";
    copyButton.addEventListener("click", function () {
      copyFacebookPost(postText, copyButton);
    });
    box.appendChild(copyButton);

    var amazonButton = card.querySelector("a.button");
    if (amazonButton) {
      amazonButton.insertAdjacentElement("beforebegin", box);
    } else {
      card.querySelector(".card-body").appendChild(box);
    }
  }

  var originalBuildCard = window.buildCard;
  if (typeof originalBuildCard !== "function") return;

  window.buildCard = function (deal, isSelected, isSelectedSection) {
    var card = originalBuildCard(deal, isSelected, isSelectedSection);
    addDealReason(card, deal);
    addFacebookPost(card, deal);
    return card;
  };
}());
