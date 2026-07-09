import yfinance as yf
import pandas as pd
import numpy as np
import json, os, requests, argparse
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────────────────────
# SUPABASE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
SB_URL = 'https://scnvnfrvxwrdwskcktnj.supabase.co'
SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNjbnZuZnJ2eHdyZHdza2NrdG5qIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM0MDE1MjYsImV4cCI6MjA5ODk3NzUyNn0.GmJ-C5mZORvPGgdp2JFDlZXamBQRwUOgAZjBmHm69C4'
SB_HDR = {
    'apikey'       : SB_KEY,
    'Authorization': f'Bearer {SB_KEY}',
    'Content-Type' : 'application/json',
    'Prefer'       : 'resolution=merge-duplicates,return=minimal',
}

# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK UNIVERSE — used only if Supabase is unreachable
# ─────────────────────────────────────────────────────────────────────────────
FALLBACK_UNIVERSE = {
    'SILVERBEES':'SILVERBEES.NS','GOLDBEES':'GOLDBEES.NS','NIFTYBEES':'NIFTYBEES.NS',
    'TATSILV':'TATSILV.NS','HDFCSILVER':'HDFCSILVER.NS','SILVERIETF':'SILVERIETF.NS',
    'TATAGOLD':'TATAGOLD.NS','GOLDIETF':'GOLDIETF.NS','ITBEES':'ITBEES.NS',
    'SETFGOLD':'SETFGOLD.NS','BANKBEES':'BANKBEES.NS','HDFCGOLD':'HDFCGOLD.NS',
    'SBISILVER':'SBISILVER.NS','PVTBANIETF':'PVTBANIETF.NS','SILVER':'SILVER.NS',
    'PSUBNKBEES':'PSUBNKBEES.NS','JUNIORBEES':'JUNIORBEES.NS','GOLD1':'GOLD1.NS',
    'HDFCSML250':'HDFCSML250.NS','MON100':'MON100.NS','MODEFENCE':'MODEFENCE.NS',
    'MID150BEES':'MID150BEES.NS','PHARMABEES':'PHARMABEES.NS','METALIETF':'METALIETF.NS',
    'CPSEETF':'CPSEETF.NS','MOREALTY':'MOREALTY.NS','NEXT50IETF':'NEXT50IETF.NS',
    'AUTOBEES':'AUTOBEES.NS','ALPHA':'ALPHA.NS','MOMENTUM50':'MOMENTUM50.NS',
    'GROWWPOWER':'GROWWPOWER.NS','MAFANG':'MAFANG.NS','MOM30IETF':'MOM30IETF.NS',
    'MONQ50':'MONQ50.NS','OILIETF':'OILIETF.NS','EQUAL50ADD':'EQUAL50ADD.NS',
    'CONSUMBEES':'CONSUMBEES.NS','INFRAIETF':'INFRAIETF.NS',
}

LOOKBACK_WEEKS = 13
N_SLOTS        = 3


# ─────────────────────────────────────────────────────────────────────────────
# SUPABASE HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def sb_get(path):
    try:
        r = requests.get(f'{SB_URL}/rest/v1/{path}', headers=SB_HDR, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f'  SB GET error: {e}')
    return None


def sb_upsert(table, rows):
    if not rows:
        return
    try:
        r = requests.post(f'{SB_URL}/rest/v1/{table}', headers=SB_HDR, json=rows, timeout=15)
        if r.status_code not in (200, 201, 204):
            print(f'  SB upsert error {table}: {r.status_code} {r.text[:200]}')
        else:
            print(f'  SB upsert OK: {table} ({len(rows)} rows)')
    except Exception as e:
        print(f'  SB upsert exception: {e}')


# ─────────────────────────────────────────────────────────────────────────────
# LOAD UNIVERSE FROM SUPABASE
# ─────────────────────────────────────────────────────────────────────────────
def load_universe():
    """
    Load ETF universe from Supabase etf_universe table.
    Falls back to FALLBACK_UNIVERSE if Supabase unreachable or empty.
    """
    rows = sb_get('etf_universe?user_id=eq.default&select=symbols')
    if rows and len(rows) > 0 and rows[0].get('symbols'):
        try:
            syms = json.loads(rows[0]['symbols'])
            if isinstance(syms, list) and len(syms) > 0:
                universe = {s: f'{s}.NS' for s in syms}
                print(f'Loaded {len(universe)} ETFs from Supabase universe')
                return universe
        except Exception as e:
            print(f'  Could not parse Supabase universe: {e}')
    print(f'Using fallback universe ({len(FALLBACK_UNIVERSE)} ETFs)')
    return FALLBACK_UNIVERSE


