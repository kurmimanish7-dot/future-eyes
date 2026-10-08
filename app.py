import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime, date, time as dtime, timedelta
import json
import requests
from zoneinfo import ZoneInfo
​IST = ZoneInfo("Asia/Kolkata")
​=========================================================
​PAGE CONFIGURATION
​=========================================================
​st.set_page_config(
page_title="AI Trading Expert Advisor • Live Market",
page_icon="📊",
layout="wide",
)
​PAPER_TRADING = True
​=========================================================
​MOBILE UI & LIVE TICKER STYLING
​=========================================================
​st.markdown("""
<style>
​/* ---------- MAIN CONTAINER ---------- */
.block-container{
padding-top:1rem!important;
padding-left:.7rem!important;
padding-right:.7rem!important;
max-width:100%!important;
}
​/* ---------- LIVE TICKER PULSE ---------- */
.live-pulse-container {
display: inline-flex;
align-items: center;
gap: 8px;
background: rgba(0, 230, 118, 0.12);
border: 1px solid rgba(0, 230, 118, 0.4);
padding: 5px 14px;
border-radius: 20px;
font-size: 13px;
font-weight: 600;
color: #00e676;
}
​.live-pulse-dot {
width: 10px;
height: 10px;
border-radius: 50%;
background-color: #00e676;
box-shadow: 0 0 0 0 rgba(0, 230, 118, 0.8);
animation: live-pulse-anim 1.5s infinite;
}
​.live-pulse-paused {
display: inline-flex;
align-items: center;
gap: 8px;
background: rgba(255, 171, 0, 0.12);
border: 1px solid rgba(255, 171, 0, 0.4);
padding: 5px 14px;
border-radius: 20px;
font-size: 13px;
font-weight: 600;
color: #ffab00;
}
​@keyframes live-pulse-anim {
0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 230, 118, 0.8); }
70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(0, 230, 118, 0); }
100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 230, 118, 0); }
}
​/* ---------- MOBILE RESPONSIVE ---------- */
@media(max-width:768px){
[data-testid="stHorizontalBlock"]{
flex-wrap:wrap!important;
gap:.45rem!important;
width:100%!important;
}
​[data-testid="column"]{
min-width:48%!important;
max-width:48%!important;
flex:1 1 48%!important;
width:48%!important;
min-height:0!important;
}
​[data-testid="stMetric"]{
width:100%!important;
min-width:0!important;
max-width:100%!important;
overflow:visible!important;
}
​[data-testid="stMetricLabel"]{
font-size:11px!important;
line-height:1.25!important;
white-space:normal!important;
overflow-wrap:anywhere!important;
}
​[data-testid="stMetricValue"]{
font-size:clamp(14px,5vw,18px)!important;
line-height:1.25!important;
}
​h1{ font-size:24px!important; line-height:1.2!important; }
h2{ font-size:20px!important; line-height:1.25!important; }
h3{ font-size:17px!important; line-height:1.3!important; }
​.trade-card{
width:100%!important;
padding:.75rem!important;
}
}
​/* ---------- TRADE CARD ---------- */
.trade-card{
width:100%;
box-sizing:border-box;
border:1px solid rgba(128,128,128,.30);
border-radius:12px;
padding:1rem;
margin:.5rem 0;
overflow-wrap:anywhere;
}
​.small{
font-size:.88rem;
opacity:.85;
overflow-wrap:anywhere;
}
​.reason{
line-height:1.5;
overflow-wrap:anywhere;
}
</style>
""", unsafe_allow_html=True)
​=========================================================
​OPTIONAL ENGINES
​=========================================================
​try:
from telemetry_engine import TelemetryEngine
except Exception:
TelemetryEngine = None
​try:
from options_engine import OptionsEngine
except Exception:
OptionsEngine = None
​try:
from tomorrow_forecast_engine import build_tomorrow_forecast
except Exception:
build_tomorrow_forecast = None
​try:
from future_eyes import FutureEyes
except Exception:
FutureEyes = None
​=========================================================
​HELPERS
​=========================================================
​def secret(name):
try:
value = st.secrets.get(name)
return str(value).strip() if value else ""
except Exception:
return ""
​def num(x, default=None):
try:
if x is None:
return default
if isinstance(x, (int, float)):
return float(x)
if isinstance(x, str):
x = x.replace(",", "").strip()
return float(x)
except Exception:
return default
​def fmt(x, digits=2):
x = num(x)
if x is None or not np.isfinite(x):
return "-"
return f"{x:,.{digits}f}"
​def safe_text(x):
return str(x) if x is not None else ""
​def market_open():
"""
NSE market status in IST.
Normal equity/derivatives session: Monday-Friday, 09:15 to 15:30.
"""
now = datetime.now(IST)
​# Saturday / Sunday
if now.weekday() >= 5:
return False
​# NSE trading holidays
NSE_HOLIDAYS = {
"2026-01-26", "2026-03-03", "2026-03-26", "2026-03-31",
"2026-04-03", "2026-04-14", "2026-05-01", "2026-06-26",
"2026-08-15", "2026-08-26", "2026-09-14", "2026-10-02",
"2026-10-20", "2026-11-09", "2026-11-10", "2026-11-24",
"2026-12-25",
}
​if now.strftime("%Y-%m-%d") in NSE_HOLIDAYS:
return False
​return dtime(9, 15) <= now.time() <= dtime(15, 30)
​def expiry_norm(x):
if x is None:
return None
if isinstance(x, (datetime, date)):
return x.strftime("%Y-%m-%d")
​s = str(x).strip().upper()
formats = [
"%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y",
"%d%b%Y", "%d-%b-%Y", "%d%b%y", "%d-%b-%y",
]
for f in formats:
try:
return datetime.strptime(s, f).strftime("%Y-%m-%d")
except Exception:
pass
return s
​def expiry_label(x):
n = expiry_norm(x)
if not n:
return "-"
try:
return datetime.strptime(n, "%Y-%m-%d").strftime("%d %b %Y")
except Exception:
return str(x)
​def clean_df(df):
if df is None:
return pd.DataFrame()
if isinstance(df, pd.DataFrame):
return df.copy()
try:
return pd.DataFrame(df)
except Exception:
return pd.DataFrame()
​def first_value(row, names, default=None):
for name in names:
if isinstance(row, dict) and name in row:
value = row.get(name)
if value is not None and str(value) != "":
return value
try:
if name in row.index:
value = row[name]
if pd.notna(value):
return value
except Exception:
pass
return default
​def find_column(df, names):
for name in names:
if name in df.columns:
return name
return None
​=========================================================
​SECRETS
​=========================================================
​ANGEL_API_KEY = secret("ANGEL_API_KEY")
ANGEL_CLIENT_CODE = secret("ANGEL_CLIENT_CODE")
ANGEL_PIN = secret("ANGEL_PIN")
ANGEL_TOTP_SECRET = secret("ANGEL_TOTP_SECRET")
ANGEL_JWT_TOKEN = secret("ANGEL_JWT_TOKEN")
​GEMINI_API_KEY = (
secret("GEMINI_API_KEY")
or secret("GOOGLE_API_KEY")
or secret("GEMINI_KEY")
)
​GEMINI_MODEL = (
secret("GEMINI_MODEL")
or "gemini-3.6-flash"
)
​=========================================================
​FII / DII
​=========================================================
​FII_DII_API = "https://fii-diidata.mrchartist.com/api/data"
FII_DII_HISTORY_API = "https://fii-diidata.mrchartist.com/api/history"
​def extract_number(obj, keys):
if not isinstance(obj, dict):
return None
for key in keys:
if key in obj:
value = num(obj.get(key))
if value is not None:
return value
return None
​def find_nested_record(obj):
if isinstance(obj, dict):
for key in ["data", "result", "latest", "current", "record"]:
value = obj.get(key)
if isinstance(value, dict):
return value
if isinstance(value, list) and value and isinstance(value[0], dict):
return value[0]
return obj
if isinstance(obj, list) and obj and isinstance(obj[0], dict):
return obj[0]
return {}
​def parse_fii_dii_record(record):
record = find_nested_record(record)
fii_buy = extract_number(record, ["fii_buy", "fiiBuy", "fiibuy", "fb", "FII Buy", "FII_Buy"])
fii_sell = extract_number(record, ["fii_sell", "fiiSell", "fiisell", "fs", "FII Sell", "FII_Sell"])
fii_net = extract_number(record, ["fii_net", "fiiNet", "fiinet", "fn", "FII Net", "FII_Net"])
dii_buy = extract_number(record, ["dii_buy", "diiBuy", "diibuy", "db", "DII Buy", "DII_Buy"])
dii_sell = extract_number(record, ["dii_sell", "diiSell", "diisell", "ds", "DII Sell", "DII_Sell"])
dii_net = extract_number(record, ["dii_net", "diiNet", "diinet", "dn", "DII Net", "DII_Net"])
​if fii_net is None and fii_buy is not None and fii_sell is not None:
fii_net = fii_buy - fii_sell
if dii_net is None and dii_buy is not None and dii_sell is not None:
dii_net = dii_buy - dii_sell
​data_date = (
record.get("date")
or record.get("d")
or record.get("trade_date")
or record.get("tradeDate")
or record.get("timestamp")
)
​return {
"fii_buy": fii_buy,
"fii_sell": fii_sell,
"fii_net": fii_net,
"dii_buy": dii_buy,
"dii_sell": dii_sell,
"dii_net": dii_net,
"date": data_date,
}
​@st.cache_data(ttl=300, show_spinner=False)
def fetch_fii_dii():
empty = {
"available": False,
"source": "Unavailable",
"date": None,
"fii_buy": None,
"fii_sell": None,
"fii_net": None,
"dii_buy": None,
"dii_sell": None,
"dii_net": None,
"combined_net": None,
"fii_3d": None,
"dii_3d": None,
"institutional_score": 0,
"bias": "UNAVAILABLE",
"bias_score": "NEUTRAL",
"status": "Data unavailable",
}
​latest = None
try:
response = requests.get(FII_DII_API, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
if response.ok:
latest = response.json()
except Exception:
latest = None
​if latest is None:
return empty
​parsed = parse_fii_dii_record(latest)
fii_net = parsed["fii_net"]
dii_net = parsed["dii_net"]
​if fii_net is None and dii_net is None:
return empty
​history = []
try:
response = requests.get(FII_DII_HISTORY_API, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
if response.ok:
history_data = response.json()
if isinstance(history_data, dict):
for key in ["data", "history", "results"]:
if isinstance(history_data.get(key), list):
history = history_data[key]
break
elif isinstance(history_data, list):
history = history_data
except Exception:
history = []
​fii_history = []
dii_history = []
for item in history[:5]:
row = parse_fii_dii_record(item)
if row["fii_net"] is not None:
fii_history.append(row["fii_net"])
if row["dii_net"] is not None:
dii_history.append(row["dii_net"])
​fii_values = [fii_net] + fii_history[:2] if fii_net is not None else fii_history[:3]
dii_values = [dii_net] + dii_history[:2] if dii_net is not None else dii_history[:3]
​fii_3d = sum(fii_values) if fii_values else None
dii_3d = sum(dii_values) if dii_values else None
​score = 0
if fii_net is not None:
if fii_net >= 2000: score += 2
elif fii_net >= 500: score += 1
elif fii_net <= -2000: score -= 2
elif fii_net <= -500: score -= 1
​if dii_net is not None:
if dii_net >= 2000: score += 1
elif dii_net >= 500: score += 1
elif dii_net <= -2000: score -= 1
elif dii_net <= -500: score -= 1
​if fii_3d is not None and fii_3d >= 5000: score += 1
elif fii_3d is not None and fii_3d <= -5000: score -= 1
​bias = "MIXED"
if fii_net is not None and dii_net is not None:
if fii_net > 500 and dii_net > 500: bias = "BULLISH CONFIRMATION"
elif fii_net < -500 and dii_net < -500: bias = "BEARISH CONFIRMATION"
elif fii_net < -500 and dii_net > 500: bias = "FII SELLING / DII BUYING"
elif fii_net > 500 and dii_net < -500: bias = "FII BUYING / DII SELLING"
else: bias = "MIXED / WEAK"
elif fii_net is not None:
if fii_net > 500: bias = "FII POSITIVE"
elif fii_net < -500: bias = "FII NEGATIVE"
​bias_score = "POSITIVE" if score > 0 else ("NEGATIVE" if score < 0 else "NEUTRAL")
​return {
"available": True,
"source": "Free NSE-sourced FII/DII API",
"date": parsed["date"],
"fii_buy": parsed["fii_buy"],
"fii_sell": parsed["fii_sell"],
"fii_net": fii_net,
"dii_buy": parsed["dii_buy"],
"dii_sell": parsed["dii_sell"],
"dii_net": dii_net,
"combined_net": (fii_net + dii_net if fii_net is not None and dii_net is not None else None),
"fii_3d": fii_3d,
"dii_3d": dii_3d,
"institutional_score": score,
"bias": bias,
"bias_score": bias_score,
"status": "Latest available / provisional",
}
​fii_dii = fetch_fii_dii()
​=========================================================
​ENGINES INITIALIZATION
​=========================================================
​@st.cache_resource(show_spinner=False)
def create_telemetry():
if TelemetryEngine is None:
return None
if not all([ANGEL_API_KEY, ANGEL_CLIENT_CODE, ANGEL_PIN, ANGEL_TOTP_SECRET]):
return None
try:
return TelemetryEngine(
api_key=ANGEL_API_KEY,
client_code=ANGEL_CLIENT_CODE,
pin=ANGEL_PIN,
totp_secret=ANGEL_TOTP_SECRET,
)
except Exception:
return None
​@st.cache_resource(show_spinner=False)
def create_options():
if OptionsEngine is None:
return None
try:
if ANGEL_JWT_TOKEN:
return OptionsEngine(
jwt_token=ANGEL_JWT_TOKEN,
api_key=ANGEL_API_KEY,
client_code=ANGEL_CLIENT_CODE,
)
except Exception:
pass
​telemetry_obj = create_telemetry()
if telemetry_obj is not None:
try:
smart_api = getattr(telemetry_obj, "smart_api", None)
token = getattr(smart_api, "access_token", None)
if token:
return OptionsEngine(
jwt_token=str(token),
api_key=ANGEL_API_KEY,
client_code=ANGEL_CLIENT_CODE,
)
except Exception:
pass
return None
​telemetry = create_telemetry()
options = create_options()
​=========================================================
​MARKET CONFIG & TOKENS
​=========================================================
​UNDERLYINGS = [
"NIFTY",
"BANKNIFTY",
"FINNIFTY",
"MIDCPNIFTY",
"SENSEX",
"BANKEX",
]
​SPOT_TOKENS = {
"NIFTY": ("NSE", "99926000"),
"BANKNIFTY": ("NSE", "99926009"),
"FINNIFTY": ("NSE", "99926037"),
"MIDCPNIFTY": ("NSE", "99926074"),
"SENSEX": ("BSE", "99919000"),
"BANKEX": ("BSE", "99919012"),
}
​SYMBOL_ALIASES = {
"NIFTY": ["NIFTY", "Nifty 50", "NIFTY 50", "Nifty50"],
"BANKNIFTY": ["BANKNIFTY", "Nifty Bank", "NIFTY BANK", "BankNifty"],
"FINNIFTY": ["FINNIFTY", "Nifty Fin Services", "NIFTY FINANCIAL SERVICES"],
"MIDCPNIFTY": ["MIDCPNIFTY", "NIFTY MID SELECT", "Nifty Midcap Select"],
"SENSEX": ["SENSEX", "Sensex", "BSE SENSEX"],
"BANKEX": ["BANKEX", "Bankex", "BSE BANKEX"],
}
​=========================================================
​ROBUST LIVE LTP STREAMING HANDLER
​=========================================================
​def parse_ltp_response(res):
"""Deeply inspects any broker response (dict, nested data, float, string) for valid positive price."""
if res is None:
return None
if isinstance(res, (int, float)):
v = float(res)
return v if v > 0 and np.isfinite(v) else None
if isinstance(res, str):
v = num(res)
return v if v and v > 0 and np.isfinite(v) else None
if isinstance(res, dict):
if "data" in res and isinstance(res["data"], dict):
val = parse_ltp_response(res["data"])
if val is not None:
return val
if "data" in res and isinstance(res["data"], list) and res["data"]:
val = parse_ltp_response(res["data"][0])
if val is not None:
return val
for k in (
"ltp", "LTP", "lastTradedPrice", "lastTradedPriceValue",
"last_price", "close", "price", "c"
):
if k in res:
v = num(res[k])
if v is not None and v > 0 and np.isfinite(v):
return v
if isinstance(res, list) and res:
return parse_ltp_response(res[0])
return None
​def get_spot(symbol):
"""
Live real-time spot fetcher.
Prioritizes real-time broker ticks via SmartAPI/Telemetry before falling back to cached OHLC.
"""
exchange, token = SPOT_TOKENS.get(symbol, ("NSE", ""))
​# 1. Direct Telemetry Engine Calls
if telemetry is not None:
try:
val = parse_ltp_response(telemetry.get_ltp(symbol))
if val is not None:
return val
except Exception:
pass
​if exchange and token:
for meth in ("get_ltp", "fetch_ltp", "get_spot_ltp"):
if hasattr(telemetry, meth):
try:
func = getattr(telemetry, meth)
val = parse_ltp_response(func(exchange, token))
if val is not None:
return val
val = parse_ltp_response(func(exchange, symbol, token))
if val is not None:
return val
except Exception:
pass
​# Direct Angel One SmartAPI integration
smart_api = getattr(telemetry, "smart_api", None)
if smart_api is not None and exchange and token:
aliases = SYMBOL_ALIASES.get(symbol, [symbol])
for alias in aliases:
try:
if hasattr(smart_api, "getLtpData"):
res = smart_api.getLtpData(
exchange=exchange,
tradingsymbol=alias,
symboltoken=token,
)
val = parse_ltp_response(res)
if val is not None:
return val
except Exception:
pass
try:
if hasattr(smart_api, "ltpData"):
res = smart_api.ltpData(exchange, alias, token)
val = parse_ltp_response(res)
if val is not None:
return val
except Exception:
pass
​# 2. Options Engine Spot
if options is not None:
try:
if hasattr(options, "get_spot_price"):
val = parse_ltp_response(options.get_spot_price(symbol))
if val is not None:
return val
except Exception:
pass
​# 3. Fallback to latest candle close
try:
df = fetch_ohlcv(symbol, interval="FIVE_MINUTE", days=5)
if df is not None and not df.empty and "close" in df.columns:
close = pd.to_numeric(df["close"], errors="coerce").dropna()
if not close.empty:
val = float(close.iloc[-1])
if val > 0 and np.isfinite(val):
return val
except Exception:
pass
​return None
​=========================================================
​EXPIRIES & CONTRACTS
​=========================================================
​@st.cache_data(ttl=300, show_spinner=False)
def load_expiries(symbol):
if options is None:
return []
try:
result = options.get_expiry_options(symbol)
values = []
for item in result or []:
value = item.get("value") or item.get("expiry") or item.get("expiryDate") if isinstance(item, dict) else item
value = expiry_norm(value)
if not value:
continue
try:
d = datetime.strptime(value, "%Y-%m-%d").date()
if d >= date.today():
values.append(value)
except Exception:
pass
return sorted(set(values))
except Exception:
return []
​@st.cache_data(ttl=120, show_spinner=False)
def load_contracts(symbol, expiry):
if options is None or not expiry:
return pd.DataFrame()
try:
return clean_df(
options.get_option_contracts(
underlying=symbol,
expiry_date=expiry,
)
)
except Exception:
return pd.DataFrame()
​def get_chain(symbol, expiry, spot):
contracts = load_contracts(symbol, expiry)
if contracts.empty:
return pd.DataFrame(), contracts
​def normalize_strike_value(value):
try:
value = float(value)
if abs(value) >= 100000:
value = value / 100.0
return value
except Exception:
return None
​try:
contract_strike_col = find_column(contracts, ["strike", "strikePrice", "strike_price"])
if contract_strike_col is not None:
contracts["strikePrice"] = (
pd.to_numeric(contracts[contract_strike_col], errors="coerce")
.apply(normalize_strike_value)
)
if "strike" in contracts.columns:
contracts["strike"] = contracts["strikePrice"]
except Exception:
pass
​# Near ATM selection
try:
if spot is not None and options is not None:
near = options.get_near_atm_contracts(
underlying=symbol,
expiry_date=expiry,
spot_price=spot,
strikes_each_side=10,
)
near = clean_df(near)
if not near.empty:
contracts = near
near_strike_col = find_column(contracts, ["strike", "strikePrice", "strike_price"])
if near_strike_col is not None:
contracts["strikePrice"] = (
pd.to_numeric(contracts[near_strike_col], errors="coerce")
.apply(normalize_strike_value)
)
if "strike" in contracts.columns:
contracts["strike"] = contracts["strikePrice"]
except Exception:
pass
​# Live Market Quotes
try:
quoted = options.get_market_quote(contracts)
quoted = clean_df(quoted)
chain = quoted if not quoted.empty else contracts.copy()
except Exception:
chain = contracts.copy()
​# Normalize fields
type_col = find_column(chain, ["option_type", "optionType", "optionTypeName", "type"])
if type_col is not None:
chain["option_type"] = chain[type_col].map(normalize_option_type)
​strike_col = find_column(chain, ["strike", "strikePrice", "strike_price"])
if strike_col is not None:
chain["strikePrice"] = pd.to_numeric(chain[strike_col], errors="coerce").apply(normalize_strike_value)
if "strike" in chain.columns:
chain["strike"] = chain["strikePrice"]
​oi_col = find_column(chain, ["opnInterest", "openInterest", "oi", "open_interest"])
if oi_col is not None:
chain["openInterest"] = pd.to_numeric(chain[oi_col], errors="coerce")
​chg_oi_col = find_column(chain, ["changeinOpenInterest", "changeInOpenInterest", "change_oi", "chg_oi"])
if chg_oi_col is not None:
chain["changeInOpenInterest"] = pd.to_numeric(chain[chg_oi_col], errors="coerce")
​# Greeks integration
try:
if options is not None:
greeks = clean_df(options.greeks_dataframe(symbol, expiry))
if not greeks.empty:
greek_strike = find_column(greeks, ["strikePrice", "strike", "strike_price"])
if greek_strike is not None:
greeks["strikePrice"] = pd.to_numeric(greeks[greek_strike], errors="coerce").apply(normalize_strike_value)
greek_cols = [c for c in ["strikePrice", "delta", "gamma", "theta", "vega", "impliedVolatility"] if c in greeks.columns]
if "strikePrice" in greek_cols:
greek_type = find_column(greeks, ["optionType", "option_type", "optionTypeName"])
if greek_type is not None:
greeks["option_type"] = greeks[greek_type].map(normalize_option_type)
chain = chain.merge(
greeks[greek_cols + ["option_type"]].drop_duplicates(),
on=["strikePrice", "option_type"],
how="left",
suffixes=("", "_greek"),
)
else:
chain = chain.merge(
greeks[greek_cols].drop_duplicates(subset=["strikePrice"]),
on="strikePrice",
how="left",
suffixes=("", "_greek"),
)
except Exception:
pass
​return chain.reset_index(drop=True), contracts.reset_index(drop=True)
​def normalize_option_type(value):
if value is None:
return ""
x = str(value).strip().upper()
if x in ["CE", "CALL", "C"] or x.endswith("CE") or "CALL" in x:
return "CE"
if x in ["PE", "PUT", "P"] or x.endswith("PE") or "PUT" in x:
return "PE"
return ""
​def calculate_pcr(df):
if df is not None and not df.empty:
oi_col = find_column(df, ["opnInterest", "openInterest", "oi", "open_interest"])
type_col = find_column(df, ["option_type", "optionType", "optionTypeName", "type"])
if oi_col is not None and type_col is not None:
work = df.copy()
work["_oi"] = pd.to_numeric(
work[oi_col].astype(str).str.replace(",", "", regex=False),
errors="coerce"
).fillna(0)
work["_option_type"] = work[type_col].map(normalize_option_type)
​ce_oi = work.loc[work["_option_type"] == "CE", "_oi"].sum()
pe_oi = work.loc[work["_option_type"] == "PE", "_oi"].sum()
​if ce_oi > 0 and pe_oi >= 0:
pcr = pe_oi / ce_oi
if np.isfinite(pcr) and 0 < pcr <= 10:
return float(pcr)
​try:
if options is not None:
pcr_df = clean_df(options.pcr_dataframe())
if not pcr_df.empty:
for col in ["pcr", "putCallRatio", "put_call_ratio"]:
if col in pcr_df.columns:
vals = pd.to_numeric(pcr_df[col], errors="coerce").dropna()
if not vals.empty:
v = float(vals.iloc[-1])
if np.isfinite(v) and 0 < v <= 10:
return v
except Exception:
pass
​return None
​def calculate_live_derivatives_proxy(chain, pcr):
result = {
"available": False,
"score": 0,
"bias": "UNAVAILABLE",
"source": "Live option-chain positioning proxy",
"status": "No usable derivatives positioning",
"reasons": [],
"pcr": pcr,
}
​if chain.empty:
return result
​type_col = find_column(chain, ["option_type", "optionType", "optionTypeName", "type"])
chg_oi_col = find_column(chain, ["changeinOpenInterest", "changeInOpenInterest", "change_oi", "chg_oi"])
​score = 0
reasons = []
usable = False
​if pcr is not None:
usable = True
if 1.10 <= pcr <= 1.80:
score += 2
reasons.append(f"PCR {pcr:.2f} supportive hai.")
elif 0.90 <= pcr < 1.10:
score += 1
reasons.append(f"PCR {pcr:.2f} mildly supportive hai.")
elif 0.70 <= pcr < 0.90:
reasons.append(f"PCR {pcr:.2f} neutral-to-cautious zone mein hai.")
elif 0.40 <= pcr < 0.70:
score -= 1
reasons.append(f"PCR {pcr:.2f} bearish pressure indicate karta hai.")
elif pcr < 0.40:
score -= 2
reasons.append(f"PCR {pcr:.2f} strong caution zone mein hai.")
​if type_col is not None and chg_oi_col is not None:
work = chain.copy()
work["_type"] = work[type_col].map(normalize_option_type)
work["_chg_oi"] = pd.to_numeric(
work[chg_oi_col].astype(str).str.replace(",", "", regex=False),
errors="coerce"
).fillna(0)
​ce_change = work.loc[work["_type"] == "CE", "_chg_oi"].sum()
pe_change = work.loc[work["_type"] == "PE", "_chg_oi"].sum()
​if work["_type"].isin(["CE", "PE"]).any():
usable = True
if pe_change > 0 and ce_change < 0:
score += 1
reasons.append("Option-chain change in OI mildly bullish side par hai.")
elif ce_change > 0 and pe_change < 0:
score -= 1
reasons.append("Option-chain change in OI mildly bearish side par hai.")
​if not usable:
return result
​score = max(-2, min(2, score))
bias_map = {2: "BULLISH PROXY", 1: "MILD BULLISH PROXY", -1: "MILD BEARISH PROXY", -2: "BEARISH PROXY"}
bias = bias_map.get(score, "NEUTRAL PROXY")
​result.update({
"available": True,
"score": score,
"bias": bias,
"status": "Live broker option-chain positioning" if market_open() else "Latest broker option-chain positioning",
"reasons": reasons,
})
return result
​=========================================================
​FAST OHLCV (15s TTL during live session)
​=========================================================
​@st.cache_data(ttl=15, show_spinner=False)
def fetch_ohlcv(symbol, interval="FIVE_MINUTE", days=5):
if telemetry is None or symbol not in SPOT_TOKENS:
return pd.DataFrame()
​exchange, token = SPOT_TOKENS[symbol]
try:
df = telemetry.fetch_ohlcv(
exchange=exchange,
token=token,
interval=interval,
days=days,
)
df = clean_df(df)
if df.empty:
return df
​rename = {}
for c in df.columns:
lc = str(c).lower()
if lc in ["open", "o"]: rename[c] = "open"
elif lc in ["high", "h"]: rename[c] = "high"
elif lc in ["low", "l"]: rename[c] = "low"
elif lc in ["close", "c", "ltp"]: rename[c] = "close"
elif lc in ["volume", "vol"]: rename[c] = "volume"
​df = df.rename(columns=rename)
needed = ["open", "high", "low", "close"]
if not all(c in df.columns for c in needed):
return pd.DataFrame()
​for c in needed + (["volume"] if "volume" in df.columns else []):
df[c] = pd.to_numeric(df[c], errors="coerce")
​return df.dropna(subset=needed).reset_index(drop=True)
except Exception:
return pd.DataFrame()
​=========================================================
​TECHNICAL INDICATORS
​=========================================================
​def add_indicators(df):
df = df.copy()
if df.empty:
return df
​close = df["close"]
high = df["high"]
low = df["low"]
​df["EMA20"] = close.ewm(span=20, adjust=False).mean()
df["EMA50"] = close.ewm(span=50, adjust=False).mean()
​delta = close.diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)
avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()
​rs = avg_gain / avg_loss.replace(0, np.nan)
df["RSI"] = 100 - (100 / (1 + rs))
​ema12 = close.ewm(span=12, adjust=False).mean()
ema26 = close.ewm(span=26, adjust=False).mean()
df["MACD"] = ema12 - ema26
df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
​tr1 = high - low
tr2 = (high - close.shift()).abs()
tr3 = (low - close.shift()).abs()
tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
atr = tr.rolling(14).mean()
​plus_dm = high.diff()
minus_dm = -low.diff()
plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
​plus_di = 100 * plus_dm.rolling(14).sum() / atr.rolling(14).sum()
minus_di = 100 * minus_dm.rolling(14).sum() / atr.rolling(14).sum()
dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
df["ADX"] = dx.rolling(14).mean()
​if "volume" in df.columns:
typical = (high + low + close) / 3
cumulative_volume = df["volume"].cumsum()
df["VWAP"] = (typical * df["volume"]).cumsum() / cumulative_volume.replace(0, np.nan)
df["VOL_AVG20"] = df["volume"].rolling(20).mean()
else:
df["VWAP"] = np.nan
df["VOL_AVG20"] = np.nan
​return df
​=========================================================
​LIVE MARKET ANALYSIS ENGINE
​=========================================================
​def analyze_market(symbol, derivatives_proxy=None):
result = {
"symbol": symbol,
"trend": "UNKNOWN",
"momentum": "NEUTRAL",
"rsi": None,
"adx": None,
"ema20": None,
"ema50": None,
"macd": None,
"macd_signal": None,
"vwap": None,
"volume_ratio": None,
"support": None,
"resistance": None,
"last": None,
"technical_score": 0,
"institutional_score": 0,
"institutional_bias": "UNAVAILABLE",
"institutional_source": "NONE",
"score": 0,
"reasons": [],
}
​live_last = get_spot(symbol)
df5 = add_indicators(fetch_ohlcv(symbol, "FIVE_MINUTE", 5))
​if df5.empty:
result["last"] = live_last
return result
​row = df5.iloc[-1]
last = live_last if live_last is not None else num(row.get("close"))
result["last"] = last
result["rsi"] = num(row.get("RSI"))
result["adx"] = num(row.get("ADX"))
result["ema20"] = num(row.get("EMA20"))
result["ema50"] = num(row.get("EMA50"))
result["macd"] = num(row.get("MACD"))
result["macd_signal"] = num(row.get("MACD_SIGNAL"))
result["vwap"] = num(row.get("VWAP"))
​if "volume" in df5.columns and num(row.get("volume")) is not None and num(row.get("VOL_AVG20")) not in [None, 0]:
result["volume_ratio"] = num(row.get("volume")) / num(row.get("VOL_AVG20"))
​recent = df5.tail(30)
result["support"] = num(recent["low"].min())
result["resistance"] = num(recent["high"].max())
​score = 0
if result["ema20"] is not None and result["ema50"] is not None and last is not None:
if last > result["ema20"] > result["ema50"]:
score += 2
result["reasons"].append("Price EMA20 aur EMA50 ke upar hai.")
elif last < result["ema20"] < result["ema50"]:
score -= 2
result["reasons"].append("Price EMA20 aur EMA50 ke neeche hai.")
​if result["vwap"] is not None and last is not None:
if last > result["vwap"]:
score += 1
result["reasons"].append("Price VWAP ke upar hai.")
elif last < result["vwap"]:
score -= 1
result["reasons"].append("Price VWAP ke neeche hai.")
​if result["macd"] is not None and result["macd_signal"] is not None:
if result["macd"] > result["macd_signal"]:
score += 1
result["reasons"].append("MACD bullish side par hai.")
else:
score -= 1
result["reasons"].append("MACD bearish side par hai.")
​if result["rsi"] is not None:
if result["rsi"] >= 60:
score += 1
result["momentum"] = "BULLISH"
elif result["rsi"] <= 40:
score -= 1
result["momentum"] = "BEARISH"
​if result["adx"] is not None and result["adx"] >= 20:
result["reasons"].append(f"ADX {result['adx']:.1f}, trend strength active.")
​if result["volume_ratio"] is not None and result["volume_ratio"] >= 1.3:
result["reasons"].append("Volume average se significantly higher hai.")
​result["technical_score"] = score
​# Institutional Flow Integration
if fii_dii.get("available"):
institutional_score = int(fii_dii.get("institutional_score", 0))
result["institutional_score"] = institutional_score
result["institutional_bias"] = fii_dii.get("bias", "MIXED")
result["institutional_source"] = "ACTUAL FII/DII"
if institutional_score > 0:
result["reasons"].append("Actual FII/DII flow market direction ko support kar raha hai.")
elif institutional_score < 0:
result["reasons"].append("Actual FII/DII flow market direction par pressure daal raha hai.")
else:
result["reasons"].append("Actual FII/DII flow mixed/neutral hai.")
elif derivatives_proxy is not None and derivatives_proxy.get("available"):
institutional_score = int(derivatives_proxy.get("score", 0))
result["institutional_score"] = institutional_score
result["institutional_bias"] = derivatives_proxy.get("bias", "DERIVATIVES PROXY")
result["institutional_source"] = "LIVE DERIVATIVES PROXY"
result["reasons"].append("Actual FII/DII pending hai; live option-chain positioning use hui hai.")
for r in derivatives_proxy.get("reasons", []):
result["reasons"].append(r)
else:
result["institutional_score"] = 0
result["institutional_bias"] = "FII/DII PENDING"
result["institutional_source"] = "NONE"
​result["score"] = score + result["institutional_score"]
if result["score"] >= 4:
result["trend"] = "BULLISH"
elif result["score"] <= -4:
result["trend"] = "BEARISH"
else:
result["trend"] = "SIDEWAYS"
​return result
​=========================================================
​OPTION SELECTION
​=========================================================
​def nearest_option(chain, spot, side):
if chain.empty or spot is None:
return None
type_col = find_column(chain, ["option_type", "optionType", "optionTypeName", "type"])
strike_col = find_column(chain, ["strike", "strikePrice", "strike_price"])
if type_col is None or strike_col is None:
return None
​work = chain.copy()
work["_type"] = work[type_col].map(normalize_option_type)
work = work[work["_type"] == side].copy()
if work.empty:
return None
​work["_strike"] = pd.to_numeric(
work[strike_col].astype(str).str.replace(",", "", regex=False),
errors="coerce",
)
work = work.dropna(subset=["_strike"])
if work.empty:
return None
​work["_distance"] = (work["_strike"] - spot).abs()
return work.sort_values("_distance").iloc[0]
​def option_ltp(row):
return num(first_value(row, ["ltp", "LTP", "lastTradedPrice", "last_price"]))
​=========================================================
​MULTI-TIMEFRAME CONFIRMATION
​=========================================================
​@st.cache_data(ttl=30, show_spinner=False)
def fetch_confirmation_timeframe(symbol, interval, days):
try:
df = fetch_ohlcv(symbol, interval, days)
return add_indicators(df) if not df.empty else pd.DataFrame()
except Exception:
return pd.DataFrame()
​def analyze_confirmation_timeframe(df, label):
result = {
"label": label,
"available": False,
"trend": "UNKNOWN",
"score": 0,
"last": None,
"ema20": None,
"ema50": None,
"rsi": None,
"adx": None,
"vwap": None,
"volume_ratio": None,
"structure": "UNKNOWN",
"reasons": [],
}
​if df is None or df.empty:
return result
row = df.iloc[-1]
last = num(row.get("close"))
if last is None:
return result
​result["available"] = True
result["last"] = last
result["ema20"] = num(row.get("EMA20"))
result["ema50"] = num(row.get("EMA50"))
result["rsi"] = num(row.get("RSI"))
result["adx"] = num(row.get("ADX"))
result["vwap"] = num(row.get("VWAP"))
​score = 0
if result["ema20"] is not None and result["ema50"] is not None:
if last > result["ema20"] > result["ema50"]:
score += 2
elif last < result["ema20"] < result["ema50"]:
score -= 2
​if result["vwap"] is not None:
score += 1 if last > result["vwap"] else -1
​if result["rsi"] is not None:
if result["rsi"] >= 55: score += 1
elif result["rsi"] <= 45: score -= 1
​result["score"] = score
result["trend"] = "BULLISH" if score >= 2 else ("BEARISH" if score <= -2 else "NEUTRAL")
return result
​def build_trade_confirmation(symbol, market):
confirmation = {
"available": False,
"status": "WAIT",
"direction": "NEUTRAL",
"score": 0,
"max_score": 0,
"strength": 0,
"timeframes": {},
"checks": [],
"reasons": [],
"warnings": [],
}
​configs = [("5M", "FIVE_MINUTE", 5), ("15M", "FIFTEEN_MINUTE", 10), ("1H", "ONE_HOUR", 20)]
results = []
for label, interval, days in configs:
df = fetch_confirmation_timeframe(symbol, interval, days)
analysis = analyze_confirmation_timeframe(df, label)
confirmation["timeframes"][label] = analysis
if analysis["available"]:
results.append(analysis)
​if not results:
confirmation["warnings"].append("Multi-timeframe data unavailable.")
return confirmation
​confirmation["available"] = True
bullish_votes = sum(1 for x in results if x["trend"] == "BULLISH")
bearish_votes = sum(1 for x in results if x["trend"] == "BEARISH")
​if bullish_votes >= 2 and bullish_votes > bearish_votes:
direction = "BULLISH"
elif bearish_votes >= 2 and bearish_votes > bullish_votes:
direction = "BEARISH"
else:
direction = "NEUTRAL"
​confirmation["direction"] = direction
raw_score = sum(x["score"] for x in results)
confirmation["score"] = raw_score
max_possible = len(results) * 7
confirmation["max_score"] = max_possible
if max_possible > 0:
confirmation["strength"] = round(min(100, abs(raw_score) / max_possible * 100), 1)
​final_score = confirmation["score"]
if direction == "BULLISH":
confirmation["status"] = "CONFIRMED" if final_score >= 4 else ("WATCH" if final_score >= 1 else "REJECT")
elif direction == "BEARISH":
confirmation["status"] = "CONFIRMED" if final_score <= -4 else ("WATCH" if final_score <= -1 else "REJECT")
else:
confirmation["status"] = "WATCH"
​return confirmation
​=========================================================
​TRADE IDEA GENERATION
​=========================================================
​def make_trade_idea(market, symbol, instrument="INDEX", option_side=None, expiry=None, chain=None):
last = market.get("last")
if last is None:
return None
​try:
entry_spot = float(last)
except Exception:
return None
​technical_score = float(market.get("technical_score", 0) or 0)
institutional_score = float(market.get("institutional_score", 0) or 0)
score = float(market.get("score", technical_score + institutional_score) or 0)
​confirmation = build_trade_confirmation(symbol, market)
if confirmation.get("status") == "REJECT":
return None
​if score >= 2:
bullish = True
elif score <= -2:
bullish = False
else:
if technical_score > 0: bullish = True
elif technical_score < 0: bullish = False
else: return None
​direction = "BUY" if bullish else "SELL"
support = market.get("support")
resistance = market.get("resistance")
​try: support = float(support) if support is not None else None
except Exception: support = None
​try: resistance = float(resistance) if resistance is not None else None
except Exception: resistance = None
​if bullish:
sl = support if (support is not None and support < entry_spot) else (entry_spot * 0.997)
risk = entry_spot - sl
if risk <= 0: return None
target1 = entry_spot + (risk * 1.5)
target2 = entry_spot + (risk * 2.5)
else:
sl = resistance if (resistance is not None and resistance > entry_spot) else (entry_spot * 1.003)
risk = sl - entry_spot
if risk <= 0: return None
target1 = entry_spot - (risk * 1.5)
target2 = entry_spot - (risk * 2.5)
​confidence = min(95, max(65, 65 + abs(score) * 4 + abs(institutional_score) * 2))
​idea = {
"segment": instrument,
"symbol": symbol,
"action": direction,
"entry": entry_spot,
"sl": sl,
"target1": target1,
"target2": target2,
"risk_reward": abs(target1 - entry_spot) / risk if risk > 0 else 0,
"confidence": confidence,
"holding": "Intraday" if market_open() else "NEXT SESSION",
"expiry": expiry,
"option": None,
"strike": None,
"option_ltp": None,
"delta": None, "gamma": None, "theta": None, "vega": None, "iv": None,
"oi": None, "change_oi": None,
"technical_score": technical_score,
"institutional_score": institutional_score,
"institutional_bias": market.get("institutional_bias", "UNAVAILABLE"),
"institutional_source": market.get("institutional_source", "NONE"),
"why": " ".join(market.get("reasons", [])[:6]),
"invalidation": f"Price {'below' if bullish else 'above'} SL level sustain kare.",
}
​if instrument == "INDEX OPTION" and chain is not None and not chain.empty:
option_type = option_side if option_side in ["CE", "PE"] else ("CE" if bullish else "PE")
selected = nearest_option(chain, entry_spot, option_type)
if selected is not None:
strike = first_value(selected, ["strike", "strikePrice", "strike_price"])
option_price = option_ltp(selected)
idea["option"] = option_type
idea["action"] = "BUY"
idea["strike"] = strike
idea["option_ltp"] = option_price
idea["oi"] = num(first_value(selected, ["openInterest", "opnInterest", "oi"]))
idea["change_oi"] = num(first_value(selected, ["changeInOpenInterest", "change_oi"]))
idea["delta"] = num(first_value(selected, ["delta"]))
idea["gamma"] = num(first_value(selected, ["gamma"]))
idea["theta"] = num(first_value(selected, ["theta"]))
idea["vega"] = num(first_value(selected, ["vega"]))
idea["iv"] = num(first_value(selected, ["impliedVolatility", "iv"]))
​if option_price is not None and option_price > 0:
idea["entry"] = option_price
idea["sl"] = option_price * 0.85
idea["target1"] = option_price * 1.20
idea["target2"] = option_price * 1.35
opt_risk = option_price - idea["sl"]
idea["risk_reward"] = (idea["target1"] - option_price) / opt_risk if opt_risk > 0 else 1.35
​idea["why"] += f" BUY {option_type} ATM Strike {strike} selected based on momentum."
​return idea
​=========================================================
​TIME MACHINE — HISTORICAL 10-MINUTE REPLAY
​=========================================================
​@st.cache_data(ttl=300, show_spinner=False)
def load_time_machine_data(symbol, replay_date):
if symbol not in SPOT_TOKENS:
return pd.DataFrame()
​try:
target = replay_date if isinstance(replay_date, date) else date.fromisoformat(str(replay_date))
days = max(5, min(30, (date.today() - target).days + 5))
​raw = telemetry.fetch_ohlcv(
exchange=SPOT_TOKENS[symbol][0],
token=SPOT_TOKENS[symbol][1],
interval="TEN_MINUTE",
days=days,
) if telemetry is not None else pd.DataFrame()
​df = clean_df(raw)
if df.empty:
return pd.DataFrame()
​rename = {}
for c in df.columns:
lc = str(c).lower()
if lc in ["open", "o"]: rename[c] = "open"
elif lc in ["high", "h"]: rename[c] = "high"
elif lc in ["low", "l"]: rename[c] = "low"
elif lc in ["close", "c", "ltp"]: rename[c] = "close"
elif lc in ["volume", "vol"]: rename[c] = "volume"
elif lc in ["datetime", "timestamp", "time", "date"]: rename[c] = "timestamp"
​df = df.rename(columns=rename)
if "timestamp" not in df.columns:
if isinstance(df.index, pd.DatetimeIndex):
df = df.reset_index().rename(columns={df.index.name or "index": "timestamp"})
else:
return pd.DataFrame()
​for c in ["open", "high", "low", "close"]:
if c not in df.columns:
return pd.DataFrame()
df[c] = pd.to_numeric(df[c], errors="coerce")
​if "volume" in df.columns:
df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
​ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
if ts.isna().all():
ts = pd.to_datetime(df["timestamp"], errors="coerce")
​try:
if getattr(ts.dt, "tz", None) is None:
ts = ts.dt.tz_localize(IST)
else:
ts = ts.dt.tz_convert(IST)
except Exception:
return pd.DataFrame()
​df["timestamp"] = ts
df = df.dropna(subset=["timestamp", "open", "high", "low", "close"])
df = df[df["timestamp"].dt.date == target].copy()
df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
​return add_indicators(df) if not df.empty else df
except Exception:
return pd.DataFrame()
​def time_machine_snapshot(df, candle_index):
if df is None or df.empty:
return pd.DataFrame()
try:
idx = max(0, min(int(candle_index), len(df) - 1))
return df.iloc[:idx + 1].copy()
except Exception:
return pd.DataFrame()
​def time_machine_signal(snapshot):
result = {
"signal": "WAIT",
"trend": "UNKNOWN",
"rsi": None,
"adx": None,
"ema20": None,
"ema50": None,
"vwap": None,
"support": None,
"resistance": None,
"score": 0,
}
​if snapshot is None or snapshot.empty:
return result
​row = snapshot.iloc[-1]
last = num(row.get("close"))
ema20 = num(row.get("EMA20"))
ema50 = num(row.get("EMA50"))
rsi = num(row.get("RSI"))
adx = num(row.get("ADX"))
vwap = num(row.get("VWAP"))
​score = 0
if last is not None and ema20 is not None: score += 1 if last > ema20 else -1
if ema20 is not None and ema50 is not None: score += 1 if ema20 > ema50 else -1
if rsi is not None:
if rsi >= 55: score += 1
elif rsi <= 45: score -= 1
if vwap is not None and last is not None: score += 1 if last > vwap else -1
​if score >= 3: signal, trend = "BUY BIAS", "BULLISH"
elif score <= -3: signal, trend = "SELL BIAS", "BEARISH"
else: signal, trend = "WAIT", "SIDEWAYS / MIXED"
​recent = snapshot.tail(min(20, len(snapshot)))
support = num(recent["low"].min()) if "low" in recent.columns else None
resistance = num(recent["high"].max()) if "high" in recent.columns else None
​result.update({
"signal": signal, "trend": trend, "rsi": rsi, "adx": adx,
"ema20": ema20, "ema50": ema50, "vwap": vwap,
"support": support, "resistance": resistance, "score": score,
})
return result
​=========================================================
​AI GEMINI ASSISTANT
​=========================================================
​def ask_gemini(ideas, market_data):
if not GEMINI_API_KEY:
return None
try:
from google import genai
client = genai.Client(api_key=GEMINI_API_KEY)
payload = {"market": market_data, "ideas": ideas, "fii_dii": fii_dii}
prompt = f"""
You are an Indian market research assistant for a PAPER TRADING ONLY application.
Use ONLY supplied data. Concisely explain technical setup, institutional input, options context, and risk invalidation.
DATA:
{json.dumps(payload, default=str)}
"""
response = client.models.generate_content(
model=GEMINI_MODEL,
contents=prompt,
)
return getattr(response, "text", None)
except Exception as e:
return f"AI explanation unavailable: {e}"
​=========================================================
​SIDEBAR & LIVE STREAM CONTROLS
​=========================================================
​st.sidebar.header("⚙️ Expert Advisor")
​old_underlying = st.session_state.get("underlying", "NIFTY")
if old_underlying not in UNDERLYINGS:
old_underlying = "NIFTY"
​underlying = st.sidebar.selectbox(
"Underlying",
UNDERLYINGS,
index=UNDERLYINGS.index(old_underlying),
)
st.session_state["underlying"] = underlying
​expiries = load_expiries(underlying)
selected_expiry = None
if expiries:
old_expiry = st.session_state.get("expiry")
if old_expiry not in expiries:
old_expiry = expiries[0]
selected_expiry = st.sidebar.selectbox(
"Expiry",
expiries,
index=expiries.index(old_expiry),
format_func=expiry_label,
)
st.session_state["expiry"] = selected_expiry
else:
st.sidebar.info("Expiry data unavailable")
​option_type = st.sidebar.selectbox("Option Type", ["CE", "PE", "BOTH"])
​--- LIVE MARKET STREAM CONTROLS ---
​st.sidebar.markdown("---")
st.sidebar.subheader("📡 Live Market Stream")
live_stream_active = st.sidebar.toggle(
"🔴 Live Streaming Active",
value=True,
help="Continuous real-time broker tick auto-refresh.",
)
stream_interval = st.sidebar.select_slider(
"Refresh Speed",
options=[1, 2, 3, 5, 10],
value=2,
format_func=lambda s: f"{s} sec",
help="Interval between live market price updates.",
)
force_stream = st.sidebar.checkbox(
"Stream After-Hours (Simulate)",
value=False,
help="Allows streaming updates even when normal market session is closed.",
)
​if st.sidebar.button("🔄 Manual Force Refresh", use_container_width=True):
st.cache_data.clear()
st.rerun()
​=========================================================
​LIVE TICK CALCULATION & HEADER
​=========================================================
​current_time_str = datetime.now(IST).strftime("%H:%M:%S")
is_open = market_open()
should_stream = live_stream_active and (is_open or force_stream)
​Spot Price & Delta Tracker
​spot = get_spot(underlying)
prev_spot_key = f"prev_spot{underlying}"
prev_spot = st.session_state.get(prev_spot_key, spot)
spot_delta = (spot - prev_spot) if (spot is not None and prev_spot is not None) else 0.0
st.session_state[prev_spot_key] = spot
​h_top1, h_top2 = st.columns([2, 1])
with h_top1:
st.title("📊 AI Trading Expert Advisor")
st.caption("Live Market Streaming • Derivatives • Technical Flow • Paper Trading")
​with h_top2:
st.write("")
if should_stream:
st.markdown(
f"""
<div style="text-align:right;">
<div class="live-pulse-container">
<span class="live-pulse-dot"></span>
LIVE STREAM ACTIVE • {current_time_str} IST
</div>
</div>
""",
unsafe_allow_html=True,
)
else:
st.markdown(
f"""
<div style="text-align:right;">
<div class="live-pulse-paused">
⏸️ STREAM PAUSED / SESSION CLOSED
</div>
</div>
""",
unsafe_allow_html=True,
)
​Metrics Ribbon
​h1, h2, h3, h4 = st.columns(4)
with h1:
st.metric("Streaming Feed", f"ACTIVE ({stream_interval}s)" if should_stream else "PAUSED")
with h2:
st.metric("Market Status", "SESSION OPEN" if is_open else "AFTER MARKET")
with h3:
st.metric("Angel One Broker", "CONNECTED" if telemetry is not None else "NOT CONNECTED")
with h4:
st.metric("AI Status", "GEMINI READY" if GEMINI_API_KEY else "TECHNICAL MODE")
​=========================================================
​CURRENT MARKET BANNER
​=========================================================
​chain = pd.DataFrame()
if selected_expiry:
chain, all_contracts = get_chain(underlying, selected_expiry, spot)
​pcr = calculate_pcr(chain)
derivatives_proxy = calculate_live_derivatives_proxy(chain, pcr)
market = analyze_market(underlying, derivatives_proxy)
​st.subheader("📌 Live Spot & Positioning")
​m1, m2, m3, m4 = st.columns(4)
with m1:
st.metric("Underlying", underlying)
with m2:
st.metric(
"Live LTP",
fmt(spot),
delta=f"{spot_delta:+.2f}" if abs(spot_delta) >= 0.01 else None,
)
with m3:
st.metric("Expiry", expiry_label(selected_expiry) if selected_expiry else "-")
with m4:
st.metric("Live Trend", market.get("trend", "UNKNOWN"))
​=========================================================
​TOMORROW MARKET BLUEPRINT
​=========================================================
​st.markdown("## 🔮 Tomorrow Market Blueprint")
​if build_tomorrow_forecast is None:
st.warning("Tomorrow Forecast Engine unavailable.")
else:
try:
tomorrow_data = {
"symbol": underlying,
"spot": spot,
"support": market.get("support"),
"resistance": market.get("resistance"),
"rsi": market.get("rsi"),
"adx": market.get("adx"),
"ema20": market.get("ema20"),
"ema50": market.get("ema50"),
"vwap": market.get("vwap"),
"technical_score": market.get("technical_score", 0),
"institutional_score": market.get("institutional_score", 0),
"score": market.get("score", 0),
"institutional_bias": market.get("institutional_bias", "UNAVAILABLE"),
"pcr": pcr,
"fii_net": fii_dii.get("fii_net"),
"dii_net": fii_dii.get("dii_net"),
}
tomorrow = build_tomorrow_forecast(tomorrow_data)
if tomorrow:
c1, c2, c3, c4 = st.columns(4)
c1.metric("Next Session Bias", tomorrow.get("bias", "N/A"))
c2.metric("Forecast Confidence", f"{tomorrow.get('confidence', 0):.0f}%")
c3.metric("Combined Score", f"{tomorrow.get('combined_score', 0):+.1f}")
c4.metric("Data Quality", tomorrow.get("data_quality", "N/A"))
​st.markdown("### 📊 Reference Levels")
r1, r2, r3, r4 = st.columns(4)
r1.metric("Reference Spot", f"{tomorrow.get('spot', 0):,.2f}" if tomorrow.get("spot") is not None else "N/A")
r2.metric("Support", f"{tomorrow.get('support', 0):,.2f}" if tomorrow.get("support") is not None else "N/A")
r3.metric("Resistance", f"{tomorrow.get('resistance', 0):,.2f}" if tomorrow.get("resistance") is not None else "N/A")
r4.metric(
"Expected Range",
(
f"{tomorrow['expected_range']['low']:,.2f} - {tomorrow['expected_range']['high']:,.2f}"
if isinstance(tomorrow.get("expected_range"), dict)
and tomorrow["expected_range"].get("low") is not None
and tomorrow["expected_range"].get("high") is not None
else "N/A"
),
)
except Exception as e:
st.warning(f"Tomorrow Market Blueprint unavailable: {e}")
​=========================================================
​INSTITUTIONAL FLOW & DERIVATIVES PROXY
​=========================================================
​st.subheader("🏦 Institutional Flow")
​if fii_dii["available"]:
f1, f2, f3, f4 = st.columns(4)
with f1: st.metric("FII Net", f"₹{fmt(fii_dii['fii_net'], 0)} Cr" if fii_dii["fii_net"] is not None else "Unavailable")
with f2: st.metric("DII Net", f"₹{fmt(fii_dii['dii_net'], 0)} Cr" if fii_dii["dii_net"] is not None else "Unavailable")
with f3: st.metric("Combined Net", f"₹{fmt(fii_dii['combined_net'], 0)} Cr" if fii_dii["combined_net"] is not None else "Unavailable")
with f4: st.metric("Institutional Score", f"{fii_dii['institutional_score']:+d}")
else:
st.warning("Actual FII/DII cash-flow data abhi unavailable hai. Live derivatives proxy use ho rahi hai.")
​st.subheader("🧮 Derivatives Institutional Proxy")
if derivatives_proxy.get("available"):
d1, d2, d3 = st.columns(3)
with d1: st.metric("Proxy Score", f"{derivatives_proxy['score']:+d}")
with d2: st.metric("Proxy Bias", derivatives_proxy["bias"])
with d3: st.metric("PCR", fmt(derivatives_proxy.get("pcr"), 2) if derivatives_proxy.get("pcr") is not None else "-")
​=========================================================
​MARKET INTELLIGENCE METRICS
​=========================================================
​st.subheader("📈 Real-Time Technical Intelligence")
​a1, a2, a3, a4 = st.columns(4)
with a1: st.metric("Trend", market["trend"])
with a2: st.metric("Momentum", market["momentum"])
with a3: st.metric("RSI (14)", fmt(market["rsi"], 1))
with a4: st.metric("ADX", fmt(market["adx"], 1))
​a5, a6, a7, a8 = st.columns(4)
with a5: st.metric("EMA 20", fmt(market["ema20"]))
with a6: st.metric("EMA 50", fmt(market["ema50"]))
with a7: st.metric("VWAP", fmt(market["vwap"]))
with a8: st.metric("Volume Ratio", fmt(market["volume_ratio"], 2))
​if market["reasons"]:
with st.expander("🔍 View Active Signals & Triggers", expanded=True):
for reason in market["reasons"]:
st.write("• " + reason)
​=========================================================
​OPTION CHAIN DISPLAY
​=========================================================
​if not chain.empty:
with st.expander(f"🧮 Live Option Chain: {underlying} ({expiry_label(selected_expiry)})", expanded=True):
display_cols = [
"strikePrice", "option_type", "ltp", "tradeVolume",
"openInterest", "changeInOpenInterest", "delta", "iv"
]
cols = [c for c in display_cols if c in chain.columns]
view = chain.copy()
type_col = find_column(view, ["option_type", "optionType"])
if option_type in ["CE", "PE"] and type_col:
view = view[view[type_col].map(normalize_option_type).eq(option_type)]
st.dataframe(view[cols].sort_values("strikePrice"), use_container_width=True, hide_index=True)
​=========================================================
​TIME MACHINE UI (HISTORICAL 10-MIN REPLAY)
​=========================================================
​st.divider()
st.subheader("📼 Time Machine — 10 Minute Market Replay")
st.caption("Historical replay only. Har step par analysis sirf us waqt tak ki candles use karta hai.")
​_tm_today = date.today()
_tm_default = _tm_today - timedelta(days=1)
if _tm_default.weekday() >= 5:
_tm_default = _tm_today - timedelta(days=2)
​_tm_date = st.date_input("Replay Date", value=_tm_default, key="tm_date")
_tm_col1, _tm_col2 = st.columns(2)
with _tm_col1:
tm_symbol = st.selectbox("Replay Market", UNDERLYINGS, index=UNDERLYINGS.index(underlying) if underlying in UNDERLYINGS else 0, key="tm_symbol")
with _tm_col2:
tm_interval = st.selectbox("Replay Interval", ["10 Minutes"], key="tm_interval")
​if st.button("📥 Load Historical Session", use_container_width=True, key="tm_load"):
st.session_state["tm_loaded"] = True
st.session_state["tm_index"] = 0
​if st.session_state.get("tm_loaded", False):
tm_df = load_time_machine_data(tm_symbol, _tm_date)
if tm_df.empty:
st.warning("Is date ke liye 10-minute historical candle data available nahi mila.")
st.session_state["tm_loaded"] = False
else:
tm_max = len(tm_df) - 1
tm_index = int(st.session_state.get("tm_index", 0))
tm_index = max(0, min(tm_index, tm_max))
​tm_index = st.slider("Replay Position", min_value=0, max_value=tm_max, value=tm_index, step=1, key="tm_slider")
st.session_state["tm_index"] = tm_index
​tm_left, tm_mid, tm_right = st.columns(3)
with tm_left:
if st.button("◀ Previous 10 Min", use_container_width=True, key="tm_prev"):
st.session_state["tm_index"] = max(0, tm_index - 1)
st.rerun()
with tm_mid:
if st.button("▶ Next 10 Min", type="primary", use_container_width=True, key="tm_next"):
st.session_state["tm_index"] = min(tm_max, tm_index + 1)
st.rerun()
with tm_right:
if st.button("⏮ Start", use_container_width=True, key="tm_start"):
st.session_state["tm_index"] = 0
st.rerun()
​tm_snapshot = time_machine_snapshot(tm_df, tm_index)
tm_row = tm_snapshot.iloc[-1]
tm_sig = time_machine_signal(tm_snapshot)
tm_time = tm_row["timestamp"].strftime("%H:%M")
​st.success(f"Replay time: {tm_time} • Candle {tm_index + 1}/{len(tm_df)}")
t1, t2, t3, t4 = st.columns(4)
with t1: st.metric("Price", fmt(tm_row.get("close")))
with t2: st.metric("Signal", tm_sig["signal"])
with t3: st.metric("Trend", tm_sig["trend"])
with t4: st.metric("Score", f"{tm_sig['score']:+d}")
​=========================================================
​AI TRADE IDEAS (PERSISTENT WITH AUTO-STREAMING)
​=========================================================
​st.divider()
st.subheader("🎯 AI Trade Setups")
​col_btn1, col_btn2 = st.columns([3, 1])
with col_btn1:
if st.button("🚀 GENERATE / UPDATE TRADE IDEAS", type="primary", use_container_width=True):
st.session_state["ideas_active"] = True
with col_btn2:
if st.button("Clear Setups", use_container_width=True):
st.session_state["ideas_active"] = False
​if st.session_state.get("ideas_active", True):
ideas = []
base_idea = make_trade_idea(market, underlying, "INDEX", expiry=selected_expiry, chain=chain)
if base_idea: ideas.append(base_idea)
​option_idea = make_trade_idea(market, underlying, "INDEX OPTION", expiry=selected_expiry, chain=chain)
if option_idea: ideas.append(option_idea)
​if not ideas:
st.info("Market structure is currently consolidating. No high-probability setup confirmed.")
else:
for i, idea in enumerate(ideas, start=1):
st.markdown(
f"""
<div class="trade-card">
<h3>Setup {i} — {idea['symbol']} ({idea['segment']})</h3>
<div class="small">Holding: {idea['holding']} | Action: {idea['action']} | Confidence: {idea['confidence']:.0f}%</div>
</div>
""",
unsafe_allow_html=True,
)
c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("Action", idea["action"])
with c2: st.metric("Entry Price", fmt(idea["entry"]))
with c3: st.metric("Stop Loss", fmt(idea["sl"]))
with c4: st.metric("Target 1", fmt(idea["target1"]))
​st.write(f"Trigger Reason: {idea['why']}")
st.caption(f"Invalidation Level: {idea['invalidation']}")
​if GEMINI_API_KEY:
with st.expander("🤖 AI Assistant Explanation", expanded=False):
ai_text = ask_gemini(ideas, {"underlying": underlying, "spot": spot, "trend": market["trend"]})
if ai_text: st.write(ai_text)
​=========================================================
​FUTURE EYES — DECISION VS ACTUAL VALIDATION
​=========================================================
​st.divider()
st.subheader("👁️ Future Eyes — Decision vs Actual")
st.caption("Historical research only. Decision ke waqt sirf visible candles use hoti hain.")
​if FutureEyes is None:
st.warning("Future Eyes module unavailable hai.")
else:
_fe_today = date.today()
_fe_default = _fe_today - timedelta(days=1)
if _fe_default.weekday() >= 5:
_fe_default = _fe_today - timedelta(days=2)
​fe_date = st.date_input("Future Eyes Replay Date", value=_fe_default, key="fe_date")
fe_c1, fe_c2 = st.columns(2)
with fe_c1:
fe_symbol = st.selectbox("Future Eyes Market", UNDERLYINGS, index=UNDERLYINGS.index(underlying) if underlying in UNDERLYINGS else 0, key="fe_symbol")
with fe_c2:
fe_horizon = st.selectbox("Validation Horizon", [1, 2, 3], index=0, format_func=lambda x: f"Next {x} candle(s)", key="fe_horizon")
​if st.button("👁️ Load Future Eyes", type="primary", use_container_width=True, key="fe_load"):
st.session_state["fe_loaded"] = True
st.session_state["fe_index"] = 0
​if st.session_state.get("fe_loaded", False):
try:
_fe_engine = FutureEyes(fetch_ohlcv=fetch_ohlcv, interval="TEN_MINUTE")
_fe_df = _fe_engine.load_session(fe_symbol, fe_date, days=30)
if _fe_df.empty:
st.warning("Selected date ke liye Future Eyes data available nahi mila.")
st.session_state["fe_loaded"] = False
else:
_fe_max = len(_fe_df) - 1
_fe_idx = int(st.session_state.get("fe_index", 0))
_fe_idx = max(0, min(_fe_idx, _fe_max))
_fe_idx = st.slider("Decision Checkpoint", min_value=0, max_value=_fe_max, value=_fe_idx, step=1, key="fe_slider")
st.session_state["fe_index"] = _fe_idx
​_fe_point = _fe_engine.point(_fe_df, _fe_idx)
_fe_visible = add_indicators(_fe_point.visible.copy())
_fe_signal = time_machine_signal(_fe_visible)
​st.success(f"Decision checkpoint: {_fe_point.timestamp.strftime('%H:%M')} • Visible: {len(_fe_point.visible)}")
fv1, fv2, fv3, fv4 = st.columns(4)
with fv1: st.metric("Decision", _fe_signal["signal"])
with fv2: st.metric("Score", f"{_fe_signal['score']:+d}")
with fv3: st.metric("RSI", fmt(_fe_signal["rsi"]))
with fv4: st.metric("ADX", fmt(_fe_signal["adx"]))
except Exception as _fe_error:
st.error(f"Future Eyes error: {_fe_error}")
​=========================================================
​LIVE STREAM AUTO-REFRESH EXECUTION
​=========================================================
​if should_stream:
time.sleep(stream_interval)
st.rerun()
