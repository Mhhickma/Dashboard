const cardsEl = document.getElementById("cards");
const selectedCardsEl = document.getElementById("selectedCards");
const selectedPostingSectionEl = document.getElementById("selectedPostingSection");
const selectedPostingCountEl = document.getElementById("selectedPostingCount");
const emptyStateEl = document.getElementById("emptyState");
const dealCountEl = document.getElementById("dealCount");
const updatedAtEl = document.getElementById("updatedAt");
const searchInput = document.getElementById("searchInput");
const sortSelect = document.getElementById("sortSelect");

const REMOVE_ASIN_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbyXILMe0WvnvjD0PMT4e6W7xvlnGePpN8HT2Dj0gsAXxT0dOh_9-4lXK9NTDw-yL5gTLg/exec";
const HIDDEN_DEALS_KEY = "keepa-dashboard-hidden-asins";
const REMOVE_QUEUE_KEY = "keepa-dashboard-remove-queue-asins";
const SELECTED_FOR_POSTING_KEY = "keepa-dashboard-selected-for-posting-asins";
const HIDE_FOR_HOURS = 24;
const DEALS_PER_PAGE = 50;

let allDeals = [];
let shownRegularDealLimit = DEALS_PER_PAGE;
let currentRenderedDeals = [];
let loadMoreSectionEl = null;
let loadMoreButtonEl = null;
let loadMoreSummaryEl = null;
let loadMoreButtonListenerAttached = false;

function ensureLoadMoreControls() {
  if (loadMoreSectionEl && loadMoreButtonEl && loadMoreSummaryEl) {
    return;
  }

  loadMoreSectionEl = document.getElementById("loadMoreSection");

  if (!loadMoreSectionEl) {
    loadMoreSectionEl = document.createElement("section");
    loadMoreSectionEl.id = "loadMoreSection";
    loadMoreSectionEl.className = "load-more-section";
    cardsEl.insertAdjacentElement("afterend", loadMoreSectionEl);
  }

  loadMoreSummaryEl = document.getElementById("loadMoreSummary");
  if (!loadMoreSummaryEl) {
    loadMoreSummaryEl = document.createElement("p");
    loadMoreSummaryEl.id = "loadMoreSummary";
    loadMoreSummaryEl.className = "load-more-summary";
    loadMoreSectionEl.appendChild(loadMoreSummaryEl);
  }

  loadMoreButtonEl = document.getElementById("loadMoreButton");
  if (!loadMoreButtonEl) {
    loadMoreButtonEl = document.createElement("button");
    loadMoreButtonEl.id = "loadMoreButton";
    loadMoreButtonEl.className = "load-more-button";
    loadMoreButtonEl.type = "button";
    loadMoreSectionEl.appendChild(loadMoreButtonEl);
  }

  if (!loadMoreButtonListenerAttached) {
    loadMoreButtonEl.addEventListener("click", loadMoreDeals);
    loadMoreButtonListenerAttached = true;
  }
}

function resetDealLimit() {
  shownRegularDealLimit = DEALS_PER_PAGE;
}

function loadMoreDeals() {
  shownRegularDealLimit += DEALS_PER_PAGE;
  renderDeals(currentRenderedDeals);
}

function updateLoadMoreControls(showingRegularCount, totalRegularCount) {
  ensureLoadMoreControls();

  const remainingCount = Math.max(0, totalRegularCount - showingRegularCount);
  loadMoreSectionEl.hidden = totalRegularCount <= DEALS_PER_PAGE || remainingCount === 0;
  loadMoreSummaryEl.textContent = `Showing ${showingRegularCount} of ${totalRegularCount} unselected deal${totalRegularCount === 1 ? "" : "s"}.`;
  loadMoreButtonEl.textContent = `Load ${Math.min(DEALS_PER_PAGE, remainingCount)} more deal${Math.min(DEALS_PER_PAGE, remainingCount) === 1 ? "" : "s"}`;
}

