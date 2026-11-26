/**
 * RiverScan email service: Google Apps Script, runs free in your own Google account.
 *
 * What it does
 *   1. Someone signs up on riverscan.com -> they're saved to the "Subscribers" sheet
 *      and sent a welcome email straight away. You get a copy.
 *   2. Every Friday the GitHub workflow sends the weekly digest here -> it's emailed
 *      to every subscriber (each with their own unsubscribe link). You get a copy.
 *   3. Unsubscribe links mark the person as unsubscribed in the sheet.
 *
 * Setup: see SETUP-EMAIL.md in the repo. You need to set two Script Properties:
 *   TOKEN       = a long random password (the same value goes in the GitHub secret SIGNUP_TOKEN)
 *   OWNER_EMAIL = the address that gets a copy of every email
 */

// Your address for copies of every email lives in a Script Property (OWNER_EMAIL), not here,
// because this file is in a public repository.
var OWNER_EMAIL = PropertiesService.getScriptProperties().getProperty("OWNER_EMAIL");
var SITE = "https://riverscan.com";
var FROM_NAME = "RiverScan";
var DISCLAIMER = "RiverScan is a data analytics company. It reports changes in public records for information only. It is not investment advice.";

function token_() {
  return PropertiesService.getScriptProperties().getProperty("TOKEN") || "";
}

function sheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName("Subscribers");
  if (!sh) {
    sh = ss.insertSheet("Subscribers");
    sh.appendRow(["email", "signed_up", "status", "source"]);
  }
  return sh;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function sig_(email) {
  var raw = Utilities.computeHmacSha256Signature(email.toLowerCase(), token_());
  return Utilities.base64EncodeWebSafe(raw).replace(/=+$/, "").slice(0, 22);
}

function unsubscribeLink_(email) {
  return ScriptApp.getService().getUrl() + "?unsubscribe=" + encodeURIComponent(email) + "&sig=" + sig_(email);
}

function footer_(email) {
  return '<p style="font-family:Helvetica,Arial,sans-serif;color:#999;font-size:11px;line-height:1.5;margin-top:28px">' +
    "You're receiving this because you signed up at riverscan.com. " +
    '<a href="' + unsubscribeLink_(email) + '" style="color:#999">Unsubscribe</a>.<br>' + DISCLAIMER + "</p>";
}

function wrap_(inner) {
  return '<div style="font-family:Georgia,\'Times New Roman\',serif;font-size:16px;max-width:600px;color:#222;line-height:1.55">' + inner + "</div>";
}

/** Sign-ups (form posts) and the weekly digest (JSON with the token). */
function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    if (e.postData && e.postData.type === "application/json") {
      var body = JSON.parse(e.postData.contents || "{}");
      if (body.action === "digest") return sendDigest_(body);
      return json_({ ok: false, error: "unknown action" });
    }
    return signup_(e.parameter || {});
  } finally {
    lock.releaseLock();
  }
}

function signup_(p) {
  if (p._gotcha) return json_({ ok: true });  // spam trap filled in: pretend it worked
  var email = String(p.email || "").trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return json_({ ok: false, error: "invalid email" });
  var sh = sheet_(), rows = sh.getDataRange().getValues();
  for (var i = 1; i < rows.length; i++) {
    if (String(rows[i][0]).toLowerCase() === email) {
      if (rows[i][2] === "active") return json_({ ok: true, existing: true });
      sh.getRange(i + 1, 3).setValue("active");  // re-subscribing
      sendWelcome_(email);
      return json_({ ok: true, resubscribed: true });
    }
  }
  sh.appendRow([email, new Date(), "active", p.source || "website"]);
  sendWelcome_(email);
  return json_({ ok: true });
}

function latestSignals_() {
  try {
    var res = UrlFetchApp.fetch(SITE + "/data/signals.json", { muteHttpExceptions: true });
    var all = JSON.parse(res.getContentText());
    return all.filter(function (s) { return s.severity !== "low"; }).slice(-3).reverse();
  } catch (err) {
    return [];
  }
}

function sendWelcome_(email) {
  var sigs = latestSignals_();
  var list = sigs.length ? "<p>Three recent ones:</p>" + sigs.map(function (s) {
    return '<p style="margin:0 0 10px"><strong>' + s.company + "</strong>. " + s.note + '. <a href="' + s.url + '" style="color:#0F5F59">Source</a></p>';
  }).join("") : "";
  var html = wrap_(
    '<p style="font-family:Helvetica,Arial,sans-serif;font-size:20px;font-weight:bold;color:#111;border-bottom:3px solid #111;padding-bottom:12px">RiverScan</p>' +
    "<p>Thanks for signing up.</p>" +
    "<p>Each morning we read clinical trial registries and UK government contract awards, and note what changed for London-listed companies worth under £1bn. Those are the companies few analysts follow, so the news can take a while to reach the share price.</p>" +
    "<p>The weekly email arrives on Fridays. In the meantime, everything we've logged is on the site: " +
    '<a href="' + SITE + '/signals.html" style="color:#0F5F59">riverscan.com/signals</a>.</p>' +
    list + footer_(email));
  var subject = "You're on the RiverScan list";
  MailApp.sendEmail({ to: email, subject: subject, htmlBody: html, name: FROM_NAME });
  MailApp.sendEmail({ to: OWNER_EMAIL, subject: "[Copy] " + subject + " — new sign-up: " + email,
                      htmlBody: wrap_("<p><strong>New sign-up:</strong> " + email + "</p><hr>") + html, name: FROM_NAME });
}

function sendDigest_(body) {
  if (!token_() || body.token !== token_()) return json_({ ok: false, error: "bad token" });
  var rows = sheet_().getDataRange().getValues(), sent = 0;
  for (var i = 1; i < rows.length; i++) {
    if (rows[i][2] !== "active") continue;
    var email = String(rows[i][0]);
    MailApp.sendEmail({ to: email, subject: body.subject, htmlBody: wrap_(body.html + footer_(email)),
                        body: (body.text || "") + "\n\nUnsubscribe: " + unsubscribeLink_(email), name: FROM_NAME });
    sent++;
  }
  MailApp.sendEmail({ to: OWNER_EMAIL, subject: "[Copy] " + body.subject + " (sent to " + sent + " subscribers)",
                      htmlBody: wrap_(body.html + footer_(OWNER_EMAIL)), name: FROM_NAME });
  return json_({ ok: true, sent: sent, quota_left: MailApp.getRemainingDailyQuota() });
}

/** Unsubscribe links. */
function doGet(e) {
  var p = e.parameter || {};
  var msg = "Nothing to do here.";
  if (p.unsubscribe) {
    var email = String(p.unsubscribe).toLowerCase();
    if (p.sig === sig_(email)) {
      var sh = sheet_(), rows = sh.getDataRange().getValues();
      for (var i = 1; i < rows.length; i++) {
        if (String(rows[i][0]).toLowerCase() === email) sh.getRange(i + 1, 3).setValue("unsubscribed");
      }
      msg = "You've been unsubscribed from RiverScan emails. Sorry to see you go.";
    } else {
      msg = "That unsubscribe link isn't valid. Reply to any RiverScan email and we'll remove you.";
    }
  }
  return HtmlService.createHtmlOutput(wrap_("<h2>RiverScan</h2><p>" + msg + '</p><p><a href="' + SITE + '">Back to riverscan.com</a></p>'));
}

/** Run this once from the editor to check it works: it emails you a test welcome. */
function testWelcome() {
  sendWelcome_(OWNER_EMAIL);
}
