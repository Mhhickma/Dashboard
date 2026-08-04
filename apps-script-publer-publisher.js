// Add these helpers to the existing ASIN tools Google Apps Script web app.
// Keep secrets in Apps Script Project Settings > Script Properties.
//
// Required for Page publishing:
// PUBLER_API_KEY, AMAZON_ASSOCIATE_TAG
//
// Required for Group CSV queue:
// GITHUB_TOKEN
//
// Optional:
// JOTURL_API_URL, JOTURL_API_KEY, PUBLISH_MODE=draft|live
//
// Page targets use these optional properties:
// PUBLER_WOODWORKING_WORKSPACE_ID, PUBLER_WOODWORKING_PAGE_ACCOUNT_ID
// PUBLER_BLACK_LAB_WORKSPACE_ID, PUBLER_BLACK_LAB_PAGE_ACCOUNT_ID

const DASHBOARD_REPO = "Mhhickma/Dashboard";
const DASHBOARD_BRANCH = "main";
const PUBLER_TARGETS = {
  woodworkingGroup: {
    type: "publer",
    label: "Woodworking Page + Group",
    workspaceIdProperty: "PUBLER_WOODWORKING_GROUP_WORKSPACE_ID",
    accountIdProperty: "PUBLER_WOODWORKING_GROUP_ACCOUNT_ID",
    extraAccountIdProperties: ["PUBLER_WOODWORKING_PAGE_ACCOUNT_ID"],
    fallbackWorkspaceId: "6a2593fa88252f00b49d50b1",
    fallbackAccountId: "6a25940388252f00b49d51b1",
  },
  dadDealsGroup: {
    type: "groupCsv",
    label: "Dad Deals Group",
    csvPath: "data/publer_group_queue_dad_deals.csv",
  },
  woodworkingPage: {
    type: "page",
    label: "Woodworking Page",
    workspaceIdProperty: "PUBLER_WOODWORKING_WORKSPACE_ID",
    accountIdProperty: "PUBLER_WOODWORKING_PAGE_ACCOUNT_ID",
    fallbackWorkspaceId: "69ff46121fa916e7b4abad77",
  },
  blackLabPage: {
    type: "page",
    label: "Black Lab Page",
    workspaceIdProperty: "PUBLER_BLACK_LAB_WORKSPACE_ID",
    accountIdProperty: "PUBLER_BLACK_LAB_PAGE_ACCOUNT_ID",
    fallbackWorkspaceId: "69fa2708b5031ee6cc0cb0a8",
  },
  groupCsv: {
    type: "groupCsv",
    label: "Group CSV",
    csvPath: "data/publer_group_queue.csv",
  },
  page: {
    type: "page",
    label: "Page",
    workspaceIdProperty: "PUBLER_WORKSPACE_ID",
    accountIdProperty: "PUBLER_PAGE_ACCOUNT_ID",
  },
};

function publishDeal_(params) {
  const target = publerTarget_(params.target);
  const deal = normalizePublishDeal_(params);
  const scheduledFor = scheduledDate_(params.delayMinutes);
  const affiliateUrl = buildAmazonAffiliateUrl_(deal.asin);
  const dealUrl = buildJotUrlDeepLink_(affiliateUrl, deal);
  const postText = buildFacebookDealText_(deal);
  const commentText = buildFirstComment_(dealUrl);

  if (target.type === "page" || target.type === "publer") {
    return publishPublerPost_(target, deal, postText, commentText, scheduledFor, Number(params.delayMinutes || 0));
  }

  if (target.type === "groupCsv") {
    return appendPublerGroupCsv_(target, deal, postText, commentText, scheduledFor);
  }

  throw new Error("Unknown publish target.");
}

function publerTarget_(targetKey) {
  const key = String(targetKey || "").trim();
  const target = PUBLER_TARGETS[key];
  if (!target) throw new Error(`Unknown publish target: ${key || "(blank)"}.`);
  return {
    key,
    ...target,
  };
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
  const required = String(scriptProp_("JOTURL_REQUIRED", false) || "").toLowerCase() === "true";
  const cacheKey = `JOTURL_LINK_${String(deal.asin || "").toUpperCase()}`;
  const cached = scriptProp_(cacheKey, false);
  if (cached) return cached;

  try {
    const authHeader = scriptProp_("JOTURL_AUTH_HEADER", false) || "Authorization";
    const authPrefix = scriptProp_("JOTURL_AUTH_PREFIX", false) || "Bearer";
    const headers = {};
    headers[authHeader] = authPrefix ? `${authPrefix} ${apiKey}` : apiKey;

    const payload = {
      url: affiliateUrl,
      title: deal.title,
      alias: deal.asin.toLowerCase(),
      description: `Amazon affiliate link for ${deal.asin}`,
      deeplink: {
        auto: true,
      },
    };

    const domain = scriptProp_("JOTURL_DOMAIN", false);
    const campaign = scriptProp_("JOTURL_CAMPAIGN_ID", false);
    const channel = scriptProp_("JOTURL_CHANNEL_ID", false);
    if (domain) payload.domain = domain;
    if (campaign) payload.campaign = campaign;
    if (channel) payload.channel = channel;

    const response = UrlFetchApp.fetch(apiUrl, {
      method: "post",
      contentType: "application/json",
      headers,
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
    });

    const code = response.getResponseCode();
    const bodyText = response.getContentText();
    if (code < 200 || code >= 300) {
      throw new Error(`JotURL failed: ${code} ${bodyText}`);
    }

    const body = JSON.parse(bodyText);
    const url = extractJotUrl_(body);
    if (!url) throw new Error(`JotURL did not return a link: ${bodyText}`);
    PropertiesService.getScriptProperties().setProperty(cacheKey, url);
    return url;
  } catch (error) {
    if (required) throw error;
    return affiliateUrl;
  }
}

