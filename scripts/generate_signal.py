import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import requests
import argparse
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────────────────────
# SUPABASE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
SB_URL = 'https://scnvnfrvxwrdwskcktnj.supabase.co'
SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNjbnZuZnJ2eHdyZHdza2NrdG5qIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM0MDE1MjYsImV4cCI6MjA5ODk3NzUyNn0.GmJ-C5mZORvPGgdp2JFDlZXamBQRwUOgAZjBmHm69C4'
SB_HEADERS = {
    'apikey': SB_KEY,
    'Authorization': f'Bearer {SB_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates,return=minimal',
}

# ─────────────────────────────────────────────────────────────────────────────
# ETF UNIVERSE — 135 ETFs with turnover >= 1 Cr
# Updated: 30 Jun 2026
# ─────────────────────────────────────────────────────────────────────────────
ETF_UNIVERSE = {
    'SILVERBEES': 'SILVERBEES.NS','GOLDBEES': 'GOLDBEES.NS','NIFTYBEES': 'NIFTYBEES.NS',
    'TATSILV': 'TATSILV.NS','HDFCSILVER': 'HDFCSILVER.NS','SILVERIETF': 'SILVERIETF.NS',
    'TATAGOLD': 'TATAGOLD.NS','GOLDIETF': 'GOLDIETF.NS','ITBEES': 'ITBEES.NS',
    'SETFGOLD': 'SETFGOLD.NS','BANKBEES': 'BANKBEES.NS','HDFCGOLD': 'HDFCGOLD.NS',
    'SBISILVER': 'SBISILVER.NS','PVTBANIETF': 'PVTBANIETF.NS','SILVER': 'SILVER.NS',
    'PSUBNKBEES': 'PSUBNKBEES.NS','JUNIORBEES': 'JUNIORBEES.NS','GOLD1': 'GOLD1.NS',
    'SILVERCASE': 'SILVERCASE.NS','HDFCSML250': 'HDFCSML250.NS','GOLDCASE': 'GOLDCASE.NS',
    'SILVERAXIS': 'SILVERAXIS.NS','MON100': 'MON100.NS','GOLDETF': 'GOLDETF.NS',
    'SILVER1': 'SILVER1.NS','MODEFENCE': 'MODEFENCE.NS','SETFNIF50': 'SETFNIF50.NS',
    'NIFTYIETF': 'NIFTYIETF.NS','MID150BEES': 'MID150BEES.NS','PHARMABEES': 'PHARMABEES.NS',
    'SILVERBETA': 'SILVERBETA.NS','SILVERAG': 'SILVERAG.NS','METALIETF': 'METALIETF.NS',
    'CPSEETF': 'CPSEETF.NS','SILVERADD': 'SILVERADD.NS','MOREALTY': 'MOREALTY.NS',
    'NEXT50IETF': 'NEXT50IETF.NS','HDFCNEXT50': 'HDFCNEXT50.NS','AUTOBEES': 'AUTOBEES.NS',
    'SMALLCAP': 'SMALLCAP.NS','HNGSNGBEES': 'HNGSNGBEES.NS','ALPHA': 'ALPHA.NS',
    'SETFNIFBK': 'SETFNIFBK.NS','PSUBANK': 'PSUBANK.NS','MONIFTY500': 'MONIFTY500.NS',
    'GOLDBETA': 'GOLDBETA.NS','GROWWSLVR': 'GROWWSLVR.NS','FMCGIETF': 'FMCGIETF.NS',
    'BANKIETF': 'BANKIETF.NS','BANKNIFTY1': 'BANKNIFTY1.NS','GOLDADD': 'GOLDADD.NS',
    'BANKBETA': 'BANKBETA.NS','PVTBANKADD': 'PVTBANKADD.NS','FINIETF': 'FINIETF.NS',
    'BSLGOLDETF': 'BSLGOLDETF.NS','MIDCAPETF': 'MIDCAPETF.NS','BSLNIFTY': 'BSLNIFTY.NS',
    'ESILVER': 'ESILVER.NS','NIFTYETF': 'NIFTYETF.NS','ICICIB22': 'ICICIB22.NS',
    'METAL': 'METAL.NS','MOSMALL250': 'MOSMALL250.NS','HDFCNIFBAN': 'HDFCNIFBAN.NS',
    'MOCAPITAL': 'MOCAPITAL.NS','MOMENTUM50': 'MOMENTUM50.NS','IT': 'IT.NS',
    'GROWWPOWER': 'GROWWPOWER.NS','MAFANG': 'MAFANG.NS','NIFTY1': 'NIFTY1.NS',
    'ITIETF': 'ITIETF.NS','GROWWGOLD': 'GROWWGOLD.NS','MOM100': 'MOM100.NS',
    'MOM30IETF': 'MOM30IETF.NS','NIFTYBETA': 'NIFTYBETA.NS','LOWVOLIETF': 'LOWVOLIETF.NS',
    'NEXT50BETA': 'NEXT50BETA.NS','MIDCAPIETF': 'MIDCAPIETF.NS','GROWWDEFNC': 'GROWWDEFNC.NS',
    'NEXT50': 'NEXT50.NS','BFSI': 'BFSI.NS','NIFTYADD': 'NIFTYADD.NS',
    'ABSLBANETF': 'ABSLBANETF.NS','HDFCNIFTY': 'HDFCNIFTY.NS','SETFNN50': 'SETFNN50.NS',
    'AUTOIETF': 'AUTOIETF.NS','EGOLD': 'EGOLD.NS','LOWVOL1': 'LOWVOL1.NS',
    'CHEMICAL': 'CHEMICAL.NS','ENERGY': 'ENERGY.NS','HDFCBSE500': 'HDFCBSE500.NS',
    'ITETF': 'ITETF.NS','BANKADD': 'BANKADD.NS','MID150CASE': 'MID150CASE.NS',
    'TOP10ADD': 'TOP10ADD.NS','DEFENCE': 'DEFENCE.NS','HEALTHIETF': 'HEALTHIETF.NS',
    'PSUBNKIETF': 'PSUBNKIETF.NS','MOM50': 'MOM50.NS','BANKETF': 'BANKETF.NS',
    'ABSL10BANK': 'ABSL10BANK.NS','OILIETF': 'OILIETF.NS','QGOLDHALF': 'QGOLDHALF.NS',
    'GROWWHOSPI': 'GROWWHOSPI.NS','GROWWRAIL': 'GROWWRAIL.NS','EQUAL50ADD': 'EQUAL50ADD.NS',
    'HDFCPVTBAN': 'HDFCPVTBAN.NS','LICMFGOLD': 'LICMFGOLD.NS','SML100CASE': 'SML100CASE.NS',
    'MONQ50': 'MONQ50.NS','ALPL30IETF': 'ALPL30IETF.NS','SENSEXIETF': 'SENSEXIETF.NS',
    'MIDSMALL': 'MIDSMALL.NS','SBIBPB': 'SBIBPB.NS','NIF100BEES': 'NIF100BEES.NS',
    'HDFCPSUBK': 'HDFCPSUBK.NS','GROWWEV': 'GROWWEV.NS','HDFCMID150': 'HDFCMID150.NS',
    'CONSUMBEES': 'CONSUMBEES.NS','MOGOLD': 'MOGOLD.NS','INFRAIETF': 'INFRAIETF.NS',
    'NIFTYBETF': 'NIFTYBETF.NS','MOSILVER': 'MOSILVER.NS','MASPTOP50': 'MASPTOP50.NS',
    'ALPHAETF': 'ALPHAETF.NS','MONEXT50': 'MONEXT50.NS','MOTOUR': 'MOTOUR.NS',
    'SILVERBND': 'SILVERBND.NS','MOLOWVOL': 'MOLOWVOL.NS','SMALL250': 'SMALL250.NS',
    'MAHKTECH': 'MAHKTECH.NS','BANK10ADD': 'BANK10ADD.NS','PSUBANKADD': 'PSUBANKADD.NS',
    'UNIONGOLD': 'UNIONGOLD.NS','MOVALUE': 'MOVALUE.NS','TOP100CASE': 'TOP100CASE.NS',
}

