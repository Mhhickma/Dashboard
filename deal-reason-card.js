// Add deal explanations and copy-ready Facebook post text to each product card.
(function () {
  var FACEBOOK_POST_MAX_LENGTH = 129;

  function number(value) {
    var parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function displayReasons(deal) {
    var reasons = [];
    var drop7 = number(deal.drop_percent);
    var drop30 = number(deal.drop_30_percent);
    var bestDays = number(deal.best_price_days);

    if (drop30 >= 10) reasons.push(drop30.toFixed(1) + "% below its 30-day average");
    if (drop7 >= 7 && drop30 >= 7) {
      reasons.push(drop7.toFixed(1) + "% below its 7-day average and " + drop30.toFixed(1) + "% below its 30-day average");
    }
    if (bestDays >= 90) reasons.push("Lowest price in at least " + Math.round(bestDays) + " days");
    if (reasons.length === 0 && Array.isArray(deal.qualification_reasons)) reasons = deal.qualification_reasons.slice();
    return reasons;
  }

  function stableNumber(value) {
    return String(value || "").split("").reduce(function (total, character) {
      return ((total * 31) + character.charCodeAt(0)) >>> 0;
    }, 0);
  }

  function cleanTitle(value) {
    return String(value || "Great Amazon find")
      .replace(/[®™©]/g, "")
      .replace(/\s+/g, " ")
      .replace(/\s*[-–—|]\s*Amazon.*$/i, "")
      .trim();
  }

  function shortenText(value, maxLength) {
    var text = cleanTitle(value);
    if (text.length <= maxLength) return text;
    var shortened = text.slice(0, maxLength + 1).replace(/\s+\S*$/, "").replace(/[,:;\-\s]+$/, "");
    return shortened || text.slice(0, maxLength).trim();
  }

  function facebookPostText(deal) {
    var templates = [
      ["Standout find: ", ". A rare deal based on its recent history. ad"],
      ["Worth a look: ", ". This deal stands out from its recent history. ad"],
      ["Deal watch: ", ". A stronger-than-usual find right now. ad"],
      ["Good find: ", ". This one rarely reaches this deal level. ad"],
      ["Spotted: ", ". Its recent history makes this a standout deal. ad"],
      ["Take a look at ", ". This is an uncommon deal for this item. ad"],
      ["Today's find: ", ". This one stands apart from its usual history. ad"],
      ["On my deal radar: ", ". A notable find based on its recent history. ad"]
    ];
    var template = templates[stableNumber(deal.asin) % templates.length];
    var titleBudget = FACEBOOK_POST_MAX_LENGTH - template[0].length - template[1].length;
    var post = template[0] + shortenText(deal.title, titleBudget) + template[1];

    if (post.length <= FACEBOOK_POST_MAX_LENGTH) return post;
    return post
      .slice(0, FACEBOOK_POST_MAX_LENGTH - 3)
      .replace(/\s+ad\s*$/i, "")
      .replace(/[,:;\-\s]+$/, "") + " ad";
  }

  async function copyFacebookPost(text, button) {
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "Copied Facebook Post";
    } catch (error) {
      window.prompt("Copy this Facebook post:", text);
      button.textContent = "Post Ready";
    }
    window.setTimeout(function () { button.textContent = "Copy Facebook Post"; }, 1800);
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
    heading.textContent = "Facebook Post - " + postText.length + " characters";
    box.appendChild(heading);
    var preview = document.createElement("p");
    preview.className = "facebook-post-preview";
    preview.textContent = postText;
    box.appendChild(preview);
    var copyButton = document.createElement("button");
    copyButton.className = "copy-facebook-post";
    copyButton.type = "button";
    copyButton.textContent = "Copy Facebook Post";
    copyButton.addEventListener("click", function () { copyFacebookPost(postText, copyButton); });
    box.appendChild(copyButton);
    var amazonButton = card.querySelector("a.button");
    if (amazonButton) amazonButton.insertAdjacentElement("beforebegin", box);
    else card.querySelector(".card-body").appendChild(box);
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
