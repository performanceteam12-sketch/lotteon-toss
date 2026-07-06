/**
 * 토스update → 토스업로드 자동 업데이트 Google Apps Script
 *
 * 설치 방법:
 * 1. 해당 구글 시트 > 확장 프로그램 > Apps Script
 * 2. 이 코드를 붙여넣고 저장
 * 3. setupDailyTrigger() 함수를 한 번 실행 (매일 오전 10시 트리거 등록)
 */

// ── 설정 ──────────────────────────────────────────
var SOURCE_SHEET = "토스update";
var TARGET_SHEET = "토스업로드";
var SLACK_WEBHOOK_URL = "https://hooks.slack.com/triggers/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";
var SLACK_EMAIL = "x-aaaatxo5yffjiqwaynov33b5re@madupteam.slack.com";  // 폴백용
// Streamlit Cloud 배포 URL
var STREAMLIT_URL = "https://lotteon-toss-update.streamlit.app";

// ── 비용 계산 (클릭 기반 구간별) ───────────────────
// - 10,000 미만: 클릭 x 10
// - 1만 단위 블록 안 나머지 < 5,000: (블록 수) x 100,000
// - 나머지 >= 5,000: 클릭 x 10
function calcCost(clicks) {
  var n = Number(clicks) || 0;
  if (n <= 0) return 0;
  if (n < 10000) return n * 10;
  if (n % 10000 < 5000) return Math.floor(n / 10000) * 100000;
  return n * 10;
}

// ── 유틸 ──────────────────────────────────────────
function formatDate(date) {
  var y = date.getFullYear();
  var m = ("0" + (date.getMonth() + 1)).slice(-2);
  var d = ("0" + date.getDate()).slice(-2);
  return y + "-" + m + "-" + d;
}

function parseDate(dateStr) {
  var parts = dateStr.split("-");
  return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
}

function findDateColumn(headerRow, targetDate) {
  for (var i = 0; i < headerRow.length; i++) {
    var cell = headerRow[i];
    if (cell instanceof Date) cell = formatDate(cell);
    if (String(cell).trim() === targetDate) return i;
  }
  return -1;
}

// ── 채널상세 누락 행 탐지 ─────────────────────────
function findMissingChannelRows(srcData, colIdx) {
  var missing = [];
  // srcData[0]은 빈 행, srcData[1]이 헤더 → 데이터는 srcData[2]부터
  for (var i = 2; i < srcData.length; i++) {
    var channel = String(srcData[i][0] || "").trim();
    var value = srcData[i][colIdx];
    var hasValue = (value !== "" && value !== null && value !== undefined && value !== 0);
    if (hasValue && !channel) {
      missing.push(i + 1);
    }
  }
  return missing;
}

// ── 중복 방지 & 재실행용 삭제 ─────────────────────
function isAlreadyUploaded(tgtSheet, targetDate) {
  var data = tgtSheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    var cellVal = data[i][0];
    if (cellVal instanceof Date) cellVal = formatDate(cellVal);
    if (String(cellVal).trim() === targetDate) return true;
  }
  return false;
}

function deleteRowsForDate(tgtSheet, targetDate) {
  var data = tgtSheet.getDataRange().getValues();
  var rowsToDelete = [];
  for (var i = 1; i < data.length; i++) {
    var cellVal = data[i][0];
    if (cellVal instanceof Date) cellVal = formatDate(cellVal);
    if (String(cellVal).trim() === targetDate) rowsToDelete.push(i + 1);
  }
  for (var j = rowsToDelete.length - 1; j >= 0; j--) {
    tgtSheet.deleteRow(rowsToDelete[j]);
  }
  return rowsToDelete.length;
}

// ── 메인 업로드 로직 ──────────────────────────────
function updateForDate(targetDate, force) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var srcSheet = ss.getSheetByName(SOURCE_SHEET);
  var tgtSheet = ss.getSheetByName(TARGET_SHEET);

  if (!srcSheet || !tgtSheet) {
    return { ok: false, msg: "시트를 찾을 수 없습니다." };
  }

  var srcData = srcSheet.getDataRange().getValues();
  // srcData[0]은 빈 행, srcData[1]이 헤더
  var header = srcData[1];
  var colIdx = findDateColumn(header, targetDate);

  if (colIdx === -1) {
    return { ok: false, msg: "토스update에서 '" + targetDate + "' 열을 찾을 수 없습니다." };
  }

  var missingRows = findMissingChannelRows(srcData, colIdx);

  if (isAlreadyUploaded(tgtSheet, targetDate)) {
    if (force) {
      deleteRowsForDate(tgtSheet, targetDate);
    } else {
      return { ok: true, msg: targetDate + " 데이터가 이미 존재합니다.", missingRows: missingRows, skipped: true };
    }
  }

  var rows = [];
  rows.push([targetDate, "토스", "-", "없음", "없음", 0, 0, 0]);

  // 데이터는 srcData[2]부터
  for (var i = 2; i < srcData.length; i++) {
    var channel = String(srcData[i][0] || "").trim();
    if (!channel) continue;
    var value = srcData[i][colIdx];
    if (value === "" || value === null || value === undefined) continue;
    var clicks = Number(value) || 0;
    if (clicks === 0) continue;
    rows.push([targetDate, "토스", "-", "없음", channel, 0, clicks, calcCost(clicks)]);
  }

  var startRow = tgtSheet.getLastRow() + 1;
  var range = tgtSheet.getRange(startRow, 1, rows.length, 8);
  range.setValues(rows);
  range.setFontFamily("Arial");
  range.setFontSize(8);

  // 날짜 오름차순 정렬 (헤더 제외)
  var lastRow = tgtSheet.getLastRow();
  if (lastRow > 1) {
    tgtSheet.getRange(2, 1, lastRow - 1, 8).sort({ column: 1, ascending: true });
  }

  var msg = targetDate + " 업로드 완료: " + rows.length + "행 (디폴트 1 + 소재 " + (rows.length - 1) + ")";
  return { ok: true, msg: msg, missingRows: missingRows, count: rows.length };
}