# ─────────────────────────────────────────────────────────────────────────────
# LOAD SETTINGS FROM SUPABASE
# ─────────────────────────────────────────────────────────────────────────────
def load_settings():
    """
    Load strategy settings from Supabase app_settings table.
    Falls back to defaults if not found.
    """
    defaults = {
        'slots'    : 3,
        'skim'     : 0.25,
        'lookback' : 13,
        'friction' : 0.0012,
        'liquid'   : 0.06,
        'capital'  : 300000,
    }
    rows = sb_get('app_settings?user_id=eq.default&select=settings')
    if rows and len(rows) > 0 and rows[0].get('settings'):
        try:
            s = json.loads(rows[0]['settings'])
            defaults.update(s)
            print(f'Loaded settings from Supabase: slots={defaults["slots"]} lookback={defaults["lookback"]}')
        except Exception as e:
            print(f'  Could not parse settings: {e}')
    else:
        print('Using default settings')
    return defaults


# ─────────────────────────────────────────────────────────────────────────────
# PRICE FETCHING
# ─────────────────────────────────────────────────────────────────────────────
def fetch_prices(universe, lookback_weeks, end_date, lookback_days=120):
    start_date = end_date - timedelta(days=lookback_days)
    prices = {}
    total  = len(universe)

    for i, (name, ticker) in enumerate(universe.items(), 1):
        try:
            df = yf.download(
                ticker,
                start=start_date.strftime('%Y-%m-%d'),
                end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                progress=False,
                auto_adjust=True
            )
            if df.empty or len(df) < 20:
                print(f'  [{i}/{total}] SKIP {name}: no data')
                continue

            close    = df['Close'].squeeze()
            weekly   = close.resample('W-MON').last().dropna()

            if len(weekly) < lookback_weeks + 1:
                print(f'  [{i}/{total}] SKIP {name}: insufficient history ({len(weekly)} weeks)')
                continue

            current  = float(weekly.iloc[-1])
            w13ago   = float(weekly.iloc[-lookback_weeks - 1])
            vel3m    = ((current - w13ago) / w13ago) * 100

            # Signal date = the Monday whose close we used
            # Use iloc[-2] date if last entry is future, else iloc[-1]
            # W-MON resampling: each label = the Monday of that week
            # The last complete Monday is iloc[-1] if today >= that Monday
            last_mon = weekly.index[-1]

            # Execution price = next actual trading day after signal Monday
            future  = close.index[close.index > last_mon]
            exec_px = float(close.loc[future[0]]) if len(future) > 0 else current
            exec_dt = str(future[0].date()) if len(future) > 0 else str(end_date.date())

            prices[name] = {
                'current'     : round(current, 2),
                'exec_price'  : round(exec_px, 2),
                'w13ago'      : round(w13ago, 2),
                'vel3m'       : round(vel3m, 4),
                'signal_date' : str(last_mon.date()),
                'exec_date'   : exec_dt,
            }
            print(f'  [{i}/{total}] {name}: {vel3m:+.2f}% close=₹{current}')

        except Exception as e:
            print(f'  [{i}/{total}] ERR {name}: {e}')

    return prices


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL GENERATION
# ─────────────────────────────────────────────────────────────────────────────
def generate_signal(prices, n_slots):
    ranked = sorted(
        [(n, d) for n, d in prices.items()],
        key=lambda x: x[1]['vel3m'], reverse=True
    )
    signal = []
    for i, (name, d) in enumerate(ranked[:n_slots]):
        signal.append({
            'rank'       : i + 1,
            'etf'        : name,
            'vel3m'      : d['vel3m'],
            'current_px' : d['current'],
            'exec_price' : d['exec_price'],
            'signal_date': d['signal_date'],
            'exec_date'  : d['exec_date'],
            'action'     : 'LIQUIDBEES' if d['vel3m'] < 0 else 'BUY_OR_HOLD',
        })
    return signal, ranked


