(() => {
  let creatorCampaignOnly = false;
  let creatorCampaignCount = 0;

  function hasCreatorCampaign(deal) {
    return Boolean(
      deal && (
        deal.has_creator_campaign ||
        deal.creator_campaign ||
        deal.creator_commission_rate
      )
    );
  }

  function updateButtonState(button) {
    button.classList.toggle("active", creatorCampaignOnly);
    button.setAttribute("aria-pressed", creatorCampaignOnly ? "true" : "false");

    if (creatorCampaignOnly) {
      button.textContent = "Show All Deals";
      return;
    }

    button.textContent = creatorCampaignCount > 0
      ? `Creator Campaigns (${creatorCampaignCount})`
      : "Creator Campaigns";
  }

  function applyCreatorCampaignFilter(button) {
    creatorCampaignOnly = !creatorCampaignOnly;
    updateButtonState(button);

    if (typeof window.applySearch === "function") {
      window.applySearch();
    }
  }

  function injectCreatorFilterStyles() {
    if (document.getElementById("creator-campaign-filter-styles")) return;

    const style = document.createElement("style");
    style.id = "creator-campaign-filter-styles";
    style.textContent = `
      .creator-campaign-filter-button {
        border: 1px solid #fed7aa;
        border-radius: 12px;
        padding: 11px 14px;
        background: #fff7ed;
        color: #9a3412;
        cursor: pointer;
        font-family: inherit;
        font-size: 0.9rem;
        font-weight: 900;
        white-space: nowrap;
      }

      .creator-campaign-filter-button:hover,
      .creator-campaign-filter-button.active {
        background: #ffedd5;
        color: #7c2d12;
      }
    `;
    document.head.appendChild(style);
  }

  function ensureCreatorCampaignFilterButton() {
    const toolbarControls = document.querySelector(".toolbar-controls");
    if (!toolbarControls || document.getElementById("creatorCampaignFilter")) return;

    injectCreatorFilterStyles();

    const button = document.createElement("button");
    button.id = "creatorCampaignFilter";
    button.className = "creator-campaign-filter-button";
    button.type = "button";
    button.setAttribute("aria-pressed", "false");
    button.textContent = "Creator Campaigns";
    button.addEventListener("click", () => applyCreatorCampaignFilter(button));

    const searchInput = document.getElementById("searchInput");
    if (searchInput) {
      searchInput.insertAdjacentElement("beforebegin", button);
    } else {
      toolbarControls.appendChild(button);
    }

    fetch("data/deals.json", { cache: "no-store" })
      .then((response) => response.ok ? response.json() : null)
      .then((data) => {
        if (!data || !Array.isArray(data.deals)) return;
        creatorCampaignCount = data.deals.filter(hasCreatorCampaign).length;
        updateButtonState(button);
      })
      .catch(() => {});
  }

  const originalVisibleDeals = window.visibleDeals;
  if (typeof originalVisibleDeals === "function") {
    window.visibleDeals = function visibleDealsWithCreatorCampaignFilter() {
      const deals = originalVisibleDeals();
      if (!creatorCampaignOnly) return deals;
      return deals.filter(hasCreatorCampaign);
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ensureCreatorCampaignFilterButton);
  } else {
    ensureCreatorCampaignFilterButton();
  }
})();
