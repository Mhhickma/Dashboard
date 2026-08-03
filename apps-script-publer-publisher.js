// Add these helpers to the existing ASIN tools Google Apps Script web app.
// Keep secrets in Apps Script Project Settings > Script Properties.
//
// Required for Page publishing:
// PUBLER_API_KEY, PUBLER_WORKSPACE_ID, PUBLER_PAGE_ACCOUNT_ID, AMAZON_ASSOCIATE_TAG
//
// Required for Group CSV queue:
// GITHUB_TOKEN
//
// Optional:
// JOTURL_API_URL, JOTURL_API_KEY, PUBLISH_MODE=draft|live, GROUP_CSV_PATH

const DASHBOARD_REPO = "Mhhickma/Dashboard";
const DASHBOARD_BRANCH = "main";
const DEFAULT_GROUP_CSV_PATH = "data/publer_group_queue.csv";

function publishDeal_(params) {
  const target = String(params.target || "").trim();
  const deal = normalizePublishDeal_(params);
  const scheduledFor = scheduledDate_(params.delayMinutes);
  const affiliateUrl = buildAmazonAffiliateUrl_(deal.asin);
  const dealUrl = buildJotUrlDeepLink_(affiliateUrl, deal);
  const postText = buildFacebookDealText_(deal);
  const commentText = buildFirstComment_(dealUrl);

  if (target === "page") {
    return publishPublerPage_(deal, postText, commentText, scheduledFor, Number(params.delayMinutes || 0));
  }

  if (target === "groupCsv") {
    return appendPublerGroupCsv_(deal, postText, commentText, scheduledFor);
  }

  throw new Error("Unknown publish target.");
}

function normalizePublishDeal_(params) {
  const asin = String(params.asin || "").trim().toUpperCase();
  if (!/^[A-Z0-9]{10}$/.test(asin)) {
    throw new Error("Missing or invalid ASIN.");
  }

  return {
    asin,
    title: String(params.title || asin).trim(),
    current_price: Number(params.currentPrice || 0),
    avg_30_price: Number(params.avg30Price || 0),
    drop_30_percent: Number(params.drop30Percent || 0),
    amazon_url: String(params.amazonUrl || "").trim(),
    image_url: String(params.imageUrl || "").trim(),
  };
}

function scheduledDate_(delayMinutes) {
  const delay = Math.max(0, Number(delayMinutes || 0));
  return new Date(Date.now() + delay * 60 * 1000);
}

function buildAmazonAffiliateUrl_(asin) {
  const tag = scriptProp_("AMAZON_ASSOCIATE_TAG", true);
  return `https://www.amazon.com/dp/${encodeURIComponent(asin)}/?tag=${encodeURIComponent(tag)}`;
}

function buildJotUrlDeepLink_(affiliateUrl, deal) {
  const apiUrl = scriptProp_("JOTURL_API_URL", false);
  const apiKey = scriptProp_("JOTURL_API_KEY", false);
  if (!apiUrl || !apiKey) return affiliateUrl;

  const response = UrlFetchApp.fetch(apiUrl, {
    method: "post",
    contentType: "application/json",
    headers: {
      Authorization: `Bearer ${apiKey}`,
    },
    payload: JSON.stringify({
      url: affiliateUrl,
      title: deal.title,
      alias: deal.asin.toLowerCase(),
      app: "amazon",
      deep_link: true,
    }),
    muteHttpExceptions: true,
  });

  const code = response.getResponseCode();
  const bodyText = response.getContentText();
  if (code < 200 || code >= 300) {
    throw new Error(`JotURL failed: ${code} ${bodyText}`);
  }

  const body = JSON.parse(bodyText);
  const url = body.url || body.short_url || body.shortUrl || body.deep_link || body.deepLink || body.data?.url || body.data?.short_url;
  if (!url) {
    throw new Error("JotURL did not return a link.");
  }
  return url;
}

function buildFacebookDealText_(deal) {
  const parts = [
    "Deal alert",
    cleanText_(deal.title),
  ];

  if (deal.current_price > 0) {
    parts.push(`Now: ${formatUsd_(deal.current_price)}`);
  }
  if (deal.avg_30_price > 0) {
    parts.push(`30-day avg: ${formatUsd_(deal.avg_30_price)}`);
  }
  if (deal.drop_30_percent > 0) {
    parts.push(`${Math.round(deal.drop_30_percent)}% below 30-day average`);
  }

  parts.push("Price can change fast.");
  return parts.join("\n");
}

function buildFirstComment_(dealUrl) {
  return `Deal link: ${dealUrl}\n\nAs an Amazon Associate, I may earn from qualifying purchases.`;
}

function publishPublerPage_(deal, postText, commentText, scheduledFor, delayMinutes) {
  const apiKey = scriptProp_("PUBLER_API_KEY", true);
  const workspaceId = scriptProp_("PUBLER_WORKSPACE_ID", true);
  const accountId = scriptProp_("PUBLER_PAGE_ACCOUNT_ID", true);
  const publishMode = scriptProp_("PUBLISH_MODE", false) || "draft";
  const isImmediateLive = publishMode === "live" && delayMinutes === 0;
  const state = publishMode === "draft" ? "draft_private" : "scheduled";
  const endpoint = isImmediateLive
    ? "https://app.publer.com/api/v1/posts/schedule/publish"
    : "https://app.publer.com/api/v1/posts/schedule";

  const account = {
    id: accountId,
    comments: [
      {
        text: commentText,
      },
    ],
  };

  if (publishMode === "live" && delayMinutes > 0) {
    account.scheduled_at = scheduledFor.toISOString();
  }

  const facebook = {
    type: "status",
    text: postText,
  };

  const payload = {
    bulk: {
      state,
      posts: [
        {
          networks: {
            facebook,
          },
          accounts: [account],
        },
      ],
    },
  };

  const response = UrlFetchApp.fetch(endpoint, {
    method: "post",
    contentType: "application/json",
    headers: publerHeaders_(apiKey, workspaceId),
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });

  const code = response.getResponseCode();
  const bodyText = response.getContentText();
  if (code < 200 || code >= 300) {
    throw new Error(`Publer failed: ${code} ${bodyText}`);
  }

  const body = JSON.parse(bodyText);
  return {
    ok: true,
    status: publishMode === "draft" ? "draft" : (delayMinutes > 0 ? "scheduled" : "published"),
    scheduled_for: delayMinutes > 0 ? scheduledFor.toISOString() : "",
    publer_job_id: body.data?.job_id || body.job_id || "",
    message: publishMode === "draft" ? "created as a Publer draft." : "sent to Publer.",
  };
}

