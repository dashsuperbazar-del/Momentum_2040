import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta

ETF_UNIVERSE = {
    'MIDSMALL'  : 'MIDSMALL.NS',
    'EVINDIA'   : 'EVINDIA.NS',
    'MOM100'    : 'MOM100.NS',
    'NIFTYBEES' : 'NIFTYBEES.NS',
    'CONSUMBEES': 'CONSUMBEES.NS',
    'MID150BEES': 'MID150BEES.NS',
    'HDFCSML250': 'HDFCSML250.NS',
    'MOM30IETF' : 'MOM30IETF.NS',
    'MAFANG'    : 'MAFANG.NS',
    'ALPHA'     : 'ALPHA.NS',
    'BANKBEES'  : 'BANKBEES.NS',
    'PSUBNKBEES': 'PSUBNKBEES.NS',
    'ITBEES'    : 'ITBEES.NS',
    'PHARMABEES': 'PHARMABEES.NS',
    'AUTOBEES'  : 'AUTOBEES.NS',
    'INFRAIETF' : 'INFRAIETF.NS',
    'MOREALTY'  : 'MOREALTY.NS',
    'MODEFENCE' : 'MODEFENCE.NS',
    'CPSEETF'   : 'CPSEETF.NS',
    'MON100'    : 'MON100.NS',
    'GOLDBEES'  : 'GOLDBEES.NS',
    'SILVERBEES': 'SILVERBEES.NS',
    'NEXT50IETF': 'NEXT50IETF.NS',
    'MOMENTUM50': 'MOMENTUM50.NS',
    'METALIETF' : 'METALIETF.NS',
    'MONQ50'    : 'MONQ50.NS',
    'GROWWPOWER': 'GROWWPOWER.NS',
    'MOENERGY'  : 'MOENERGY.NS',
    'EQUAL50ADD': 'EQUAL50ADD.NS',
    'TNIDETF'   : 'TNIDETF.NS',
    'OILIETF'   : 'OILIETF.NS',
}

LOOKBACK_WEEKS = 13
N_SLOTS        = 3
END_DATE       = datetime.today()
START_DATE     = END_DATE - timedelta(days=120)


def fetch_prices():
    prices = {}
    for name, ticker in ETF_UNIVERSE.items():
        try:
            df = yf.download(
                ticker,
                start=START_DATE.strftime('%Y-%m-%d'),
                end=(END_DATE + timedelta(days=1)).strftime('%Y-%m-%d'),
                progress=False,
                auto_adjust=True
            )
            if df.empty or len(df) < 20:
                print(f'  SKIP {name}: insufficient data')
                continue

            close  = df['Close'].squeeze()
            monday = close.resample('W-MON').last().dropna()

            if len(monday) < LOOKBACK_WEEKS + 1:
                print(f'  SKIP {name}: not enough weekly data ({len(monday)} weeks)')
                continue

            current = float(monday.iloc[-1])
            w13ago  = float(monday.iloc[-LOOKBACK_WEEKS - 1])
            vel3m   = ((current - w13ago) / w13ago) * 100

            # Execution price = next actual trading day after last Monday
            last_mon = monday.index[-1]
            future   = close.index[close.index > last_mon]
            exec_px  = float(close.loc[future[0]]) if len(future) > 0 else current
            exec_dt  = str(future[0].date()) if len(future) > 0 else str(END_DATE.date())

            prices[name] = {
                'current'     : round(current, 2),
                'exec_price'  : round(exec_px, 2),
                'w13ago'      : round(w13ago, 2),
                'vel3m'       : round(vel3m, 4),
                'signal_date' : str(monday.index[-1].date()),
                'exec_date'   : exec_dt,
            }
            print(f'  OK   {name}: vel3m={vel3m:.2f}%  price=Rs{current:.2f}  exec=Rs{exec_px:.2f}')

        except Exception as e:
            print(f'  ERR  {name}: {e}')

    return prices


def generate_signal(prices):
    ranked = sorted(
        [(name, d) for name, d in prices.items() if d.get('vel3m') is not None],
        key=lambda x: x[1]['vel3m'],
        reverse=True
    )

    top = ranked[:N_SLOTS]
    signal = []
    for i, (name, d) in enumerate(top):
        vel    = d['vel3m']
        action = 'LIQUIDBEES' if vel < 0 else 'BUY_OR_HOLD'
        signal.append({
            'rank'       : i + 1,
            'etf'        : name,
            'vel3m'      : d['vel3m'],
            'current_px' : d['current'],
            'exec_price' : d['exec_price'],
            'signal_date': d['signal_date'],
            'exec_date'  : d['exec_date'],
            'action'     : action,
        })

    return signal, ranked


def main():
    print(f'Freedom 2040 — Signal Generator')
    print(f'Run date : {END_DATE.strftime("%Y-%m-%d %H:%M")} UTC')
    print(f'Lookback : {LOOKBACK_WEEKS} weeks\n')
    print('Fetching prices...')

    prices         = fetch_prices()
    signal, ranked = generate_signal(prices)

    output = {
        'generated_at' : datetime.now().isoformat(),
        'signal_date'  : signal[0]['signal_date'] if signal else str(END_DATE.date()),
        'exec_date'    : signal[0]['exec_date']   if signal else str(END_DATE.date()),
        'top3'         : signal,
        'full_ranking' : [
            {
                'rank'      : i + 1,
                'etf'       : n,
                'vel3m'     : d['vel3m'],
                'current_px': d['current'],
                'exec_price': d['exec_price'],
            }
            for i, (n, d) in enumerate(ranked)
        ],
        'n_positive'   : sum(1 for _, d in ranked if d['vel3m'] > 0),
        'n_total'      : len(ranked),
    }

    os.makedirs('docs', exist_ok=True)
    with open('docs/signal.json', 'w') as f:
        json.dump(output, f, indent=2)

    print(f'\nLoaded {len(prices)}/{len(ETF_UNIVERSE)} ETFs\n')
    print('TOP 3 SIGNAL:')
    print('-' * 50)
    for s in signal:
        print(f"  #{s['rank']}  {s['etf']:<15}  {s['vel3m']:+.2f}%  Rs{s['exec_price']}  → {s['action']}")
    print('-' * 50)
    print(f"\nSignal date : {output['signal_date']}")
    print(f"Execute on  : {output['exec_date']}")
    print(f"Positive    : {output['n_positive']} / {output['n_total']} ETFs")
    print('\nWritten to docs/signal.json')


if __name__ == '__main__':
    main()
