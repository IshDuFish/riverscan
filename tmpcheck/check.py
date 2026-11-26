import yfinance as yf
syms = ["^FTAI", "^FTAS", "^FTSE", "^FTMC", "^FTLC", "SCLP.L", "BAB.L", "BA.L", "QQ.L", "HCM.L", "OXB.L", "AVCT.L", "HVO.L", "KIE.L", "RNWH.L", "CHG.L", "FUM.L", "EVG.L", "IMM.L", "STX.L", "AREC.L", "POLB.L", "FARN.L"]
for s in syms:
    try:
        df = yf.download(s, period="1mo", progress=False, auto_adjust=True)
        c = df["Close"]; c = c.iloc[:, 0] if hasattr(c, "columns") else c
        print(f"{s:8} rows={len(c):3} last={c.iloc[-1]:.2f} on {c.index[-1].date()}" if len(c) else f"{s:8} EMPTY")
    except Exception as e:
        print(s, "ERR", e)