function readHiddenMap() {
  try {
    const raw = JSON.parse(localStorage.getItem(HIDDEN_DEALS_KEY) || "{}");

    if (Array.isArray(raw)) {
      const upgraded = {};
      const hideUntil = Date.now() + HIDE_FOR_HOURS * 60 * 60 * 1000;
      raw.forEach((asin) => {
        upgraded[asin] = hideUntil;
      });
      localStorage.setItem(HIDDEN_DEALS_KEY, JSON.stringify(upgraded));
      return upgraded;
    }

    if (raw && typeof raw === "object") return raw;
  } catch {}

  return {};
}

function writeHiddenMap(values) {
  localStorage.setItem(HIDDEN_DEALS_KEY, JSON.stringify(values));
}

function readSet(key) {
  try {
    return new Set(JSON.parse(localStorage.getItem(key) || "[]"));
  } catch {
    return new Set();
  }
}

function writeSet(key, values) {
  localStorage.setItem(key, JSON.stringify([...values]));
}

function activeHiddenMap() {
  const hidden = readHiddenMap();
  const now = Date.now();
  const active = {};

  Object.entries(hidden).forEach(([asin, hideUntil]) => {
    if (Number(hideUntil) > now) {
      active[asin] = Number(hideUntil);
    }
  });

  if (Object.keys(active).length !== Object.keys(hidden).length) {
    writeHiddenMap(active);
  }

  return active;
}

function hiddenAsins() {
  return new Set(Object.keys(activeHiddenMap()));
}

function removeQueueAsins() {
  return readSet(REMOVE_QUEUE_KEY);
}

function selectedForPostingAsins() {
  return readSet(SELECTED_FOR_POSTING_KEY);
}

function writeSelectedForPostingAsins(values) {
  writeSet(SELECTED_FOR_POSTING_KEY, values);
}

function toggleSelectedForPosting(asin) {
  const selected = selectedForPostingAsins();

  if (selected.has(asin)) {
    selected.delete(asin);
  } else {
    selected.add(asin);
  }

  writeSelectedForPostingAsins(selected);
  applySearch(false);
}

function removeFromSelectedForPosting(asin) {
  const selected = selectedForPostingAsins();
  if (!selected.has(asin)) return;

  selected.delete(asin);
  writeSelectedForPostingAsins(selected);
}

function hideDeal(asin) {
  const hidden = activeHiddenMap();
  hidden[asin] = Date.now() + HIDE_FOR_HOURS * 60 * 60 * 1000;
  writeHiddenMap(hidden);
  removeFromSelectedForPosting(asin);
  applySearch(false);
}

