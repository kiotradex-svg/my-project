/**
 * 패치: API 키 없이 SPY/QQQ/VGT 일봉 종가를 자동 수집해 Price_History 시트에 누적한다.
 * 소스 우선순위: Yahoo Finance chart(키 불필요) → Stooq CSV(키 불필요).
 * 적용: DataService.gs 맨 아래에 이 파일 내용을 전부 붙여넣고,
 *       기존 getMarketPrice_(symbol) 함수의 첫 줄(const sheet = ...) 바로 위에
 *       `syncPriceHistory_(symbol);` 한 줄만 추가한다.
 */

function syncPriceHistory_(symbol) {
  try {
    const closes = fetchDailyCloses_(symbol);            // [{date, close, source}] 오름차순
    if (!closes.length) return;
    const sheet = getSpreadsheet_().getSheetByName('Price_History');
    const have = new Set(sheet.getLastRow() > 1
      ? sheet.getRange(2, 1, sheet.getLastRow() - 1, 2).getValues().map(r => String(r[0]) + '|' + marketDateKey_(r[1]))
      : []);
    const now = new Date();
    const rows = closes
      .filter(c => !have.has(symbol + '|' + c.date))
      .map(c => [symbol, c.date, c.close, c.source, now]);
    if (rows.length) sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, 5).setValues(rows);
  } catch (e) { console.warn('syncPriceHistory_ ' + symbol + ': ' + e); }
}

function fetchDailyCloses_(symbol) {
  const errors = [];
  const sources = [fetchYahooCloses_, fetchStooqCloses_];
  for (const fn of sources) {
    try {
      const out = fn(symbol);
      if (out && out.length > 20) return dropIncompleteBar_(out);
    } catch (e) { errors.push(fn.name + ': ' + e); }
  }
  console.warn('가격 수집 실패 ' + symbol + ' | ' + errors.join(' | '));
  return [];
}

function fetchYahooCloses_(symbol) {
  const url = 'https://query1.finance.yahoo.com/v8/finance/chart/' + encodeURIComponent(symbol) + '?range=1y&interval=1d';
  const res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, headers: { 'User-Agent': 'Mozilla/5.0' } });
  if (res.getResponseCode() !== 200) throw new Error('HTTP ' + res.getResponseCode());
  const r = JSON.parse(res.getContentText()).chart.result[0];
  const q = r.indicators.quote[0].close;
  const out = [];
  r.timestamp.forEach((t, i) => {
    if (q[i] == null || !Number.isFinite(Number(q[i]))) return;
    out.push({ date: Utilities.formatDate(new Date(t * 1000), 'America/New_York', 'yyyy-MM-dd'),
               close: Number(Number(q[i]).toFixed(2)), source: 'Yahoo Finance daily close' });
  });
  return out;
}

function fetchStooqCloses_(symbol) {
  const url = 'https://stooq.com/q/d/l/?s=' + encodeURIComponent(symbol.toLowerCase()) + '.us&i=d';
  const res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) throw new Error('HTTP ' + res.getResponseCode());
  const rows = Utilities.parseCsv(res.getContentText());
  if (!rows || rows.length < 3 || rows[0][0] !== 'Date') throw new Error('CSV 형식 오류');
  return rows.slice(1).filter(r => /^\d{4}-\d{2}-\d{2}$/.test(r[0]) && Number.isFinite(Number(r[4])))
    .map(r => ({ date: r[0], close: Number(r[4]), source: 'Stooq daily close' }))
    .slice(-260);
}

// 장중에는 마지막 봉이 미완성이므로 제외 (미국 동부 16:15 이전이면 오늘 봉 삭제)
function dropIncompleteBar_(arr) {
  const et = new Date(Utilities.formatDate(new Date(), 'America/New_York', "yyyy-MM-dd'T'HH:mm:ss"));
  const today = Utilities.formatDate(new Date(), 'America/New_York', 'yyyy-MM-dd');
  const minutes = et.getHours() * 60 + et.getMinutes();
  const last = arr[arr.length - 1];
  return (last.date === today && minutes < 16 * 60 + 15) ? arr.slice(0, -1) : arr;
}
