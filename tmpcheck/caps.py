import yfinance as yf
syms = {"BBY":"BBY.L","MGNS":"MGNS.L","KIE":"KIE.L","COST":"COST.L","GFRD":"GFRD.L","KLR":"KLR.L","RNWH":"RNWH.L","SRP":"SRP.L","MTO":"MTO.L","CPI":"CPI.L","BA.":"BA.L","BAB":"BAB.L","QQ.":"QQ.L","CHG":"CHG.L",
 "SFR":"SFR.L","BOOT":"BOOT.L","RCDO":"RCDO.L","AVON":"AVON.L","CHRT":"CHRT.L","KNOS":"KNOS.L","NCC":"NCC.L","MTEC":"MTEC.L","TPX":"TPX.L","MER":"MER.L","RST":"RST.L","PEG":"PEG.L","NTBR":"NTBR.L",
 "HCM":"HCM.L","SCLP":"SCLP.L","FARN":"FARN.L","AVCT":"AVCT.L","POLB":"POLB.L","FUM":"FUM.L","AREC":"AREC.L","IMM":"IMM.L","STX":"STX.L","EVG":"EVG.L","HVO":"HVO.L","OXB":"OXB.L"}
for t, s in syms.items():
    try:
        tk = yf.Ticker(s); i = tk.info
        fi = tk.fast_info
        print(f"{t:5} {i.get('shortName','?')[:28]:28} mcap={i.get('marketCap')} cur={i.get('currency')} fin={i.get('financialCurrency')} rev={i.get('totalRevenue')} price={i.get('currentPrice') or i.get('regularMarketPrice')} shares={i.get('sharesOutstanding')} fast_mcap={getattr(fi,'market_cap',None)}")
    except Exception as e:
        print(t, "ERR", str(e)[:80])