function removeAsinWithScript(asin) {
  return new Promise((resolve, reject) => {
    if (!REMOVE_ASIN_WEB_APP_URL || REMOVE_ASIN_WEB_APP_URL.includes("PASTE_YOUR_GOOGLE_APPS_SCRIPT_WEB_APP_URL_HERE")) {
      reject(new Error("Remove ASIN is not connected yet."));
      return;
    }

    const callbackName = `handleAsinRemoval_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    const script = document.createElement("script");
    const url = new URL(REMOVE_ASIN_WEB_APP_URL);
    let timeoutId = null;

    function cleanup() {
      if (timeoutId) clearTimeout(timeoutId);
      delete window[callbackName];
      script.remove();
    }

    window[callbackName] = (payload) => {
      cleanup();
      resolve(payload);
    };

    script.onerror = () => {
      cleanup();
      reject(new Error("Could not connect to the ASIN removal script."));
    };

    timeoutId = setTimeout(() => {
      cleanup();
      reject(new Error("The ASIN removal script did not respond."));
    }, 15000);

    url.searchParams.set("action", "removeAsin");
    url.searchParams.set("asin", asin);
    url.searchParams.set("callback", callbackName);
    script.src = url.toString();
    document.head.appendChild(script);
  });
}

async function queueRemoveDeal(asin) {
  const confirmRemove = confirm(`Remove ASIN ${asin} from the source sheet?`);
  if (!confirmRemove) return;

  try {
    const result = await removeAsinWithScript(asin);

    if (!result || !result.ok) {
      const message = result && result.error ? result.error : "The source sheet did not confirm removal.";
      alert(`Could not remove ${asin}: ${message}`);
      return;
    }

    hideDeal(asin);
    alert(`Removed ${asin} from ${result.sheet || "the source sheet"}.`);
  } catch (error) {
    const removeQueue = removeQueueAsins();
    removeQueue.add(asin);
    writeSet(REMOVE_QUEUE_KEY, removeQueue);
    removeFromSelectedForPosting(asin);
    applySearch(false);

    alert(`${error.message} ${asin} was queued locally instead. Use "Copy removals" at the top of the dashboard if you need to remove it manually.`);
  }
}

function resetHiddenDeals() {
  localStorage.removeItem(HIDDEN_DEALS_KEY);
  applySearch();
}

function clearSelectedForPosting() {
  localStorage.removeItem(SELECTED_FOR_POSTING_KEY);
  applySearch(false);
}

function clearRemoveQueue() {
  localStorage.removeItem(REMOVE_QUEUE_KEY);
  applySearch(false);
}

async function copyRemoveQueue() {
  const removeQueue = [...removeQueueAsins()].sort();
  if (removeQueue.length === 0) return;

  const text = removeQueue.join("\n");
  try {
    await navigator.clipboard.writeText(text);
    alert(`Copied ${removeQueue.length} ASIN${removeQueue.length === 1 ? "" : "s"} to remove.`);
  } catch {
    prompt("Copy these ASINs and remove them from the Google Sheet:", text);
  }
}

async function copySelectedLinks() {
  const selectedAsins = selectedForPostingAsins();
  const selectedDeals = sortDeals(visibleDeals()).filter((deal) => selectedAsins.has(deal.asin));

  if (selectedDeals.length === 0) {
    alert("No selected links to copy.");
    return;
  }

  const text = selectedDeals
    .map((deal) => `${deal.title}\n${deal.amazon_url}`)
    .join("\n\n");

  try {
    await navigator.clipboard.writeText(text);
    alert(`Copied ${selectedDeals.length} selected link${selectedDeals.length === 1 ? "" : "s"}.`);
  } catch {
    prompt("Copy these selected links:", text);
  }
}

function visibleDeals() {
  const hidden = hiddenAsins();
  const removeQueue = removeQueueAsins();
  return allDeals.filter((deal) => !hidden.has(deal.asin) && !removeQueue.has(deal.asin));
}

function money(value) {
  if (value === null || value === undefined) return "N/A";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

function formatDate(value) {
  if (!value) return "Not updated yet";
  return new Date(value).toLocaleString();
}

function formatShortDate(value) {
  if (!value) return "N/A";
  return new Date(value).toLocaleString([], {
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function numericValue(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function dateValue(value) {
  if (!value) return 0;
  const time = new Date(value).getTime();
  return Number.isFinite(time) ? time : 0;
}

function hoursUntil(value) {
  if (!value) return null;
  const diffMs = new Date(value).getTime() - Date.now();
  if (!Number.isFinite(diffMs)) return null;
  return Math.max(0, diffMs / (1000 * 60 * 60));
}

function compareNullableNumbers(aValue, bValue, direction = "desc") {
  const aNumber = numericValue(aValue);
  const bNumber = numericValue(bValue);

  if (aNumber === null && bNumber === null) return 0;
  if (aNumber === null) return 1;
  if (bNumber === null) return -1;

  return direction === "asc" ? aNumber - bNumber : bNumber - aNumber;
}

function dollarDrop(deal) {
  const currentPrice = numericValue(deal.current_price);
  const avg7Price = numericValue(deal.avg_7_price);

  if (currentPrice === null || avg7Price === null) return null;
  return Math.max(0, avg7Price - currentPrice);
}

function hasCreatorCampaign(deal) {
  return Boolean(
    deal && (
      deal.has_creator_campaign ||
      deal.creator_campaign ||
      deal.creator_commission_rate
    )
  );
}

function creatorCampaignEndDateValue(deal) {
  const campaign = deal && deal.creator_campaign;
  if (!campaign || !campaign.campaign_end_date) return Number.MAX_SAFE_INTEGER;
  const endTime = dateValue(campaign.campaign_end_date);
  return endTime || Number.MAX_SAFE_INTEGER;
}

function dealScore(deal) {
  const dropPercent = numericValue(deal.drop_percent) || 0;
  const drop30Percent = numericValue(deal.drop_30_percent) || 0;
  const savings = dollarDrop(deal) || 0;
  const freshnessHours = hoursUntil(deal.expires_at);
  const freshnessBonus = freshnessHours === null ? 0 : Math.max(0, Math.min(24, freshnessHours)) / 24;

  return (dropPercent * 2) + drop30Percent + Math.min(savings, 100) + freshnessBonus;
}

function compareText(aValue, bValue) {
  return String(aValue || "").localeCompare(String(bValue || ""), undefined, {
    numeric: true,
    sensitivity: "base",
  });
}

function postedDateValue(deal) {
  return dateValue(deal.posted_at || deal.first_seen_at || deal.checked_at);
}

function checkedDateValue(deal) {
  return dateValue(deal.last_checked_at || deal.checked_at);
}

function expiresDateValue(deal) {
  return dateValue(deal.expires_at);
}

function sortDeals(deals) {
  const sortMode = sortSelect ? sortSelect.value : "best-score";
  const sorted = [...deals];

  sorted.sort((a, b) => {
    if (sortMode === "best-score") {
      const scoreCompare = compareNullableNumbers(dealScore(a), dealScore(b));
      return scoreCompare || postedDateValue(b) - postedDateValue(a);
    }

    if (sortMode === "creator-first") {
      const creatorCompare = Number(hasCreatorCampaign(b)) - Number(hasCreatorCampaign(a));
      const endDateCompare = creatorCampaignEndDateValue(a) - creatorCampaignEndDateValue(b);
      const scoreCompare = compareNullableNumbers(dealScore(a), dealScore(b));
      return creatorCompare || endDateCompare || scoreCompare || postedDateValue(b) - postedDateValue(a);
    }

    if (sortMode === "newest-checked") {
      return checkedDateValue(b) - checkedDateValue(a);
    }

    if (sortMode === "expiring-soon") {
      return expiresDateValue(a) - expiresDateValue(b);
    }

    if (sortMode === "highest-drop") {
      return compareNullableNumbers(a.drop_percent, b.drop_percent);
    }

    if (sortMode === "highest-30-drop") {
      return compareNullableNumbers(a.drop_30_percent, b.drop_30_percent);
    }

    if (sortMode === "highest-dollar-drop") {
      return compareNullableNumbers(dollarDrop(a), dollarDrop(b));
    }

    if (sortMode === "lowest-price") {
      return compareNullableNumbers(a.current_price, b.current_price, "asc");
    }

    if (sortMode === "highest-price") {
      return compareNullableNumbers(a.current_price, b.current_price);
    }

    if (sortMode === "title-az") {
      return compareText(a.title, b.title);
    }

    if (sortMode === "asin-az") {
      return compareText(a.asin, b.asin);
    }

    return postedDateValue(b) - postedDateValue(a);
  });

  return sorted;
}

function imageCandidatesForDeal(deal) {
  const asin = deal.asin;
  const candidates = [];

  if (deal.image) candidates.push(deal.image);

  if (asin) {
    candidates.push(`https://images-na.ssl-images-amazon.com/images/P/${asin}.01._SL500_.jpg`);
    candidates.push(`https://m.media-amazon.com/images/P/${asin}.01._SL500_.jpg`);
    candidates.push(`https://images-na.ssl-images-amazon.com/images/P/${asin}.01.LZZZZZZZ.jpg`);
    candidates.push(`https://ws-na.amazon-adsystem.com/widgets/q?_encoding=UTF8&MarketPlace=US&ASIN=${asin}&ServiceVersion=20070822&ID=AsinImage&WS=1&Format=_SL500_`);
  }

  return [...new Set(candidates.filter(Boolean))];
}

function buildImageMarkup(deal) {
  const candidates = imageCandidatesForDeal(deal);
  const encodedCandidates = encodeURIComponent(JSON.stringify(candidates));
  const firstImage = candidates[0] || "";

  if (!firstImage) return "";

  return `<img
    src="${firstImage}"
    alt="${deal.title}"
    loading="lazy"
    data-image-index="0"
    data-image-candidates="${encodedCandidates}"
    onerror="tryNextImage(this)"
  >`;
}

function tryNextImage(img) {
  const wrap = img.closest(".image-wrap");
  const candidates = JSON.parse(decodeURIComponent(img.dataset.imageCandidates || "%5B%5D"));
  const currentIndex = Number(img.dataset.imageIndex || 0);
  const nextIndex = currentIndex + 1;

  if (nextIndex < candidates.length) {
    img.dataset.imageIndex = String(nextIndex);
    img.src = candidates[nextIndex];
    return;
  }

  wrap.classList.add("image-missing");
  img.remove();
}

function updateCounts(renderedCount, selectedCount, totalMatchingCount) {
  const hiddenCount = hiddenAsins().size;
  const removeCount = removeQueueAsins().size;
  const totalCount = allDeals.length;

  dealCountEl.innerHTML = `${renderedCount} shown of ${totalMatchingCount} visible active deal${totalMatchingCount === 1 ? "" : "s"}`;

  if (selectedCount > 0) {
    dealCountEl.innerHTML += ` <span class="count-note">${selectedCount} selected for posting</span>`;
    dealCountEl.innerHTML += ` <button class="copy-selected" type="button" onclick="copySelectedLinks()">Copy selected links</button>`;
  }

  if (totalCount !== totalMatchingCount) {
    dealCountEl.innerHTML += ` <span class="count-note">${totalCount} total active</span>`;
  }

  if (hiddenCount > 0) {
    dealCountEl.innerHTML += ` <button class="reset-hidden" type="button" onclick="resetHiddenDeals()">Show hidden (${hiddenCount})</button>`;
  }

  if (selectedCount > 0) {
    dealCountEl.innerHTML += ` <button class="clear-selected" type="button" onclick="clearSelectedForPosting()">Clear selected</button>`;
  }

  if (removeCount > 0) {
    dealCountEl.innerHTML += ` <button class="copy-remove" type="button" onclick="copyRemoveQueue()">Copy removals (${removeCount})</button>`;
    dealCountEl.innerHTML += ` <button class="clear-remove" type="button" onclick="clearRemoveQueue()">Clear removals</button>`;
  }
}

function buildCard(deal, isSelected, isSelectedSection) {
  const card = document.createElement("article");
  card.className = isSelected ? "card selected-card" : "card";
  const postedAt = deal.posted_at || deal.first_seen_at || deal.checked_at;
  const expiresAt = deal.expires_at;
  const hoursLeft = hoursUntil(expiresAt);
  const expiresText = hoursLeft === null ? "N/A" : `${hoursLeft.toFixed(1)} hrs left`;

  const selectedPostingTools = isSelectedSection ? `
    <div class="posting-helper-box">
      <p>Make the link, post it, then hide this card.</p>
      <button class="posted-hide-card" type="button" onclick="hideDeal('${deal.asin}')">Posted â€” Hide Card</button>
    </div>
  ` : "";

  card.innerHTML = `
    <div class="select-posting-row">
      <label class="select-posting-control">
        <input type="checkbox" ${isSelected ? "checked" : ""} onchange="toggleSelectedForPosting('${deal.asin}')">
        <span>Select for posting</span>
      </label>
      ${isSelected ? `<span class="selected-pill">Selected</span>` : ""}
    </div>
    <a class="image-wrap" href="${deal.amazon_url}" target="_blank" rel="noopener noreferrer" aria-label="Open ${deal.title} on Amazon">
      ${buildImageMarkup(deal)}
      <div class="image-placeholder">
        <span>No image available</span>
        <small>${deal.asin}</small>
      </div>
    </a>
    <div class="card-body">
      <div class="card-top-row">
        <span class="badge">${deal.drop_30_percent}% below 30-day average</span>
        <div class="card-actions">
          <button class="hide-card" type="button" onclick="hideDeal('${deal.asin}')">Hide 24h</button>
          <button class="remove-card" type="button" onclick="queueRemoveDeal('${deal.asin}')">Remove ASIN</button>
        </div>
      </div>
      <div class="deal-time">
        <span>Posted: ${formatShortDate(postedAt)}</span>
        <span>${expiresText}</span>
      </div>
      <h2>${deal.title}</h2>
      <div class="asin">ASIN: ${deal.asin}</div>
      <div class="price-row">
        <div class="price-box">
          <span>Current</span>
          <strong>${money(deal.current_price)}</strong>
        </div>
        <div class="price-box">
          <span>7-Day Avg.</span>
          <strong>${money(deal.avg_7_price)}</strong>
        </div>
      </div>
      <div class="price-row">
        <div class="price-box">
          <span>30-Day Avg.</span>
          <strong>${money(deal.avg_30_price)}</strong>
        </div>
        <div class="price-box">
          <span>30-Day Drop</span>
          <strong>${deal.drop_30_percent === null || deal.drop_30_percent === undefined ? "N/A" : `${deal.drop_30_percent}%`}</strong>
        </div>
      </div>
      <div class="price-box">
        <span>7-Day Low</span>
        <strong>${money(deal.min_7_price)}</strong>
      </div>
      ${selectedPostingTools}
      <a class="button" href="${deal.amazon_url}" target="_blank" rel="noopener noreferrer">Open on Amazon</a>
    </div>
  `;

  return card;
}

function renderDeals(deals) {
  currentRenderedDeals = deals;

  const selectedAsins = selectedForPostingAsins();
  const selectedDeals = deals.filter((deal) => selectedAsins.has(deal.asin));
  const regularDeals = deals.filter((deal) => !selectedAsins.has(deal.asin));
  const visibleRegularDeals = regularDeals.slice(0, shownRegularDealLimit);

  cardsEl.innerHTML = "";
  selectedCardsEl.innerHTML = "";

  const totalRendered = selectedDeals.length + visibleRegularDeals.length;
  emptyStateEl.hidden = totalRendered !== 0;
  updateCounts(totalRendered, selectedDeals.length, deals.length);

  selectedPostingSectionEl.hidden = selectedDeals.length === 0;
  selectedPostingCountEl.textContent = `${selectedDeals.length} selected`;

  selectedDeals.forEach((deal) => {
    selectedCardsEl.appendChild(buildCard(deal, true, true));
  });

  visibleRegularDeals.forEach((deal) => {
    cardsEl.appendChild(buildCard(deal, false, false));
  });

  updateLoadMoreControls(visibleRegularDeals.length, regularDeals.length);
}

function applySearch(resetLimit = true) {
  if (resetLimit) {
    resetDealLimit();
  }

  const term = searchInput.value.trim().toLowerCase();
  const baseDeals = sortDeals(visibleDeals());

  if (!term) {
    renderDeals(baseDeals);
    return;
  }

  const filtered = baseDeals.filter((deal) => {
    return (
      deal.title.toLowerCase().includes(term) ||
      deal.asin.toLowerCase().includes(term)
    );
  });

  renderDeals(filtered);
}

async function loadDeals() {
  try {
    const response = await fetch("data/deals.json", { cache: "no-store" });
    if (!response.ok) throw new Error("Could not load deals.json");

    const data = await response.json();
    const creatorConnections = data.creator_connections || {};
    const creatorUpdatedAt = creatorConnections.latest_csv_updated_at
      ? ` - Creator CSV: ${formatDate(creatorConnections.latest_csv_updated_at)}`
      : "";
    allDeals = data.deals || [];
    updatedAtEl.textContent = `Last updated: ${formatDate(data.updated_at)} - Deals kept for ${data.deal_ttl_hours || 24} hours${creatorUpdatedAt}`;
    applySearch();
  } catch (error) {
    dealCountEl.textContent = "Could not load deal data";
    updatedAtEl.textContent = error.message;
    emptyStateEl.hidden = false;
  }
}

searchInput.addEventListener("input", () => applySearch());
if (sortSelect) sortSelect.addEventListener("change", () => applySearch());
loadDeals();

