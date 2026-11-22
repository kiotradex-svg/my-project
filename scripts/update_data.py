#!/usr/bin/env python3
"""FRED 공개 CSV(API 키 불필요)로 자동 지표(01,02,03,05,06,07)를 갱신한다.
수동 지표(04,08,09,10)는 data.json 값을 그대로 유지한다.
사용: python3 scripts/update_data.py [입력.json] [출력.json]"""
import csv, io, json, sys, time, urllib.request, datetime

SRC = sys.argv[1] if len(sys.argv) > 1 else "data.json"
DST = sys.argv[2] if len(sys.argv) > 2 else SRC

def fred(sid, start):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"
    last_err = None
    for i in range(5):  # FRED가 간헐적으로 연결을 끊으므로 재시도
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=60) as r:
                rows = list(csv.reader(io.StringIO(r.read().decode())))[1:]
            return [(d, float(v)) for d, v in rows if v not in ("", ".")]
        except Exception as e:
            last_err = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"FRED {sid} 조회 실패: {last_err}")

def ago(days):
    return (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

def pct(x): return f"{x:+.1f}%".replace("+", "") if x < 0 else f"{x:.1f}%"

def drawdown(sid, label, name):
    data = fred(sid, ago(400))
    last_d, last = data[-1]
    cut = ago(365)
    hi = max(v for d, v in data if d >= cut)
    dd = (last / hi - 1) * 100
    status = "red" if dd <= -20 else "amber" if dd <= -10 else "green"
    recent = [v for d, v in data if d >= ago(92)]
    return dict(value=f"{dd:.1f}%", unit=f"52주 고점({hi:,.0f}) 대비 · {last_d} 종가 {last:,.0f}",
                status=status, series=recent, range="최근 3개월 종가", trend="FRED 일간",
                src=f"FRED {sid} ({name}) · {last_d} · 52주 고점 대비")

def main():
    d = json.load(open(SRC, encoding="utf-8"))
    by = {m["no"]: m for m in d["metrics"]}
    upd = {}
    upd["01"] = drawdown("SP500", "SPY", "S&P 500 지수")
    upd["02"] = drawdown("NASDAQ100", "QQQ", "나스닥100 지수")

    v = fred("VIXCLS", ago(45)); last_d, last = v[-1]
    upd["03"] = dict(value=f"{last:.1f}", unit=f"변동성 지수 · {last_d}",
        status="red" if last > 30 else "amber" if last > 20 else "green",
        series=[x for _, x in v[-24:]], range="최근 1개월 종가", trend="FRED 일간",
        src=f"FRED VIXCLS · {last_d}")

    h = fred("BAMLH0A0HYM2", ago(60)); last_d, last = h[-1]
    w1 = last - h[-6][1] if len(h) > 6 else 0
    w4 = last - h[-21][1] if len(h) > 21 else 0
    st = "red" if (w1 >= 0.5 or last >= 5) else "amber" if (w1 >= 0.25 or w4 >= 0.25 or last >= 4) else "green"
    upd["05"] = dict(value=f"{last:.2f}%p", unit=f"{last_d} 기준 · 4주 {w4:+.2f}%p · 1주 {w1:+.2f}%p",
        status=st, series=[x for _, x in h[-23:]], range=f"{h[-23][0][5:]} ~ {last_d[5:]}", trend="FRED 일간",
        src=f"FRED BAMLH0A0HYM2 · {last_d}")

    for no, sid, lo, hi_ in (("06", "DGS10", 4.5, 5.25), ("07", "DGS2", 4.5, 5.25)):
        y = fred(sid, ago(130)); last_d, last = y[-1]
        w4 = last - y[-21][1] if len(y) > 21 else 0
        st = "red" if (last >= hi_ or w4 >= 0.5) else "amber" if (last >= lo or w4 >= 0.25) else "green"
        upd[no] = dict(value=f"{last:.2f}%", unit=f"4주 변화 {w4:+.2f}%p · {last_d}",
            status=st, series=[x for _, x in y[-63:]], range="최근 3개월", trend="FRED 일간",
            src=f"FRED {sid} · {last_d}")

    for no, patch in upd.items():
        by[no].update(patch)
    d["asOf"] = v[-1][0]  # 데이터의 실제 최신 거래일(FRED는 하루 지연)
    d["updatedAt"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    json.dump(d, open(DST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(DST, "a").write("\n")
    print("updated:", ", ".join(sorted(upd)), "->", DST)

if __name__ == "__main__":
    main()
