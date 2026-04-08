#!/usr/bin/env python3
"""
カスタムバックテスト バックグラウンド実行スクリプト
PHP の exec(nohup ...) から起動される独立スクリプト。

パラメータ: /tmp/forex_bt_params.json を読み込む
結果:       /tmp/forex_bt_result.json に書き出す
"""

import sys
import os
import json
import traceback
from datetime import datetime, timezone

# プロジェクトルートをパスに追加
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

PARAMS_FILE = '/tmp/forex_bt_params.json'
RESULT_FILE = '/tmp/forex_bt_result.json'


def write_result(data: dict):
    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, default=str)


def main():
    # パラメータ読み込み
    if not os.path.exists(PARAMS_FILE):
        write_result({'status': 'error', 'error': 'パラメータファイルが見つかりません'})
        return

    try:
        with open(PARAMS_FILE, 'r', encoding='utf-8') as f:
            params = json.load(f)
    except Exception as e:
        write_result({'status': 'error', 'error': 'パラメータ読み込みエラー: ' + str(e)})
        return

    write_result({'status': 'running', 'message': '初期化中...', 'started_at': int(datetime.now(timezone.utc).timestamp())})

    try:
        from app import create_app
        from app.services.data_fetcher import get_candles
        from app.services.backtester import run_backtest_for_indicator
        from app.services.indicators.oscillators import calculate_oscillators
        from app.services.indicators.trend import calculate_trend
        from app.services.indicators.lines import calculate_lines
        from app.services.indicators.volatility import calculate_volatility
        from app.services.indicators.patterns import calculate_patterns
        import pandas as pd

        write_result({'status': 'running', 'message': 'データ取得中...', 'started_at': int(datetime.now(timezone.utc).timestamp())})

        app = create_app()
        with app.app_context():
            pair            = params.get('pair', 'USDJPY')
            timeframe       = params.get('timeframe', '1hr')
            start_date      = params.get('start_date', '')
            end_date        = params.get('end_date', '')
            capital         = float(params.get('initial_capital', 1_000_000))
            sl_pips         = float(params.get('sl_pips', 20))
            rr_ratio        = float(params.get('rr_ratio', 1.5))
            tp_pips         = round(sl_pips * rr_ratio, 1)
            indicator_names = params.get('indicators', [])

            if not indicator_names:
                write_result({'status': 'error', 'error': '指標が選択されていません'})
                return

            # 指標名 → 計算関数マップ
            INDICATOR_FUNC_MAP = {}
            for func in [calculate_oscillators, calculate_trend,
                         calculate_lines, calculate_volatility, calculate_patterns]:
                try:
                    dummy = pd.DataFrame({
                        c: [float(i) for i in range(1, 61)]
                        for c in ['open', 'high', 'low', 'close', 'volume']
                    })
                    for k in func(dummy).keys():
                        INDICATOR_FUNC_MAP[k] = func
                except Exception:
                    pass

            # データ取得
            df = get_candles(pair, timeframe, limit=5000)
            if df.empty:
                tf_labels = {'15min': '15分足', '1hr': '1時間足', '4hr': '4時間足', 'daily': '日足'}
                write_result({
                    'status': 'error',
                    'error': f'{pair} の {tf_labels.get(timeframe, timeframe)} データがDBにありません。'
                             'ダッシュボードで「データ取得を実行」してから再試行してください。'
                })
                return

            total_rows = len(df)

            # 日付フィルタ
            if start_date:
                try:
                    sd = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=None)
                    df = df[df['timestamp'] >= sd]
                except ValueError:
                    pass
            if end_date:
                try:
                    ed = datetime.strptime(end_date, '%Y-%m-%d').replace(
                        hour=23, minute=59, second=59, tzinfo=None)
                    df = df[df['timestamp'] <= ed]
                except ValueError:
                    pass
            df = df.reset_index(drop=True)

            if len(df) < 30:
                db_min = str(df['timestamp'].min())[:10] if not df.empty else 'なし'
                db_max = str(df['timestamp'].max())[:10] if not df.empty else 'なし'
                write_result({
                    'status': 'error',
                    'error': (
                        f'選択期間のデータが {len(df)} 本しかありません（30本以上必要）。\n'
                        f'DBには {total_rows} 本ありますが、期間フィルタ後に減りました。\n'
                        f'利用可能期間: {db_min} 〜 {db_max}'
                    )
                })
                return

            write_result({
                'status': 'running',
                'message': f'{len(indicator_names)} 個の指標でバックテスト実行中...',
                'started_at': int(datetime.now(timezone.utc).timestamp())
            })

            # バックテスト実行
            results = []
            for ind_name in indicator_names:
                func = INDICATOR_FUNC_MAP.get(ind_name)
                if func is None:
                    continue
                try:
                    res = run_backtest_for_indicator(
                        df=df,
                        indicator_name=ind_name,
                        indicator_func=func,
                        pair=pair,
                        timeframe=timeframe,
                        initial_capital=capital,
                        sl_pips=sl_pips,
                        tp_pips=tp_pips,
                        backtest_hours=99999,
                    )
                except Exception:
                    continue

                if not res:
                    continue

                res['indicator_name'] = ind_name
                res['tp_pips']  = tp_pips
                res['rr_ratio'] = rr_ratio

                # トレード履歴を JSON シリアライズ可能な形に変換
                trades_out = []
                for t in res.get('trades', []):
                    ets = t.get('entry_ts')
                    xts = t.get('exit_ts')
                    trades_out.append({
                        'entry_ts':     ets.strftime('%Y/%m/%d %H:%M') if hasattr(ets, 'strftime') else str(ets),
                        'exit_ts':      xts.strftime('%Y/%m/%d %H:%M') if hasattr(xts, 'strftime') else str(xts),
                        'signal':       t.get('signal'),
                        'entry_price':  round(float(t.get('entry_price', 0)), 3),
                        'exit_price':   round(float(t.get('exit_price', 0)), 3),
                        'outcome':      t.get('outcome'),
                        'capital_after': round(float(t.get('capital_after', 0))),
                    })
                res['trades'] = trades_out

                # datetime オブジェクトを文字列に変換
                for k in ['calculated_at']:
                    if k in res and hasattr(res[k], 'strftime'):
                        res[k] = res[k].strftime('%Y/%m/%d %H:%M')

                results.append(res)

            write_result({
                'status': 'done',
                'message': f'{len(results)} 件の指標でバックテスト完了',
                'results': results,
            })

    except Exception as e:
        write_result({
            'status': 'error',
            'error': str(e) + '\n' + traceback.format_exc(),
        })


if __name__ == '__main__':
    main()
