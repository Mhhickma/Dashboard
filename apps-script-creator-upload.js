// Add this upload action to the existing ASIN tools Google Apps Script web app.
// Store a GitHub fine-grained token in Script Properties as GITHUB_TOKEN.
// Token permissions: Contents read/write on Mhhickma/influencer-prospects.

const CREATOR_CONNECTIONS_REPO = "Mhhickma/influencer-prospects";
const CREATOR_CONNECTIONS_BRANCH = "main";
const CREATOR_CONNECTIONS_UPLOAD_PATH = "creator-connections/latest.csv";

function uploadCreatorCsv_(params) {
  const filename = String(params.filename || "creator-connections.csv").trim();
  const csvBase64 = String(params.csvBase64 || "").trim();
  if (!csvBase64) {
    throw new Error("Missing CSV content.");
  }

  const token = PropertiesService.getScriptProperties().getProperty("GITHUB_TOKEN");
  if (!token) {
    throw new Error("Missing GITHUB_TOKEN script property.");
  }

  const decoded = Utilities.newBlob(Utilities.base64Decode(csvBase64)).getDataAsString("UTF-8");
  if (!decoded || decoded.indexOf("ASIN") === -1) {
    throw new Error("The uploaded file does not look like a Creator Connections CSV.");
  }

  const apiBase = `https://api.github.com/repos/${CREATOR_CONNECTIONS_REPO}/contents/${CREATOR_CONNECTIONS_UPLOAD_PATH}`;
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };

  let sha = "";
  const existing = UrlFetchApp.fetch(`${apiBase}?ref=${CREATOR_CONNECTIONS_BRANCH}`, {
    method: "get",
    headers,
    muteHttpExceptions: true,
  });
  if (existing.getResponseCode() === 200) {
    sha = JSON.parse(existing.getContentText()).sha || "";
  }

  const payload = {
    message: `Replace Creator Connections CSV from dashboard upload: ${filename}`,
    content: Utilities.base64Encode(decoded, Utilities.Charset.UTF_8),
    branch: CREATOR_CONNECTIONS_BRANCH,
  };
  if (sha) {
    payload.sha = sha;
  }

  const saved = UrlFetchApp.fetch(apiBase, {
    method: "put",
    headers,
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });

  const code = saved.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error(`GitHub save failed: ${code} ${saved.getContentText()}`);
  }

  return {
    ok: true,
    file: CREATOR_CONNECTIONS_UPLOAD_PATH,
    source_filename: filename,
  };
}

function creatorUploadResponse_(payload) {
  return HtmlService.createHtmlOutput(
    `<script>document.body.textContent=${JSON.stringify(JSON.stringify(payload))};</script>`
  );
}

function doPost(e) {
  try {
    const params = e.parameter || {};
    if (params.action === "uploadCreatorCsv") {
      return creatorUploadResponse_(uploadCreatorCsv_(params));
    }
    return creatorUploadResponse_({ ok: false, error: "Unknown action." });
  } catch (error) {
    return creatorUploadResponse_({ ok: false, error: error.message });
  }
}