function extractJotUrl_(body) {
  return body.url ||
    body.short_url ||
    body.shortUrl ||
    body.shorturl ||
    body.short ||
    body.deep_link ||
    body.deepLink ||
    body.data?.url ||
    body.data?.short_url ||
    body.data?.shortUrl ||
    body.data?.shorturl ||
    body.data?.short ||
    body.data?.deep_link ||
    body.data?.deepLink ||
    "";
}

function buildFacebookDealText_(deal) {
  const title = shortenProductTitle_(deal.title, 125);
  const linkedBelow = "Worth a look for the shop. Linked below.";
  const casualFallback = "Worth a look for the shop.";
  const text = `${title}\n${linkedBelow}`;
  return text.length <= 180 ? text : `${title}\n${casualFallback}`;
}

function buildFirstComment_(dealUrl) {
  return `#ad ${dealUrl}`;
}

function publishPublerPost_(target, deal, postText, commentText, scheduledFor, delayMinutes) {
  const apiKey = scriptProp_("PUBLER_API_KEY", true);
  const workspaceId = scriptProp_(target.workspaceIdProperty, false) || target.fallbackWorkspaceId;
  const accountId = scriptProp_(target.accountIdProperty, false) || target.fallbackAccountId;
  const extraAccountIds = (target.extraAccountIdProperties || [])
    .map((name) => scriptProp_(name, false))
    .filter(Boolean)
    .filter((id, index, ids) => ids.indexOf(id) === index && id !== accountId);
  const publishMode = scriptProp_("PUBLISH_MODE", false) || "draft";
  if (!workspaceId) throw new Error(`Missing ${target.workspaceIdProperty} script property.`);
  if (!accountId) throw new Error(`Missing ${target.accountIdProperty} script property.`);
  preventDirectPublerDuplicate_(target, deal.asin);
  const adjustedScheduledFor = adjustedDirectPublerSchedule_(target, scheduledFor);
  const isImmediateLive = publishMode === "live" && delayMinutes === 0;
  const state = publishMode === "draft" ? "draft_private" : "scheduled";
  const endpoint = isImmediateLive
    ? "https://app.publer.com/api/v1/posts/schedule/publish"
    : "https://app.publer.com/api/v1/posts/schedule";

  const makeAccount = (id, includeComment) => {
    const account = {
      id,
    };

    if (includeComment) {
      account.comments = [{
          text: commentText,
          conditions: {
            relation: "AND",
            clauses: {
              age: {
                duration: 0,
                unit: "Minute",
              },
            },
          },
        }];
    }

    if (publishMode === "live" && delayMinutes > 0) {
      account.scheduled_at = adjustedScheduledFor.toISOString();
    }

    return account;
  };

  const posts = [];
  if (target.type === "publer") {
    posts.push({
      networks: {
        facebook: {
          type: "status",
          text: `${postText}\n\n${commentText}`,
        },
      },
      accounts: [makeAccount(accountId, false)],
    });

    if (extraAccountIds.length) {
      posts.push({
        networks: {
          facebook: {
            type: "status",
            text: postText,
          },
        },
        accounts: extraAccountIds.map((id) => makeAccount(id, true)),
      });
    }
  } else {
    posts.push({
      networks: {
        facebook: {
          type: "status",
          text: postText,
        },
      },
      accounts: [makeAccount(accountId, true)],
    });
  }

  const payload = {
    bulk: {
      state,
      posts,
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
  recordDirectPublerPost_(target, deal.asin, adjustedScheduledFor);
  return {
    ok: true,
    status: publishMode === "draft" ? "draft" : (delayMinutes > 0 ? "scheduled" : "published"),
    target: target.key,
    label: target.label,
    account_count: 1 + extraAccountIds.length,
    scheduled_for: delayMinutes > 0 ? adjustedScheduledFor.toISOString() : "",
    publer_job_id: body.data?.job_id || body.job_id || "",
    message: `${target.label} ${publishMode === "draft" ? "created as a Publer draft." : "sent to Publer."}`,
  };
}

function directPublerState_() {
  const raw = scriptProp_("PUBLER_DIRECT_POST_STATE", false) || "{}";
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (error) {
    return {};
  }
}

function writeDirectPublerState_(state) {
  PropertiesService.getScriptProperties().setProperty("PUBLER_DIRECT_POST_STATE", JSON.stringify(state));
}

function preventDirectPublerDuplicate_(target, asin) {
  const state = directPublerState_();
  const targetState = state[target.key] || {};
  const postedAsins = targetState.asins || {};
  if (postedAsins[String(asin || "").toUpperCase()]) {
    throw new Error(`${asin} was already sent to ${target.label}.`);
  }
}

function adjustedDirectPublerSchedule_(target, requestedDate) {
  const state = directPublerState_();
  const targetState = state[target.key] || {};
  const latestTime = Number(targetState.latestScheduledAt || 0);
  const minGapMs = 45 * 60 * 1000;
  const requestedTime = requestedDate.getTime();
  if (!latestTime || requestedTime >= latestTime + minGapMs) return requestedDate;
  return new Date(latestTime + minGapMs);
}

function recordDirectPublerPost_(target, asin, scheduledFor) {
  const state = directPublerState_();
  const targetState = state[target.key] || {};
  const postedAsins = targetState.asins || {};
  postedAsins[String(asin || "").toUpperCase()] = new Date().toISOString();
  targetState.asins = postedAsins;
  targetState.latestScheduledAt = Math.max(Number(targetState.latestScheduledAt || 0), scheduledFor.getTime());
  state[target.key] = targetState;
  writeDirectPublerState_(state);
}

function appendPublerGroupCsv_(target, deal, postText, commentText, scheduledFor) {
  const path = target.csvPath;
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

  const existing = readGithubTextFile_(DASHBOARD_REPO, path);
  if (csvAlreadyHasDeal_(existing.content, deal.asin)) {
    throw new Error(`${deal.asin} is already in ${path}.`);
  }

  const adjustedScheduledFor = adjustedGroupSchedule_(existing.content, scheduledFor);
  const row = [
    formatPublerCsvDate_(adjustedScheduledFor),
    postText,
    "",
    "",
    "",
    "Amazon Deals",
    deal.title,
    commentText,
    "",
    "",
    "",
    "",
  ];

  const csv = existing && existing.content
    ? `${existing.content.replace(/\s*$/, "\n")}${csvRow_(row)}\n`
    : `${csvRow_(headers)}\n${csvRow_(row)}\n`;

  writeGithubTextFile_(DASHBOARD_REPO, path, csv, existing.sha, `Add Publer group CSV row for ${deal.asin}`);

  return {
    ok: true,
    status: "queued",
    target: target.key,
    label: target.label,
    scheduled_for: adjustedScheduledFor.toISOString(),
    message: `${target.label} added to ${path}.`,
  };
}

function csvAlreadyHasDeal_(content, asin) {
  if (!content) return false;
  return String(content).toUpperCase().indexOf(String(asin || "").toUpperCase()) !== -1;
}

function adjustedGroupSchedule_(content, requestedDate) {
  const minGapMs = 45 * 60 * 1000;
  let latestTime = 0;

  if (content) {
    try {
      const rows = Utilities.parseCsv(content);
      rows.slice(1).forEach((row) => {
        const dateText = row && row[0] ? String(row[0]).trim() : "";
        const time = dateText ? new Date(dateText.replace(" ", "T")).getTime() : 0;
        if (Number.isFinite(time)) latestTime = Math.max(latestTime, time);
      });
    } catch (error) {
      latestTime = 0;
    }
  }

  const requestedTime = requestedDate.getTime();
  if (!latestTime || requestedTime >= latestTime + minGapMs) return requestedDate;
  return new Date(latestTime + minGapMs);
}

function readGithubTextFile_(repo, path) {
  const token = dashboardGithubToken_();
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
  const token = dashboardGithubToken_();
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

function dashboardGithubToken_() {
  return scriptProp_("DASHBOARD_GITHUB_TOKEN", false) || scriptProp_("GITHUB_TOKEN", true);
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

function shortenProductTitle_(value, maxLength) {
  const text = cleanText_(value)
    .replace(/\bAmazon(?:\.com)?\b/gi, "")
    .replace(/\b\d+(?:\.\d+)?\s*%\s*(?:off|discount|below)?\b/gi, "")
    .replace(/\$\s*\d+(?:\.\d{2})?\b/g, "")
    .replace(/\s+/g, " ")
    .replace(/[,:;\-\s]+$/, "")
    .trim();

  if (text.length <= maxLength) return text || "Shop find worth checking";
  const shortened = text.slice(0, maxLength + 1).replace(/\s+\S*$/, "").replace(/[,:;\-\s]+$/, "");
  return shortened || text.slice(0, maxLength).trim();
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
