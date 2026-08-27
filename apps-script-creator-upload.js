// Add this upload action to the existing ASIN tools Google Apps Script web app.
// Store a GitHub fine-grained token in Script Properties as GITHUB_TOKEN.
// Token permissions: Contents read/write on Mhhickma/Dashboard.

const SHEET_NAME = "ASIN_List";
const START_ROW = 2;
const ASIN_RE = /\bB[0-9A-Z]{9}\b/g;
const CREATOR_CONNECTIONS_REPO = "Mhhickma/Dashboard";
const CREATOR_CONNECTIONS_BRANCH = "main";
const CREATOR_CONNECTIONS_UPLOAD_PATH = "data/creator-connections/latest.csv";

function parseAsinsFromText_(value) {
  const matches = String(value || "").toUpperCase().match(ASIN_RE) || [];
  const seen = {};
  const asins = [];

  matches.forEach((asin) => {
    if (seen[asin]) return;
    seen[asin] = true;
    asins.push(asin);
  });

  return asins;
}

function removeAsins_(asinText) {
  const asins = parseAsinsFromText_(asinText);
  if (!asins.length) {
    throw new Error("Missing ASIN.");
  }

  const asinLookup = {};
  asins.forEach((asin) => {
    asinLookup[asin] = true;
  });

  const sheet = SpreadsheetApp.getActive().getSheetByName(SHEET_NAME);
  if (!sheet) {
    throw new Error(`Missing sheet named ${SHEET_NAME}.`);
  }

  const lastRow = sheet.getLastRow();
  const lastColumn = sheet.getLastColumn();
  if (lastRow < START_ROW || lastColumn < 1) {
    return {
      ok: true,
      requested: asins.length,
      removed: 0,
      removed_asins: [],
      not_found: asins,
    };
  }

  const range = sheet.getRange(START_ROW, 1, lastRow - START_ROW + 1, lastColumn);
  const values = range.getValues();
  const removedLookup = {};
  let removedCells = 0;

  values.forEach((row) => {
    row.forEach((cell, columnIndex) => {
      const cellAsins = parseAsinsFromText_(cell);
      if (!cellAsins.length) return;

      if (cellAsins.some((asin) => asinLookup[asin])) {
        row[columnIndex] = "";
        removedCells += 1;
        cellAsins.forEach((asin) => {
          if (asinLookup[asin]) removedLookup[asin] = true;
        });
      }
    });
  });

  range.setValues(values);

  const removedAsins = asins.filter((asin) => removedLookup[asin]);
  const notFound = asins.filter((asin) => !removedLookup[asin]);

  return {
    ok: true,
    requested: asins.length,
    removed: removedAsins.length,
    removed_cells: removedCells,
    removed_asins: removedAsins,
    not_found: notFound,
  };
}

function removeAsin_(asinValue) {
  return removeAsins_(asinValue);
}

function normalizeCreatorCsv_(csvText) {
  return String(csvText || "")
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function mergeCreatorCsvText_(existingText, incomingText) {
  const existingLines = normalizeCreatorCsv_(existingText);
  const incomingLines = normalizeCreatorCsv_(incomingText);
  if (incomingLines.length === 0) {
    throw new Error("The uploaded CSV is empty.");
  }

  const header = existingLines[0] || incomingLines[0];
  const rows = [header];
  const seenRows = {};

  existingLines.slice(1).concat(incomingLines.slice(1)).forEach((line) => {
    if (!line || line === header || seenRows[line]) return;
    seenRows[line] = true;
    rows.push(line);
  });

  if (rows.length <= 1) {
    throw new Error("No creator connection rows were found in the uploaded CSV files.");
  }

  return `${rows.join("\n")}\n`;
}

function uploadCreatorCsv_(params) {
  const filename = String(params.filename || "creator-connections.csv").trim();
  const mergeMode = String(params.mergeMode || "replace").trim().toLowerCase();
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
  let existingText = "";
  const existing = UrlFetchApp.fetch(`${apiBase}?ref=${CREATOR_CONNECTIONS_BRANCH}`, {
    method: "get",
    headers,
    muteHttpExceptions: true,
  });
  if (existing.getResponseCode() === 200) {
    const existingPayload = JSON.parse(existing.getContentText());
    sha = existingPayload.sha || "";
    if (mergeMode === "append" && existingPayload.content) {
      existingText = Utilities.newBlob(
        Utilities.base64Decode(String(existingPayload.content).replace(/\s/g, ""))
      ).getDataAsString("UTF-8");
    }
  }

  const uploadText = mergeMode === "append" ? mergeCreatorCsvText_(existingText, decoded) : `${normalizeCreatorCsv_(decoded).join("\n")}\n`;

  const payload = {
    message: `${mergeMode === "append" ? "Merge" : "Replace"} Creator Connections CSV from dashboard upload: ${filename}`,
    content: Utilities.base64Encode(uploadText, Utilities.Charset.UTF_8),
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
    merge_mode: mergeMode,
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
    if (params.action === "removeAsin") {
      return creatorUploadResponse_(removeAsin_(params.asin));
    }
    if (params.action === "removeAsins") {
      return creatorUploadResponse_(removeAsins_(params.asins || params.asin));
    }
    return creatorUploadResponse_({ ok: false, error: "Unknown action." });
  } catch (error) {
    return creatorUploadResponse_({ ok: false, error: error.message });
  }
}

function doGet(e) {
  try {
    const params = e.parameter || {};
    const callback = String(params.callback || "").trim();
    let payload;

    if (params.action === "removeAsin") {
      payload = removeAsin_(params.asin);
    } else if (params.action === "removeAsins") {
      payload = removeAsins_(params.asins || params.asin);
    } else {
      payload = { ok: false, error: "Unknown action." };
    }

    const json = JSON.stringify(payload);
    if (callback) {
      return ContentService
        .createTextOutput(`${callback}(${json});`)
        .setMimeType(ContentService.MimeType.JAVASCRIPT);
    }

    return ContentService
      .createTextOutput(json)
      .setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    const callback = e && e.parameter ? String(e.parameter.callback || "").trim() : "";
    const json = JSON.stringify({ ok: false, error: error.message });
    if (callback) {
      return ContentService
        .createTextOutput(`${callback}(${json});`)
        .setMimeType(ContentService.MimeType.JAVASCRIPT);
    }

    return ContentService
      .createTextOutput(json)
      .setMimeType(ContentService.MimeType.JSON);
  }
}
