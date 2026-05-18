(() => {
  const POSTED_DEALS_KEY = "keepa-dashboard-posted-asins";
  const POSTED_HIDE_FOR_HOURS = 72;
  const AMAZON_AFFILIATE_TAG = "simplewoodsho-20";

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

  function money(value) {
    const number = numericValue(value);
    if (number === null) return "N/A";
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(number);
  }

  function affiliateUrlForAsin(asin) {
    const cleanAsin = String(asin || "").trim();
    if (!cleanAsin) return "#";
    return `https://www.amazon.com/dp/${encodeURIComponent(cleanAsin)}?tag=${encodeURIComponent(AMAZON_AFFILIATE_TAG)}`;
  }

  function affiliateUrlForDeal(deal) {
    if (deal && deal.asin) return affiliateUrlForAsin(deal.asin);

    const rawUrl = String((deal && (deal.amazon_url || deal.url || deal.link)) || "").trim();
    if (!rawUrl) return "#";

    try {
      const url = new URL(rawUrl, window.location.href);
      const asinMatch = url.pathname.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/i);
      if (asinMatch) return affiliateUrlForAsin(asinMatch[1].toUpperCase());
      if (url.hostname.includes("amazon.")) {
        url.searchParams.set("tag", AMAZON_AFFILIATE_TAG);
        return url.toString();
      }
    } catch {}

    return rawUrl;
  }

  function parseCampaignDate(value) {
    const text = String(value || "").trim();
    if (!text) return null;

    const isoMatch = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (isoMatch) {
      return new Date(Number(isoMatch[1]), Number(isoMatch[2]) - 1, Number(isoMatch[3]));
    }

    const slashMatch = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2}|\d{4})$/);
    if (slashMatch) {
      let year = Number(slashMatch[3]);
      if (year < 100) year += 2000;
      return new Date(year, Number(slashMatch[1]) - 1, Number(slashMatch[2]));
    }

    const parsed = new Date(text);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function campaignDaysLeftText(campaign) {
    if (!campaign) return "";
    const endDate = parseCampaignDate(campaign.campaign_end_date);
    if (!endDate) return "";

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    endDate.setHours(0, 0, 0, 0);

    const daysLeft = Math.ceil((endDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
    if (!Number.isFinite(daysLeft)) return "";
    if (daysLeft < 0) return "campaign ended";
    if (daysLeft === 0) return "ends today";
    return `${daysLeft} day${daysLeft === 1 ? "" : "s"} left`;
  }

  function creatorCampaignText(deal) {
    const campaign = deal && deal.creator_campaign;
    if (!campaign && !(deal && deal.has_creator_campaign)) return "";

    const commission = (campaign && campaign.commission_rate) || deal.creator_commission_rate || "";
    const daysLeft = campaignDaysLeftText(campaign);
    const brand = campaign && campaign.campaign_brand;
    const name = campaign && campaign.campaign_name;
    const endDate = campaign && campaign.campaign_end_date;
    const parts = ["Creator campaign"];

    if (commission) parts.push(`${commission} commission`);
    if (daysLeft) parts.push(daysLeft);
    if (brand) parts.push(brand);

    return {
      label: parts.join(" - "),
      title: [name, endDate ? `Ends ${endDate}` : ""].filter(Boolean).join(" - ") || parts.join(" - "),
    };
  }

  function injectAffiliateStyles() {
    if (document.getElementById("affiliate-copy-card-styles")) return;

    const style = document.createElement("style");
    style.id = "affiliate-copy-card-styles";
    style.textContent = `
      .link-actions {
        display: grid;
        grid-template-columns: minmax(104px, 0.8fr) minmax(140px, 1.2fr);
        gap: 10px;
        margin-top: auto;
      }

      .copy-link-card {
        border: 1px solid #bbf7d0;
        border-radius: 14px;
        padding: 12px;
        background: white;
        color: #15803d;
        cursor: pointer;
        font-family: inherit;
        font-size: 0.86rem;
        font-weight: 800;
        white-space: nowrap;
      }

      .copy-link-card:hover,
      .copy-link-card.copied {
        background: #f0fdf4;
        color: #166534;
      }

      .link-actions .button {
        margin-top: 0;
      }

      .creator-campaign-badge {
        display: inline-flex;
        align-items: center;
        width: fit-content;
        max-width: 100%;
        border: 1px solid #fed7aa;
        border-radius: 999px;
        padding: 7px 10px;
        background: #fff7ed;
        color: #9a3412;
        font-size: 0.84rem;
        font-weight: 900;
        line-height: 1.2;
        white-space: normal;
      }
    `;
    document.head.appendChild(style);
  }

  window.copyAmazonAffiliateLink = async function copyAmazonAffiliateLink(asin, button) {
    const affiliateUrl = affiliateUrlForAsin(asin);

    try {
      await navigator.clipboard.writeText(affiliateUrl);
      if (button) {
        const originalText = button.textContent;
        button.textContent = "Copied";
        button.classList.add("copied");
        setTimeout(() => {
          button.textContent = originalText;
          button.classList.remove("copied");
        }, 1600);
      }
    } catch {
      prompt("Copy this affiliate link:", affiliateUrl);
    }
  };

  window.copySelectedLinks = async function copySelectedLinks() {
    const selectedAsins = typeof window.selectedForPostingAsins === "function" ? window.selectedForPostingAsins() : new Set();
    const visible = typeof window.visibleDeals === "function" ? window.visibleDeals() : [];
    const sorted = typeof window.sortDeals === "function" ? window.sortDeals(visible) : visible;
    const selectedDeals = sorted.filter((deal) => selectedAsins.has(deal.asin));

    if (selectedDeals.length === 0) {
      alert("No selected links to copy.");
      return;
    }

    const text = selectedDeals
      .map((deal) => `${deal.title}\n${affiliateUrlForDeal(deal)}`)
      .join("\n\n");

    try {
      await navigator.clipboard.writeText(text);
      alert(`Copied ${selectedDeals.length} selected link${selectedDeals.length === 1 ? "" : "s"}.`);
    } catch {
      prompt("Copy these selected links:", text);
    }
  };

  function fallbackDollarDrop(deal) {
    const currentPrice = numericValue(deal.current_price);
    const avg7Price = numericValue(deal.avg_7_price);

    if (currentPrice === null || avg7Price === null) return null;
    return Math.max(0, avg7Price - currentPrice);
  }

  function bestPriceDays(deal) {
    return numericValue(deal.best_price_days) || 0;
  }

  function enhancedDealScore(deal) {
    const dropPercent = numericValue(deal.drop_percent) || 0;
    const drop30Percent = numericValue(deal.drop_30_percent) || 0;
    const savings = fallbackDollarDrop(deal) || 0;
    const freshnessHours = hoursUntil(deal.expires_at);
    const freshnessBonus = freshnessHours === null ? 0 : Math.max(0, Math.min(24, freshnessHours)) / 24;
    const rarityBonus = Math.min(bestPriceDays(deal), 180) / 3;

    return (dropPercent * 2) + drop30Percent + Math.min(savings, 100) + freshnessBonus + rarityBonus;
  }

  function formatDealScore(deal) {
    return enhancedDealScore(deal).toFixed(1);
  }

  function bestPriceText(deal) {
    if (deal.best_price_message) return deal.best_price_message;

    const days = numericValue(deal.best_price_days);
    if (days === null) return "";

    return `best price in ${days} day${days === 1 ? "" : "s"}`;
  }

  function qualityLabel(deal) {
    const score = enhancedDealScore(deal);
    const days = bestPriceDays(deal);
    const drop = numericValue(deal.drop_percent) || 0;

    if (score >= 120 || (days >= 90 && drop >= 10)) return "Elite";
    if (score >= 80 || days >= 45) return "Strong";
    if (score >= 55 || days >= 14) return "Good";
    return "Watch";
  }

  function dealReason(deal) {
    const parts = [];
    const bestPrice = bestPriceText(deal);
    const drop = numericValue(deal.drop_percent);
    const drop30 = numericValue(deal.drop_30_percent);
    const savings = fallbackDollarDrop(deal);

    if (bestPrice) parts.push(bestPrice);
    if (drop !== null) parts.push(`${drop}% below 7-day avg`);
    if (drop30 !== null) parts.push(`${drop30}% below 30-day avg`);
    if (savings !== null && savings > 0) parts.push(`${money(savings)} drop`);

    return parts.slice(0, 4).join(" - ");
  }

  function readPostedMap() {
    try {
      const raw = JSON.parse(localStorage.getItem(POSTED_DEALS_KEY) || "{}");
      if (raw && typeof raw === "object" && !Array.isArray(raw)) return raw;
    } catch {}

    return {};
  }

  function writePostedMap(values) {
    localStorage.setItem(POSTED_DEALS_KEY, JSON.stringify(values));
  }

  function activePostedMap() {
    const posted = readPostedMap();
    const now = Date.now();
    const active = {};

    Object.entries(posted).forEach(([asin, hideUntil]) => {
      if (Number(hideUntil) > now) active[asin] = Number(hideUntil);
    });

    if (Object.keys(active).length !== Object.keys(posted).length) writePostedMap(active);
    return active;
  }

  function postedAsins() {
    return new Set(Object.keys(activePostedMap()));
  }

  window.postedDeal = function postedDeal(asin) {
    const posted = activePostedMap();
    posted[asin] = Date.now() + POSTED_HIDE_FOR_HOURS * 60 * 60 * 1000;
    writePostedMap(posted);

    if (typeof window.removeFromSelectedForPosting === "function") {
      window.removeFromSelectedForPosting(asin);
    }
    if (typeof window.applySearch === "function") {
      window.applySearch(false);
    }
  };

  window.resetPostedDeals = function resetPostedDeals() {
    localStorage.removeItem(POSTED_DEALS_KEY);
    if (typeof window.applySearch === "function") window.applySearch(false);
  };

  const originalVisibleDeals = window.visibleDeals;
  if (typeof originalVisibleDeals === "function") {
    window.visibleDeals = function visibleDealsWithPostedMemory() {
      const posted = postedAsins();
      return originalVisibleDeals().filter((deal) => !posted.has(deal.asin));
    };
  }

  const originalUpdateCounts = window.updateCounts;
  if (typeof originalUpdateCounts === "function") {
    window.updateCounts = function updateCountsWithPosted(renderedCount, selectedCount, totalMatchingCount) {
      originalUpdateCounts(renderedCount, selectedCount, totalMatchingCount);
      const postedCount = postedAsins().size;
      const dealCountEl = document.getElementById("dealCount");
      if (postedCount > 0 && dealCountEl) {
        dealCountEl.innerHTML += ` <button class="clear-posted" type="button" onclick="resetPostedDeals()">Show posted (${postedCount})</button>`;
      }
    };
  }

  window.dealScore = enhancedDealScore;

  const originalBuildCard = window.buildCard;
  if (typeof originalBuildCard === "function") {
    window.buildCard = function buildCardWithUxUpgrades(deal, isSelected, isSelectedSection) {
      injectAffiliateStyles();

      const card = originalBuildCard(deal, isSelected, isSelectedSection);
      const topRow = card.querySelector(".card-top-row");
      const affiliateUrl = affiliateUrlForDeal(deal);

      card.querySelectorAll(".image-wrap, .button").forEach((link) => {
        link.href = affiliateUrl;
      });

      const openButton = card.querySelector(".button");
      if (openButton && !card.querySelector(".copy-link-card")) {
        const actionWrap = document.createElement("div");
        actionWrap.className = "link-actions";

        const copyButton = document.createElement("button");
        copyButton.className = "copy-link-card";
        copyButton.type = "button";
        copyButton.textContent = "Copy Link";
        copyButton.addEventListener("click", () => window.copyAmazonAffiliateLink(deal.asin, copyButton));

        openButton.insertAdjacentElement("beforebegin", actionWrap);
        actionWrap.appendChild(copyButton);
        actionWrap.appendChild(openButton);
      }

      const campaignInfo = creatorCampaignText(deal);
      const asinLine = card.querySelector(".asin");
      if (campaignInfo && asinLine && !card.querySelector(".creator-campaign-badge")) {
        const campaignBadge = document.createElement("div");
        campaignBadge.className = "creator-campaign-badge";
        campaignBadge.textContent = campaignInfo.label;
        campaignBadge.title = campaignInfo.title;
        asinLine.insertAdjacentElement("afterend", campaignBadge);
      }

      if (!topRow) return card;

      let metrics = topRow.querySelector(".deal-metrics");
      if (!metrics) {
        metrics = document.createElement("div");
        metrics.className = "deal-metrics";

        const badge = topRow.querySelector(".badge");
        if (badge) metrics.appendChild(badge);

        topRow.insertBefore(metrics, topRow.firstChild);
      }

      if (!card.querySelector(".quality-badge")) {
        const label = qualityLabel(deal);
        const qualityBadge = document.createElement("span");
        qualityBadge.className = `quality-badge quality-${label.toLowerCase()}`;
        qualityBadge.textContent = label;
        metrics.insertBefore(qualityBadge, metrics.firstChild);
      }

      if (!card.querySelector(".score-badge")) {
        const scoreBadge = document.createElement("span");
        scoreBadge.className = "score-badge";
        scoreBadge.title = "Best deal score uses discount, dollar savings, freshness, and best-price age.";
        scoreBadge.innerHTML = `Deal score <strong>${formatDealScore(deal)}</strong>`;
        metrics.appendChild(scoreBadge);
      }

      const bestPrice = bestPriceText(deal);
      if (bestPrice && !card.querySelector(".best-price-badge")) {
        const bestPriceBadge = document.createElement("span");
        bestPriceBadge.className = "best-price-badge";
        bestPriceBadge.title = "How long it has been since Keepa history showed this ASIN at or below the current price.";
        bestPriceBadge.textContent = bestPrice;
        metrics.appendChild(bestPriceBadge);
      }

      const reason = dealReason(deal);
      const title = card.querySelector(".card-body h2");
      if (reason && title && !card.querySelector(".deal-reason")) {
        const reasonLine = document.createElement("p");
        reasonLine.className = "deal-reason";
        reasonLine.textContent = reason;
        title.insertAdjacentElement("afterend", reasonLine);
      }

      const postedButton = card.querySelector(".posted-hide-card");
      if (postedButton) {
        postedButton.textContent = `Posted - Hide ${POSTED_HIDE_FOR_HOURS}h`;
        postedButton.setAttribute("onclick", `postedDeal('${deal.asin}')`);
      }

      return card;
    };
  }

  async function renderScanHealth() {
    const updatedAtEl = document.getElementById("updatedAt");
    if (!updatedAtEl || updatedAtEl.querySelector(".scan-health")) return;

    try {
      const response = await fetch("data/deals.json", { cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();
      const scan = data.scan_window || {};
      const settings = data.settings || {};
      const tokenTest = data.token_test || {};
      const creatorConnections = data.creator_connections || {};
      const details = [];

      if (scan.scan_count && scan.total_asins) details.push(`scanned ${scan.scan_count} of ${scan.total_asins}`);
      if (scan.next_start_sheet_row) details.push(`next row ${scan.next_start_sheet_row}`);
      if (data.deal_count !== undefined) details.push(`${data.deal_count} active deals`);
      if (data.creator_campaign_deal_count !== undefined) details.push(`${data.creator_campaign_deal_count} creator campaigns`);
      if (settings.scan_limit) details.push(`${settings.scan_limit}/run`);
      if (tokenTest.estimated_tokens_for_run) details.push(`~${tokenTest.estimated_tokens_for_run} token estimate`);
      if (creatorConnections.asins_matched !== undefined) details.push(`${creatorConnections.asins_matched} campaign ASIN matches`);

      if (details.length) {
        updatedAtEl.innerHTML += `<br><span class="scan-health">${details.join(" - ")}</span>`;
      }
    } catch {}
  }

  setTimeout(renderScanHealth, 1000);
})();