LOOKBACK_WEEKS = 13
N_SLOTS        = 3


def sb_upsert(table, rows):
    """Upsert rows into Supabase table. rows = list of dicts."""
    if not rows:
        return
    r = requests.post(
        f'{SB_URL}/rest/v1/{table}',
        headers=SB_HEADERS,
        json=rows
    )
    if r.status_code not in (200, 201):
        print(f'  SB error {table}: {r.status_code} {r.text[:200]}')
    return r


def fetch_prices(end_date, lookback_days=120):
    start_date = end_date - timedelta(days=lookback_days)
    prices = {}
    total  = len(ETF_UNIVERSE)
    for i, (name, ticker) in enumerate(ETF_UNIVERSE.items(), 1):
        try:
            df = yf.download(
                ticker,
                start=start_date.strftime('%Y-%m-%d'),
                end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                progress=False,
                auto_adjust=True
            )
            if df.empty or len(df) < 20:
                continue
            close  = df['Close'].squeeze()
            monday = close.resample('W-MON').last().dropna()
            if len(monday) < LOOKBACK_WEEKS + 1:
                continue
            current  = float(monday.iloc[-1])
            w13ago   = float(monday.iloc[-LOOKBACK_WEEKS - 1])
            vel3m    = ((current - w13ago) / w13ago) * 100
            last_mon = monday.index[-1]
            future   = close.index[close.index > last_mon]
            exec_px  = float(close.loc[future[0]]) if len(future) > 0 else current
            exec_dt  = str(future[0].date()) if len(future) > 0 else str(end_date.date())
            prices[name] = {
                'current'     : round(current, 2),
                'exec_price'  : round(exec_px, 2),
                'w13ago'      : round(w13ago, 2),
                'vel3m'       : round(vel3m, 4),
                'signal_date' : str(monday.index[-1].date()),
                'exec_date'   : exec_dt,
            }
            print(f'  [{i}/{total}] OK {name}: {vel3m:+.2f}%')
        except Exception as e:
            print(f'  [{i}/{total}] ERR {name}: {e}')
    return prices