function appendPublerGroupCsv_(deal, postText, commentText, scheduledFor) {
  const path = scriptProp_("GROUP_CSV_PATH", false) || DEFAULT_GROUP_CSV_PATH;
  const headers = [
    "Date - Intl. format or prompt",
    "Text",
    "Link(s) - Separated by comma for FB carousels",
    "Media URL(s) - Separated by comma",
    "Title - For the video, pin, PDF ..",
    "Label(s) - Separated by comma",
    "Alt text(s) - Separated by ||",
    "Comment(s) - Separated by ||",
    "Pin board, FB album, or Google category",
    "Post subtype - I.e. story, reel, PDF ..",
    "CTA - For Facebook links or Google",
    "Reminder - For stories, reels, shorts, and TikToks",
  ];

  const row = [
    formatPublerCsvDate_(scheduledFor),
    postText,
    "",
    deal.image_url,
    "",
    "Amazon Deals",
    deal.title,
    commentText,
    "",
    "",
    "",
    "",
  ];

  const existing = readGithubTextFile_(DASHBOARD_REPO, path);
  const csv = existing && existing.content
    ? `${existing.content.replace(/\s*$/, "\n")}${csvRow_(row)}\n`
    : `${csvRow_(headers)}\n${csvRow_(row)}\n`;

  writeGithubTextFile_(DASHBOARD_REPO, path, csv, existing.sha, `Add Publer group CSV row for ${deal.asin}`);

  return {
    ok: true,
    status: "queued",
    scheduled_for: scheduledFor.toISOString(),
    message: `added to ${path}.`,
  };
}

function readGithubTextFile_(repo, path) {
  const token = scriptProp_("GITHUB_TOKEN", true);
  const response = UrlFetchApp.fetch(`https://api.github.com/repos/${repo}/contents/${path}?ref=${DASHBOARD_BRANCH}`, {
    method: "get",
    headers: githubHeaders_(token),
    muteHttpExceptions: true,
  });
  if (response.getResponseCode() === 404) return { content: "", sha: "" };
  if (response.getResponseCode() !== 200) {
    throw new Error(`GitHub read failed: ${response.getResponseCode()} ${response.getContentText()}`);
  }
  const body = JSON.parse(response.getContentText());
  return {
    content: Utilities.newBlob(Utilities.base64Decode(body.content)).getDataAsString("UTF-8"),
    sha: body.sha || "",
  };
}

function writeGithubTextFile_(repo, path, content, sha, message) {
  const token = scriptProp_("GITHUB_TOKEN", true);
  const payload = {
    message,
    content: Utilities.base64Encode(content, Utilities.Charset.UTF_8),
    branch: DASHBOARD_BRANCH,
  };
  if (sha) payload.sha = sha;

  const response = UrlFetchApp.fetch(`https://api.github.com/repos/${repo}/contents/${path}`, {
    method: "put",
    headers: githubHeaders_(token),
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });
  if (response.getResponseCode() < 200 || response.getResponseCode() >= 300) {
    throw new Error(`GitHub write failed: ${response.getResponseCode()} ${response.getContentText()}`);
  }
}

function publerHeaders_(apiKey, workspaceId) {
  return {
    Authorization: `Bearer-API ${apiKey}`,
    "Publer-Workspace-Id": workspaceId,
  };
}

function githubHeaders_(token) {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

function scriptProp_(name, required) {
  const value = PropertiesService.getScriptProperties().getProperty(name);
  if (required && !value) {
    throw new Error(`Missing ${name} script property.`);
  }
  return value;
}

function formatUsd_(value) {
  return `$${Number(value).toFixed(2)}`;
}

function formatPublerCsvDate_(date) {
  return Utilities.formatDate(date, Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm");
}

function cleanText_(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function csvRow_(values) {
  return values.map((value) => {
    const text = String(value || "");
    return `"${text.replace(/"/g, '""')}"`;
  }).join(",");
}

function jsonpResponse_(params, payload) {
  const callback = String(params.callback || "").trim();
  const json = JSON.stringify(payload);
  if (!callback) {
    return ContentService.createTextOutput(json).setMimeType(ContentService.MimeType.JSON);
  }
  return ContentService
    .createTextOutput(`${callback}(${json});`)
    .setMimeType(ContentService.MimeType.JAVASCRIPT);
}

// If your existing Apps Script already has doGet(e), merge this action branch into it.
function doGet(e) {
  const params = e.parameter || {};
  try {
    if (params.action === "publishDeal") {
      return jsonpResponse_(params, publishDeal_(params));
    }
    return jsonpResponse_(params, { ok: false, error: "Unknown action." });
  } catch (error) {
    return jsonpResponse_(params, { ok: false, error: error.message });
  }
}
