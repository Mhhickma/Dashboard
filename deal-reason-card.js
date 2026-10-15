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

  function dealFact(deal) { return ''; }

  // Short item identity plus practical use. No title dumps or stock sales filler.
  function facebookPostText(deal) {
    var title = String(deal.title || "");
    var rules = [
      [/blast gate/i, "Blast gates for controlling airflow in your dust collection lines."],
      [/wall dust collector/i, "Wall-mounted dust collector for keeping the floor space clear."],
      [/track saw.*miter guide|miter guide.*guide rail/i, "Track saw miter guide for setting repeatable cutting angles."],
      [/all purpose white glue|all-purpose white glue|white glue/i, "All-purpose white glue for small repairs and everyday projects. Handy to keep with the shop supplies."],
      [/wood glue|pva adhesive/i, "Wood glue for your next glue-up."],
      [/\bglue\b/i, "Glue for everyday projects and small repairs. Handy to keep with the shop supplies."],
      [/welding table/i, "Welding table for metalwork in the shop."],
      [/hold[ -]?down clamps?/i, "Hold-down clamps for securing work to your jigs."],
      [/table\/track clamp|track clamp/i, "Track clamp for holding boards to your bench or jig."],
      [/paddle switch|knee paddle/i, "Paddle switch for a shop machine. Check voltage and amp ratings before fitting it."],
      [/dado set|dado blade/i, "Dado set for cutting grooves and dados."],
      [/jig\s*saw|jigsaw/i, "Jigsaw for curved cuts and cutouts."],
      [/socket.*adapter|drill.*extension|bit.*extension/i, "Drill extensions and socket adapters for hard-to-reach fasteners."],
      [/backing pad/i, "Replacement backing pad for sanding. Check the fitting against your tool."],
      [/router bit/i, "Router bit for your next jig or woodworking project."],
      [/tape measure|measuring tape/i, "Tape measures to keep at the bench and in your tool bag."],
      [/parallel clamps/i, "Parallel clamps for cabinet and panel glue-ups."],
      [/bar clamps/i, "Bar clamps for holding parts together during assembly."],
      [/corner clamps/i, "Corner clamps for holding parts at right angles."],
      [/\bclamps?\b/i, "Clamps for holding your work in place."],
      [/\bvise\b/i, "Bench vise for holding small parts while you work."],
      [/tool.*liner|drawer.*liner/i, "Tool drawer liner to help keep tools from sliding around."],
      [/blue light|computer glasses/i, "Blue light glasses for time at the computer."],
      [/safety glasses/i, "Safety glasses for shop work."],
      [/dust collect/i, "Dust collector for handling sawdust in the shop."],
      [/air filtration/i, "Air filtration system for airborne shop dust."],
      [/saw blade/i, "Replacement saw blade. Check the size and arbor against your saw."],
      [/scroll saw/i, "Scroll saw for detailed cuts and small projects."],
      [/miter saw/i, "Miter saw for crosscuts and angled cuts."],
      [/table saw/i, "Table saw for ripping boards and making straight cuts."],
      [/band\s*saw/i, "Bandsaw for straight and curved cuts."],
      [/sander/i, "Sander for smoothing boards and preparing a project for finish."],
      [/sandpaper|sand paper/i, "Sandpaper for the next round of project prep."],
      [/impact driver/i, "Impact driver for driving screws and other fasteners."],
      [/\bdrill\b/i, "Drill for holes, shop jigs and everyday repairs."],
      [/magnetic parts tray/i, "Magnetic parts tray for keeping small hardware together."],
      [/organizer|storage|tool ?box/i, "Shop storage for keeping tools and supplies organized."],
      [/workbench|work bench/i, "Workbench for assembly and everyday shop work."],
      [/flashlight/i, "Flashlight for seeing into tight or poorly lit spaces."],
      [/light|lamp/i, "Lighting for your bench or work area."],
      [/charger/i, "Charger for your tool batteries. Check platform compatibility."],
      [/battery/i, "Tool battery. Check that it matches your cordless platform."],
      [/square|level|caliper|ruler/i, "Measuring tool for checking your layout before cutting."],
      [/deck screws/i, "Deck screws for the next outdoor build."],
      [/wood screws/i, "Wood screws for shop projects and repairs."],
      [/screwdriver/i, "Screwdriver set for the bench or tool bag."],
      [/t[- ]?track.*bolt/i, "T-track bolts for mounting accessories to your jigs."],
      [/\bscrews?\b/i, "Screws for the next build or repair."],
      [/\bbolts?\b/i, "Bolts for your next project. Check the size you need."],
      [/\bnuts?\b/i, "Nuts for your project hardware. Check the thread size."],
      [/shop stool/i, "Shop stool for seated work at the bench."]
    ];
    var post = "";
    for (var i = 0; i < rules.length; i += 1) {
      if (rules[i][0].test(title)) { post = rules[i][1]; break; }
    }
    if (!post) {
      // Keep unfamiliar products short; do not append generic engagement prompts.
      post = shortenText(cleanTitle(title).split(/[,;|]|\s+(?:with|for)\s+/i)[0], 40) + ".";
    }
    if (/dado/i.test(title) && /^Freud\b/i.test(title)) post = "Freud " + post.charAt(0).toLowerCase() + post.slice(1);
    if (/jig\s*saw|jigsaw/i.test(title) && /^Bosch\b/i.test(title)) post = "Bosch " + post.charAt(0).toLowerCase() + post.slice(1);
    if (/wood glue/i.test(title) && /speed set/i.test(title)) post = "Fast-setting wood glue for your next glue-up.";
    if (/welding table/i.test(title) && /folding/i.test(title)) post = "Folding welding table for metalwork. Packs away between projects.";
    if (/hold[ -]?down clamps?/i.test(title) && /t[- ]?track/i.test(title)) post = "Hold-down clamps for securing work to your T-track jigs.";
    if (/white glue/i.test(title) && /titebond/i.test(title)) post = "Titebond " + post.charAt(0).toLowerCase() + post.slice(1);
    var grit = title.match(/(\d+)\s*grit/i);
    var pack = title.match(/(\d+)[ -]?pack|(?<![\d.])(\d+)\s*(?:count|ct\b|pk\b)/i);
    var count = pack ? (pack[1] || pack[2]) : "";
    var inches = title.match(/(\d+(?:\.\d+)?)\s*(?:in\.|inch(?:es)?|")/i);
    var drive = title.match(/torx\s*(?:#|t[- ]?)?(\d+)/i);
    if (/sandpaper|sand paper/i.test(title) && /roll/i.test(title)) {
      post = "Some " + (grit ? grit[1] + "-grit " : "") + "sandpaper on a roll.";
    } else if (/sanding discs?/i.test(title)) {
      post = (count ? count + " pack of " : "") + (inches ? inches[1] + " inch " : "") + "sanding discs" + (grit ? ", " + grit[1] + " grit" : "") + ".";
    } else if (/bits?/i.test(title) && drive) {
      post = (count ? count + " pack of " : "") + (inches ? inches[1] + " inch " : "") + (/bosch/i.test(title) ? "Bosch " : "") + "bits, T-" + drive[1] + ".";
    } else if (/mechanical pencils/i.test(title)) {
      post = (count ? count + " count pack of " : "") + "mechanical pencils";
      post += number(deal.current_price) > 0 && number(deal.current_price) <= 5 ? ", cheap enough to lose and not worry about it." : ", good to keep a few around the shop.";
    }
    var betterPrice = number(deal.drop_30_percent) >= 5;
    if (betterPrice && (/sandpaper|sand paper/i.test(title) && /roll/i.test(title))) {
      post = post.replace(/\.$/, "") + " at a better price than normal right now.";
    }
    if (post) post = post.charAt(0).toUpperCase() + post.slice(1);
    var knownBrands = ["Shop Fox", "Paper Mate", "Dura-Gold", "Bosch", "POWERTEC", "Bessey", "Titebond", "Freud", "WEN", "DeWalt", "Makita", "Milwaukee", "Lincoln", "Milescraft", "Pony", "CMT", "Forney", "ValueMax", "CASOMAN", "ALORAIR", "SKIL", "OLIGHT", "JET", "Rikon", "Ridgid", "Ryobi", "Metabo", "Irwin", "Kreg", "DMT", "Festool"];
    var brand = typeof deal.brand === "string" && deal.brand.trim().length <= 30 ? deal.brand.trim() : "";
    if (!brand) {
      for (var j = 0; j < knownBrands.length; j += 1) {
        if (title.toLowerCase().indexOf(knownBrands[j].toLowerCase() + " ") === 0) { brand = knownBrands[j]; break; }
      }
    }
    if (brand && post.toLowerCase().indexOf(brand.toLowerCase()) === -1) {
      post = post.replace(/^Some /, "");
      post = brand + " " + post.charAt(0).toLowerCase() + post.slice(1);
    }
    if (post.length > FACEBOOK_POST_MAX_LENGTH) post = post.split(/[.!?]\s/)[0].replace(/[.!?]$/, "") + ".";
    return post;

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

