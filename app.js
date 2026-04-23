const cardsEl = document.getElementById("cards");
const emptyStateEl = document.getElementById("emptyState");
const dealCountEl = document.getElementById("dealCount");
const updatedAtEl = document.getElementById("updatedAt");
const searchInput = document.getElementById("searchInput");

let allDeals = [];

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

function renderDeals(deals) {
  cardsEl.innerHTML = "";
  emptyStateEl.hidden = deals.length !== 0;

  deals.forEach((deal) => {
    const card = document.createElement("article");
    card.className = "card";

    card.innerHTML = `
      <div class="image-wrap">
        ${deal.image ? `<img src="${deal.image}" alt="${deal.title}" loading="lazy">` : `<strong>No Image</strong>`}
      </div>
      <div class="card-body">
        <span class="badge">${deal.drop_percent}% below 90-day average</span>
        <h2>${deal.title}</h2>
        <div class="asin">ASIN: ${deal.asin}</div>
        <div class="price-row">
          <div class="price-box">
            <span>Current</span>
            <strong>${money(deal.current_price)}</strong>
          </div>
          <div class="price-box">
            <span>90-Day Avg.</span>
            <strong>${money(deal.avg_90_price)}</strong>
          </div>
        </div>
        <div class="price-box">
          <span>90-Day Low</span>
          <strong>${money(deal.min_90_price)}</strong>
        </div>
        <a class="button" href="${deal.amazon_url}" target="_blank" rel="noopener noreferrer">Open on Amazon</a>
      </div>
    `;

    cardsEl.appendChild(card);
  });
}

function applySearch() {
  const term = searchInput.value.trim().toLowerCase();
  if (!term) {
    renderDeals(allDeals);
    return;
  }

  const filtered = allDeals.filter((deal) => {
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
    allDeals = data.deals || [];
    dealCountEl.textContent = `${allDeals.length} price drop${allDeals.length === 1 ? "" : "s"} found`;
    updatedAtEl.textContent = `Last updated: ${formatDate(data.updated_at)}`;
    renderDeals(allDeals);
  } catch (error) {
    dealCountEl.textContent = "Could not load deal data";
    updatedAtEl.textContent = error.message;
    emptyStateEl.hidden = false;
  }
}

searchInput.addEventListener("input", applySearch);
loadDeals();