# ─────────────────────────────────────────────────────────────────────────────
# PUSH SIGNAL HISTORY TO SUPABASE
# ─────────────────────────────────────────────────────────────────────────────
def push_signal_history(signal):
    rows = []
    for s in signal:
        rows.append({
            'signal_date' : s['signal_date'],
            'rank'        : s['rank'],
            'etf'         : s['etf'],
            'vel3m'       : s['vel3m'],
            'exec_price'  : s['exec_price'],
            'entered_top3': s['signal_date'],
            'action'      : s['action'],
        })
    sb_upsert('signal_history', rows)


# ─────────────────────────────────────────────────────────────────────────────
# BACKFILL
# ─────────────────────────────────────────────────────────────────────────────
def backfill(from_date_str):
    from_date = datetime.strptime(from_date_str, '%Y-%m-%d')
    today     = datetime.today()
    current   = from_date

    # Load settings and universe once
    settings  = load_settings()
    universe  = load_universe()
    n_slots   = settings.get('slots', 3)
    lookback  = settings.get('lookback', 13)

    print(f'\nBackfilling {from_date_str} → {today.strftime("%Y-%m-%d")}')
    print(f'Universe: {len(universe)} ETFs | Slots: {n_slots} | Lookback: {lookback}w\n')

    week = 0
    while current <= today:
        week += 1
        print(f'\n--- Week {week}: ~{current.strftime("%Y-%m-%d")} ---')
        prices = fetch_prices(universe, lookback, current, lookback_days=150)
        if prices:
            signal, _ = generate_signal(prices, n_slots)
            if signal:
                push_signal_history(signal)
                print(f'  Top {n_slots}: {[s["etf"] for s in signal]}')
        current += timedelta(weeks=1)

    print(f'\nBackfill complete. {week} weeks processed.')


# ─────────────────────────────────────────────────────────────────────────────
# MAIN — WEEKLY RUN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    now      = datetime.now()
    end_date = datetime.today()

    # Load settings and universe from Supabase
    settings    = load_settings()
    universe    = load_universe()
    n_slots     = settings.get('slots', 3)
    lookback    = settings.get('lookback', 13)

    print(f'Freedom 2040 — Signal Generator')
    print(f'Run time : {now.strftime("%Y-%m-%d %H:%M:%S")} UTC')
    print(f'Universe : {len(universe)} ETFs')
    print(f'Settings : slots={n_slots} lookback={lookback}w\n')

    prices         = fetch_prices(universe, lookback, end_date)
    signal, ranked = generate_signal(prices, n_slots)

    if signal:
        push_signal_history(signal)

    # Build output for signal.json
    sig_date = signal[0]['signal_date'] if signal else str(end_date.date())
    exec_date = signal[0]['exec_date'] if signal else str(end_date.date())

    output = {
        'generated_at'  : now.isoformat(),
        'generated_at_ist': (now + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d %H:%M IST'),
        'data_source'   : 'NSE EOD via yfinance (Monday closing prices, ~1hr delayed)',
        'signal_date'   : sig_date,
        'exec_date'     : exec_date,
        'universe_size' : len(universe),
        'top3'          : signal,
        'full_ranking'  : [
            {
                'rank'       : i + 1,
                'etf'        : n,
                'vel3m'      : d['vel3m'],
                'current_px' : d['current'],
                'exec_price' : d['exec_price'],
            }
            for i, (n, d) in enumerate(ranked)
        ],
        'n_positive': sum(1 for _, d in ranked if d['vel3m'] > 0),
        'n_total'   : len(ranked),
    }

    os.makedirs('docs', exist_ok=True)
    with open('docs/signal.json', 'w') as f:
        json.dump(output, f, indent=2)

    print(f'\n{"─"*60}')
    print(f'TOP {n_slots} SIGNAL  |  {sig_date}  |  Execute: {exec_date}')
    print(f'{"─"*60}')
    for s in signal:
        print(f"  #{s['rank']}  {s['etf']:<15} {s['vel3m']:+.2f}%  ₹{s['exec_price']}  → {s['action']}")
    print(f'{"─"*60}')
    print(f'Positive momentum: {output["n_positive"]}/{output["n_total"]}')
    print(f'Generated at: {output["generated_at_ist"]}')
    print(f'Data source: {output["data_source"]}')
    print(f'\nWritten docs/signal.json | Pushed to Supabase signal_history')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--backfill', metavar='YYYY-MM-DD',
                        help='Backfill from this date to today')
    args = parser.parse_args()
    if args.backfill:
        backfill(args.backfill)
    else:
        main()
