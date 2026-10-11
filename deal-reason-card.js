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
    if (drop7 >= 7 && drop30 >= 7) reasons.push(drop7.toFixed(1) + "% below its 7-day average and " + drop30.toFixed(1) + "% below its 30-day average");
    if (bestDays >= 90) reasons.push("Lowest price in at least " + Math.round(bestDays) + " days");
    if (reasons.length === 0 && Array.isArray(deal.qualification_reasons)) reasons = deal.qualification_reasons.slice();
    return reasons;
  }

  function stableNumber(value) {
    return String(value || "").split("").reduce(function (total, character) {
      return ((total * 31) + character.charCodeAt(0)) >>> 0;
    }, 0);
  }

  function isModelNumber(token) {
    var clean = token.replace(/^[^A-Za-z0-9]+|[^A-Za-z0-9.-]+$/g, "");
    if (!clean) return false;
    if (/^\d{4,}(?:-[A-Za-z0-9]+)?$/i.test(clean)) return true;
    if (/^(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$/i.test(clean)) {
      return !/^\d+(?:\.\d+)?(?:v|ah|in|inch|ft|oz|lb|lbs|mm|cm|pk)$/i.test(clean);
    }
    return false;
  }

  function cleanTitle(value) {
    var title = String(value || "Great Amazon find")
      .replace(/[®™©*]/g, "")
      .replace(/\([^)]*(?=[A-Za-z-]*\d)[^)]*\)/g, "")
      .replace(/\s+/g, " ")
      .replace(/\s*[-–—|]\s*Amazon.*$/i, "")
      .trim();

    title = title.split(" ").filter(function (token) { return !isModelNumber(token); }).join(" ");
    title = title.replace(/\s+([,.;:)])/g, "$1").replace(/([(])\s+/g, "$1").replace(/\(\s*\)/g, "");
    title = title.split(/,\s+(?=(?:black|white|red|blue|gray|grey|orange|yellow|green|silver|gold)\b)/i)[0];
    return title.replace(/[,:;\-\s]+$/, "").trim() || "Great Amazon find";
  }

  function shortenText(value, maxLength) {
    var text = cleanTitle(value);
    if (text.length <= maxLength) return text;
    var shortened = text.slice(0, maxLength + 1).replace(/\s+\S*$/, "").replace(/[,:;\-\s]+$/, "");
    return shortened || text.slice(0, maxLength).trim();
  }

  function dealFact(deal) {
    var bestDays = Math.round(number(deal.best_price_days));

    if (bestDays >= 335) return "Best price this year.";
    if (bestDays >= 180) return "Best price in months.";
    if (bestDays >= 30) return "Lowest price in " + bestDays + " days.";
    return "Lower price than normal right now.";
  }

  // Match the daily engagement voices: practical curiosity and light shop humor.
  // Fixed local wording keeps automated posting free of AI service calls.
  function shopCaption(deal) {
    var title = String(deal.title || "");
    var rules = [
      [/hold[ -]?down clamps?/i, ["Mini hold-down clamps for your T-track jigs. Handy for keeping the workpiece in place.", "Anyone building a new sled or jig? These hold-down clamps fit T-track."]],
      [/paddle switch|knee paddle|power.*switch/i, ["Anyone need a paddle switch for a shop machine? Nice to have the stop button where your knee can reach it.", "A paddle switch for the shop. Check your machine's ratings before swapping one in."]],
      [/freud.*dado/i, ["Freud dado set below. Anyone cutting dados, or are you doing them with a router?", "Anyone need a dado set? This Freud set is worth checking before the next cabinet project."]],
      [/bosch.*12v.*(?:jig\s*saw|jigsaw)/i, ["Bosch cordless jigsaw below. Anyone using their 12V tools in the shop?", "Anyone prefer a barrel-grip jigsaw? This Bosch is a bare tool, so you'll need the battery."]],
      [/dado set|dado blade/i, ["Anyone need a dado set before the next cabinet project? Linked below."]],
      [/jig\s*saw|jigsaw/i, ["Anyone prefer a jigsaw for curved cuts? One to check out below."]],
      [/socket.*adapter|drill.*extension|bit.*extension/i, ["For the screw your drill can't reach. Extensions and socket adapters below.", "Drill extensions and socket adapters. Handy when the screw is just out of reach."]],
      [/\bclamps?\b/i, ["Clamps below. I'm sure you already have enough...until the next glue-up.", "A few more clamps for the shop. You have room, right?"]],
      [/\bvise\b/i, ["Anyone need a bench vise? Beats chasing the part around while you work on it.", "A bench vise for the small jobs. Sometimes a third hand would be nice."]],
      [/tape measure|measuring tape/i, ["More tape measures. Because the ones you own are probably hiding somewhere.", "Anyone need a spare tape measure? Or a spare for the spare?"]],
      [/tool.*liner|drawer.*liner/i, ["Tool drawer liner. For those of us whose tools move around more than they should.", "I'm sure your tool drawers are perfectly organized...so you can skip this liner."]],
      [/backing pad/i, ["Backing pad below if yours is ready to retire. Not exciting, but sometimes you need one.", "Anyone need a replacement backing pad? One of those things you forget until sanding day."]],
      [/router bit/i, ["A router bit for the next project. Or the next project you haven't thought of yet.", "One more router bit for the drawer. Anyone actually use every bit they own?"]],
      [/safety glasses|computer glasses|blue light.*glasses/i, ["Anyone else keep spare glasses around so there's a pair when you need them? Found these today.", "Glasses only help when you can find them. A spare pair might be worth a look."]],
      [/air filtration|air filter|dust collect/i, ["Something for the shop dust problem. Making sawdust is the easy part.", "For those of you making more sawdust than progress today. Dust cleanup below."]],
      [/sander|sanding/i, ["The project is built. Now comes all that sanding. Found something worth a look before the next round.", "Anyone actually enjoy sanding? Found this for that part of the project we all have to get through."]],
      [/saw blade/i, ["When did you last check your saw blade? A fresh one might belong on the next shop shopping list.", "Blades are easy to forget until a cut reminds you. Found this one today."]],
      [/\bsaw\b/i, ["What's on your next project list? This saw might be worth a look for the shop.", "One new saw, three new project ideas. Anyone else work that way? Found this today."]],
      [/\bdrill\b|impact driver/i, ["What's the drill that gets used most in your shop? Found this one worth checking today.", "From shop jigs to the weekend fix-it list, a drill stays busy. Found this today."]],
      [/organizer|storage|tool box|toolbox/i, ["Shop cleanup: put things away, then remember where you put them. Found this to help with the first part.", "Anyone else spend more time finding tools than using them? Here's a storage idea worth a look."]],
      [/light|lamp/i, ["Ever move a project just to see your pencil line? Found some lighting worth a look.", "Better light belongs on the shop wish list too. Found this today."]],
      [/glue|adhesive/i, ["Got a glue-up on the weekend list? Might be a good time to check the glue shelf.", "Nothing like setting up a glue-up and finding an empty bottle. Found this today."]],
      [/square|level|caliper|ruler/i, ["Measure twice, cut once... then check it again? Found this for the measuring drawer.", "What measurement gives you the most trouble? Found a measuring tool worth a look."]],
      [/workbench|work bench/i, ["What's taking up your workbench right now? Found this for anyone planning a bench upgrade.", "A place to work beats balancing the project on whatever is handy. Found this bench today."]],
      [/battery|charger/i, ["Ever start a project and find every battery dead? Found this for the charging corner.", "Charged batteries make the weekend project easier to start. Found this today."]],
      [/screw|bolt|nut|fastener/i, ["The right fastener is always in the other drawer. Found these for the next shop project.", "Got a build coming up? Might be time to check the fastener stash."]]
    ];
    var choices = null;
    for (var i = 0; i < rules.length; i += 1) {
      if (rules[i][0].test(title)) { choices = rules[i][1]; break; }
    }
    if (!choices) {
      choices = ["Something for the shop wish list. Take a look if you're planning the next project."];
    }
    var post = choices[stableNumber(deal.asin + title) % choices.length];
    if (post.length > FACEBOOK_POST_MAX_LENGTH) {
      post = "Found something for the shop wish list. Worth a look if it's on yours too.";
    }
    return post;
  }

  function itemIdentity(title) {
    var types = [
      [/hold[ -]?down clamps?/i, "hold-down clamps"],
      [/paddle switch|knee paddle/i, "paddle switch"], [/dado set|dado blade/i, "dado set"],
      [/jig\s*saw|jigsaw/i, "jigsaw"], [/socket.*adapter|drill.*extension|bit.*extension/i, "drill extensions and socket adapters"],
      [/backing pad/i, "backing pad"], [/router bit/i, "router bit"],
      [/deck screws/i, "deck screws"], [/wood screws/i, "wood screws"], [/screwdriver/i, "screwdriver set"],
      [/t[- ]?track.*bolt/i, "T-track bolts"], [/\bscrews?\b/i, "screws"], [/\bbolts?\b/i, "bolts"], [/\bnuts?\b/i, "nuts"],
      [/backing pad/i, "backing pad"], [/router bit/i, "router bit"], [/tape measure|measuring tape/i, "tape measures"],
      [/parallel clamps/i, "parallel clamps"], [/bar clamps/i, "bar clamps"], [/corner clamps/i, "corner clamps"], [/clamps?/i, "clamps"],
      [/vise/i, "bench vise"], [/drawer.*liner|tool.*liner/i, "tool drawer liner"],
      [/blue light|computer glasses/i, "blue light glasses"], [/safety glasses/i, "safety glasses"],
      [/dust collect/i, "dust collector"], [/air filtration/i, "air filtration system"], [/saw blade/i, "saw blade"],
      [/miter saw/i, "miter saw"], [/table saw/i, "table saw"], [/scroll saw/i, "scroll saw"], [/band\s*saw/i, "bandsaw"],
      [/sander/i, "sander"], [/sandpaper|sand paper/i, "sandpaper"], [/impact driver/i, "impact driver"], [/drill/i, "drill"],
      [/workbench|work bench/i, "workbench"], [/flashlight/i, "flashlight"], [/charger/i, "charger"], [/battery/i, "battery"],
      [/glue/i, "glue"], [/organizer/i, "organizer"], [/tool ?box/i, "toolbox"], [/shop stool/i, "shop stool"]
    ];
    for (var i = 0; i < types.length; i += 1) {
      if (types[i][0].test(title)) return types[i][1];
    }
    // Unrecognized items still get their own short identity, never anonymous filler.
    return shortenText(cleanTitle(title).split(/[,;|]/)[0], 55);
  }

  function facebookPostText(deal) {
    var title = String(deal.title || "");
    var item = itemIdentity(title);
    var post = shopCaption(deal);
    if (/hold[ -]?down clamps?/i.test(title)) {
      if (!/mini/i.test(title)) post = post.replace("Mini hold-down", "Hold-down");
      if (!/t[- ]?track/i.test(title)) post = "Hold-down clamps for your shop jigs. Handy for keeping the workpiece in place.";
    }
    if (/clamps$/.test(item) && post.toLowerCase().indexOf(item.toLowerCase()) === -1) post = post.replace(/\bclamps\b/gi, item);
    if (post.length > FACEBOOK_POST_MAX_LENGTH) post = item + ". Worth a look for the next project.";
    if (post.toLowerCase().indexOf(item.toLowerCase()) !== -1) return post;
    var identity = item.charAt(0).toUpperCase() + item.slice(1);
    if (post.indexOf("Something for the shop wish list.") === 0) {
      return identity + ". Anyone need one for the next project?";
    }
    var combined = identity + ". " + post;
    return combined.length <= FACEBOOK_POST_MAX_LENGTH ? combined : identity + ". Worth a look if it's on your shop list.";
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
    reasons.forEach(function (reason) { var item = document.createElement("li"); item.textContent = reason; list.appendChild(item); });
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

  function publishButton(deal, target, delayMinutes, label) {
    var button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", function () {
      if (typeof window.publishDeal !== "function") {
        window.alert("Publishing tools are still loading. Refresh the dashboard and try again.");
        return;
      }
      window.publishDeal(deal, target, delayMinutes, button);
    });
    return button;
  }

  function addPublishControls(card, deal) {
    if (card.querySelector(".posting-helper-box")) return;
    var amazonButton = card.querySelector("a.button");
    var body = card.querySelector(".card-body");
    if (!body) return;

    var box = document.createElement("section");
    box.className = "posting-helper-box";
    box.setAttribute("aria-label", "Publish or schedule deal");

    var note = document.createElement("p");
    note.textContent = "Publish to a Page or add a scheduled row to a Publer Group CSV.";
    box.appendChild(note);

    var targets = document.body.dataset.dashboardMode === "best-sellers"
      ? [["Black Lab", "blackLabPage"]]
      : [["Wood Page", "woodworkingPage"]];

    targets.forEach(function (target) {
      var row = document.createElement("div");
      row.className = "publish-tool-row";
      var label = document.createElement("span");
      label.textContent = target[0];
      row.appendChild(label);
      row.appendChild(publishButton(deal, target[1], 0, "Now"));
      row.appendChild(publishButton(deal, target[1], 60, "60"));
      row.appendChild(publishButton(deal, target[1], 90, "90"));
      row.appendChild(publishButton(deal, target[1], 120, "120"));
      box.appendChild(row);
    });

    if (amazonButton) amazonButton.insertAdjacentElement("beforebegin", box);
    else body.appendChild(box);
  }

  var originalBuildCard = window.buildCard;
  if (typeof originalBuildCard !== "function") return;
  window.buildCard = function (deal, isSelected, isSelectedSection) {
    var card = originalBuildCard(deal, isSelected, isSelectedSection);
    addDealReason(card, deal);
    addFacebookPost(card, deal);
    addPublishControls(card, deal);
    return card;
  };
}());