// ── 구간 업로드 ───────────────────────────────────
function updateForRange(startDate, endDate, force) {
  var results = [];
  var current = parseDate(startDate);
  var end = parseDate(endDate);

  while (current <= end) {
    var dateStr = formatDate(current);
    var result = updateForDate(dateStr, force);
    results.push({ date: dateStr, result: result });
    current.setDate(current.getDate() + 1);
  }
  return results;
}

// ── 슬랙 알림 ─────────────────────────────────────
function sendSlackAlert(result, targetDate) {
  if (SLACK_WEBHOOK_URL) {
    sendSlackWebhook(result, targetDate);
  } else {
    sendSlackEmail(result, targetDate);
  }
}

function sendSlackWebhook(result, targetDate) {
  var icon = result.skipped ? "ℹ️" : (result.ok ? "✅" : "❌");
  var text = icon + " [토스봇] " + targetDate + "\n" + result.msg;

  if (result.missingRows && result.missingRows.length > 0) {
    text += "\n\n⚠️ 채널상세 업데이트 필요:";
    for (var i = 0; i < result.missingRows.length; i++) {
      text += "\n   • " + result.missingRows[i] + "행";
    }
  }


  var payload = { text: text };
  UrlFetchApp.fetch(SLACK_WEBHOOK_URL, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload)
  });
}

function sendSlackEmail(result, targetDate) {
  var subject = "[토스봇] " + targetDate;
  var body = "";

  if (result.skipped) {
    body += "ℹ️ " + result.msg + "\n";
  } else if (result.ok) {
    body += "✅ " + result.msg + "\n";
  } else {
    body += "❌ " + result.msg + "\n";
  }

  if (result.missingRows && result.missingRows.length > 0) {
    body += "\n⚠️ 채널상세 업데이트 필요:\n";
    for (var i = 0; i < result.missingRows.length; i++) {
      body += "  • " + result.missingRows[i] + "행 채널상세 업데이트 필요\n";
    }
  }

  body += "\n🔗 재수집: " + STREAMLIT_URL;

  MailApp.sendEmail({ to: SLACK_EMAIL, subject: subject, body: body });
}

function sendSlackAlertBatch(results) {
  var successDates = [];
  var failDates = [];
  var allMissing = [];

  for (var i = 0; i < results.length; i++) {
    var r = results[i];
    if (r.result.ok && !r.result.skipped) successDates.push(r.date);
    else if (!r.result.skipped) failDates.push(r.date + ": " + r.result.msg);

    if (r.result.missingRows) {
      for (var j = 0; j < r.result.missingRows.length; j++) {
        allMissing.push(r.date + " " + r.result.missingRows[j] + "행");
      }
    }
  }

  var combined = { ok: failDates.length === 0, msg: "", missingRows: null };

  if (successDates.length > 0) combined.msg += "업로드 완료: " + successDates.join(", ");
  if (failDates.length > 0) combined.msg += (combined.msg ? "\n" : "") + "실패: " + failDates.join(", ");
  if (combined.msg === "") { combined.msg = "변경사항 없음 (이미 업로드된 날짜)"; combined.skipped = true; }
  if (allMissing.length > 0) combined.missingRows = allMissing;

  var targetLabel = results.length === 1
    ? results[0].date
    : results[0].date + " ~ " + results[results.length - 1].date;

  if (SLACK_WEBHOOK_URL) {
    sendSlackWebhookBatch(combined, targetLabel);
  } else {
    sendSlackEmailBatch(combined, targetLabel);
  }
}

function sendSlackWebhookBatch(result, targetLabel) {
  var icon = result.skipped ? "ℹ️" : (result.ok ? "✅" : "❌");
  var text = icon + " [토스봇] " + targetLabel + "\n" + result.msg;

  if (result.missingRows && result.missingRows.length > 0) {
    text += "\n\n⚠️ 채널상세 업데이트 필요:";
    for (var i = 0; i < result.missingRows.length; i++) {
      text += "\n   • " + result.missingRows[i];
    }
  }


  UrlFetchApp.fetch(SLACK_WEBHOOK_URL, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({ text: text })
  });
}

function sendSlackEmailBatch(result, targetLabel) {
  var subject = "[토스봇] " + targetLabel;
  var body = (result.ok ? "✅ " : "❌ ") + result.msg + "\n";

  if (result.missingRows && result.missingRows.length > 0) {
    body += "\n⚠️ 채널상세 업데이트 필요:\n";
    for (var i = 0; i < result.missingRows.length; i++) {
      body += "  • " + result.missingRows[i] + " 채널상세 업데이트 필요\n";
    }
  }

  body += "\n🔗 재수집: " + STREAMLIT_URL;

  MailApp.sendEmail({ to: SLACK_EMAIL, subject: subject, body: body });
}

// ── 매일 자동 실행 (트리거용) ─────────────────────
function runTossUpdate() {
  var yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  var targetDate = formatDate(yesterday);

  var result = updateForDate(targetDate, false);
  Logger.log(result.msg);
  sendSlackAlert(result, targetDate);
}

// ── 트리거 등록 (최초 1회 실행) ──────────────────
function setupDailyTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === "runTossUpdate") {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }

  ScriptApp.newTrigger("runTossUpdate")
    .timeBased()
    .everyDays(1)
    .atHour(10)
    .create();

  Logger.log("매일 오전 10시 트리거가 등록되었습니다.");
}