def generate_signal(prices):
    ranked = sorted(
        [(n, d) for n, d in prices.items() if d.get('vel3m') is not None],
        key=lambda x: x[1]['vel3m'], reverse=True
    )
    top    = ranked[:N_SLOTS]
    signal = []
    for i, (name, d) in enumerate(top):
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


def push_signal_history(signal):
    """Push this week's top3 to Supabase signal_history table."""
    rows = []
    for s in signal:
        rows.append({
            'signal_date'   : s['signal_date'],
            'rank'          : s['rank'],
            'etf'           : s['etf'],
            'vel3m'         : s['vel3m'],
            'exec_price'    : s['exec_price'],
            'entered_top3'  : s['signal_date'],
        })
    sb_upsert('signal_history', rows)
    print(f'  Pushed {len(rows)} rows to Supabase signal_history')


def backfill(from_date_str):
    """Backfill signal_history from from_date to today, one week at a time."""
    from_date = datetime.strptime(from_date_str, '%Y-%m-%d')
    today     = datetime.today()
    current   = from_date

    print(f'\nBackfilling from {from_date_str} to {today.strftime("%Y-%m-%d")}')
    print('This will take a while — downloading data for each week...\n')

    week_num = 0
    while current <= today:
        week_num += 1
        print(f'\n--- Week {week_num}: signal date ~{current.strftime("%Y-%m-%d")} ---')
        prices = fetch_prices(current, lookback_days=150)
        if prices:
            signal, _ = generate_signal(prices)
            if signal:
                push_signal_history(signal)
                print(f'  Top 3: {[s["etf"] for s in signal]}')
        current += timedelta(weeks=1)

    print(f'\nBackfill complete. {week_num} weeks processed.')


def main(run_date=None):
    end_date = run_date or datetime.today()
    print(f'Freedom 2040 — Signal Generator')
    print(f'Universe : {len(ETF_UNIVERSE)} ETFs (turnover >= 1 Cr)')
    print(f'Run date : {end_date.strftime("%Y-%m-%d %H:%M")}\n')

    prices         = fetch_prices(end_date)
    signal, ranked = generate_signal(prices)

    if signal:
        push_signal_history(signal)

    output = {
        'generated_at': datetime.now().isoformat(),
        'signal_date' : signal[0]['signal_date'] if signal else str(end_date.date()),
        'exec_date'   : signal[0]['exec_date']   if signal else str(end_date.date()),
        'top3'        : signal,
        'full_ranking': [
            {'rank': i+1, 'etf': n, 'vel3m': d['vel3m'],
             'current_px': d['current'], 'exec_price': d['exec_price']}
            for i, (n, d) in enumerate(ranked)
        ],
        'n_positive'  : sum(1 for _, d in ranked if d['vel3m'] > 0),
        'n_total'     : len(ranked),
    }

    os.makedirs('docs', exist_ok=True)
    with open('docs/signal.json', 'w') as f:
        json.dump(output, f, indent=2)

    print(f'\nLoaded {len(prices)}/{len(ETF_UNIVERSE)} ETFs\n')
    print('TOP 3 SIGNAL:')
    print('-' * 65)
    for s in signal:
        print(f"  #{s['rank']}  {s['etf']:<15} {s['vel3m']:+.2f}%  exec ₹{s['exec_price']}")
    print('-' * 65)
    print(f"Signal: {output['signal_date']} | Execute: {output['exec_date']}")
    print(f"Positive momentum: {output['n_positive']}/{output['n_total']}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--backfill', metavar='YYYY-MM-DD',
                        help='Backfill signal history from this date to today')
    args = parser.parse_args()

    if args.backfill:
        backfill(args.backfill)
    else:
        main()
