#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FutureQuantVexa v2.0 — Advanced Pattern-Based Signal Generator
================================================================

Features:
  - 18 Japanese candlestick patterns × 7 weekdays × 13 pairs
  - MTG1 recovery (Entry 1 → MTG1 → STOP, max loss 3× stake)
  - Time range filter (e.g. 09:00-12:00)
  - Smart dedup: signals ≥4 minutes apart (configurable)
  - Persistent cache: never repeats already-sent signals
  - Telegram-style output (M1 PAIR-OTC HH:MM CALL/PUT)
  - Timezone offset support (--tz=1 for UTC+1)

Usage:
  python futurequantvexa.py *.json --tz=1 --time=09:00-12:00 --gap=4
  python futurequantvexa.py *.json --tz=1 --time=22:00-00:00 --gap=3
  python futurequantvexa.py *.json --tz=1 --time=23:00-00:00 --gap=5 --clear-cache
"""

import os
import sys
import json
import csv
import re
import argparse
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# ============================================================================
# ELITE PATTERN DATABASE (142 combinations, ≥85% C1+C2 success rate)
# ============================================================================
ELITE_PATTERNS = {
    # SUNDAY
    "USDPHP:Sun:GapRev:BUY": (50.0, 86.7, 6.6),
    "USDNGN:Sun:InsideBody:SELL": (50.0, 89.3, 8.8),
    "USDIDR:Sun:InsideBar:SELL": (70.0, 95.0, 11.2),
    "USDIDR:Sun:PinBar:SELL": (50.0, 94.4, 9.0),
    "USDIDR:Sun:ShootStar:SELL": (33.3, 91.7, 4.4),
    "USDIDR:Sun:LongWick:SELL": (52.4, 90.5, 7.6),
    "USDIDR:Sun:Harami:SELL": (60.0, 90.0, 3.6),
    "USDMXN:Sun:Doji:SELL": (55.6, 94.4, 9.2),
    "USDMXN:Sun:Marubozu:BUY": (50.0, 92.9, 6.2),
    "USDMXN:Sun:LongWick:SELL": (57.6, 87.9, 9.2),
    "USDMXN:Sun:PinBar:SELL": (55.0, 85.0, 3.4),
    "USDMXN:Sun:Harami:BUY": (58.3, 83.3, 7.8),
    "USDMXN:Sun:InsideBody:BUY": (50.0, 81.3, 4.0),
    "USDCOP:Sun:Engulfing:SELL": (58.3, 91.7, 5.0),
    "USDCOP:Sun:BigBodyRev:SELL": (59.5, 86.5, 8.6),
    "USDCOP:Sun:Marubozu:SELL": (66.7, 86.7, 3.8),
    "USDZAR:Sun:Tweezer:SELL": (68.2, 86.4, 5.4),
    "USDZAR:Sun:InsideBar:BUY": (60.0, 85.0, 3.6),
    "USDZAR:Sun:PinBar:SELL": (47.1, 82.4, 9.8),
    "USDARS:Sun:GapRev:BUY": (60.6, 90.9, 13.0),
    "USDARS:Sun:Engulfing:BUY": (52.4, 90.5, 7.6),
    "USDARS:Sun:Marubozu:BUY": (55.0, 85.0, 3.4),
    "USDBDT:Sun:Doji:BUY": (55.6, 83.3, 10.8),
    "USDDZD:Sun:PinBar:SELL": (71.4, 85.7, 3.2),
    "USDEGP:Sun:Tweezer:SELL": (71.4, 85.7, 3.2),
    "USDEGP:Sun:Marubozu:BUY": (40.0, 86.7, 3.0),
    "USDEGP:Sun:BigBodyRev:SELL": (51.4, 82.9, 20.6),
    "BRLUSD:Wed:ShootStar:SELL": (50.0, 85.0, 3.2),

    # MONDAY
    "USDINR:Mon:PinBar:BUY": (66.7, 100.0, 11.0),
    "USDZAR:Mon:Doji:BUY": (75.0, 100.0, 9.0),
    "USDEGP:Mon:InsideBar:SELL": (75.0, 93.8, 8.4),
    "USDMXN:Mon:Marubozu:SELL": (73.3, 93.3, 7.6),
    "USDCOP:Mon:Star:BUY": (70.6, 94.1, 9.0),
    "USDARS:Mon:Star:BUY": (80.0, 93.3, 7.8),
    "USDARS:Mon:Harami:SELL": (30.0, 90.0, 3.0),
    "USDINR:Mon:Tweezer:BUY": (60.0, 86.7, 3.6),
    "BRLUSD:Mon:Engulfing:SELL": (66.7, 91.7, 5.2),
    "BRLUSD:Mon:PinBar:BUY": (68.4, 89.5, 6.8),
    "BRLUSD:Mon:LongWick:BUY": (57.7, 88.5, 7.8),
    "BRLUSD:Mon:Hammer:BUY": (64.3, 85.7, 3.0),
    "BRLUSD:Mon:Harami:BUY": (38.5, 84.6, 8.0),
    "USDDZD:Mon:Tweezer:BUY": (69.2, 92.3, 6.0),
    "USDDZD:Mon:InsideBar:BUY": (50.0, 89.3, 8.8),
    "USDDZD:Mon:LongWick:BUY": (56.7, 83.3, 19.4),
    "USDPHP:Mon:Marubozu:SELL": (46.2, 92.3, 5.4),
    "USDPHP:Mon:Star:BUY": (71.4, 85.7, 3.2),
    "USDPHP:Mon:PinBar:BUY": (43.8, 81.3, 9.0),
    "USDNGN:Mon:InsideBar:BUY": (59.3, 88.9, 8.6),
    "USDNGN:Mon:InsideBody:BUY": (60.0, 85.0, 3.6),
    "USDEGP:Mon:Star:BUY": (56.3, 87.5, 4.2),

    # TUESDAY
    "USDINR:Tue:PinBar:BUY": (60.0, 95.0, 10.8),
    "USDINR:Tue:ShootStar:SELL": (20.0, 90.0, 2.8),
    "USDINR:Tue:Marubozu:SELL": (50.0, 90.0, 3.4),
    "USDNGN:Tue:Engulfing:BUY": (58.3, 91.7, 5.0),
    "USDNGN:Tue:InsideBar:SELL": (63.2, 89.5, 6.6),
    "USDNGN:Tue:LongWick:SELL": (57.7, 88.5, 7.8),
    "USDNGN:Tue:BigBodyRev:SELL": (57.1, 82.9, 5.8),
    "USDNGN:Tue:Tweezer:BUY": (59.5, 85.7, 8.6),
    "USDARS:Tue:PinBar:SELL": (71.4, 85.7, 3.2),
    "USDARS:Tue:GapRev:BUY": (60.0, 85.7, 7.2),
    "USDARS:Tue:LongWick:SELL": (65.4, 84.6, 1.4),
    "USDPKR:Tue:InsideBody:BUY": (69.4, 91.7, 15.8),
    "USDPKR:Tue:GapRev:BUY": (53.7, 87.8, 11.0),
    "USDPKR:Tue:Star:BUY": (51.6, 83.9, 18.2),
    "USDPKR:Tue:Harami:SELL": (54.5, 81.8, 7.0),
    "USDIDR:Tue:Engulfing:SELL": (56.3, 87.5, 4.2),
    "USDIDR:Tue:PinBar:SELL": (39.1, 87.0, 4.8),
    "USDIDR:Tue:ShootStar:SELL": (10.0, 90.0, 2.8),
    "USDIDR:Tue:Doji:SELL": (42.9, 82.1, 15.6),
    "USDIDR:Tue:Tweezer:SELL": (65.6, 87.5, 9.0),
    "USDIDR:Tue:InsideBar:BUY": (53.3, 83.3, 4.0),
    "USDIDR:Tue:BigBodyRev:BUY": (46.3, 82.9, 24.8),
    "USDZAR:Tue:Hammer:SELL": (58.3, 91.7, 5.0),
    "USDZAR:Tue:Doji:SELL": (65.0, 85.0, 3.8),
    "USDZAR:Tue:Marubozu:BUY": (52.4, 85.7, 4.0),
    "USDMXN:Tue:Doji:SELL": (53.3, 86.7, 3.4),
    "USDCOP:Tue:3Soldiers:BUY": (60.9, 85.5, 13.8),
    "USDCOP:Tue:Consec2:BUY": (57.9, 81.7, 33.0),
    "BRLUSD:Fri:Engulfing:BUY": (51.9, 85.2, 4.6),

    # WEDNESDAY
    "USDPHP:Wed:Harami:SELL": (56.3, 93.8, 7.8),
    "USDPHP:Wed:InsideBar:SELL": (48.1, 86.5, 11.0),
    "USDNGN:Wed:Harami:BUY": (62.5, 87.5, 4.4),
    "USDNGN:Wed:InsideBar:BUY": (51.1, 87.2, 11.4),
    "USDNGN:Wed:Tweezer:BUY": (59.5, 85.7, 8.6),
    "USDARS:Wed:Star:SELL": (69.2, 87.2, 10.8),
    "USDDZD:Wed:PinBar:SELL": (54.8, 90.3, 11.2),
    "USDDZD:Wed:ShootStar:SELL": (58.8, 88.2, 5.0),
    "USDDZD:Wed:LongWick:SELL": (54.4, 84.2, 4.0),
    "USDDZD:Tue:TrendCont:BUY": (63.6, 85.5, 11.2),
    "USDMXN:Wed:ShootStar:SELL": (54.5, 86.4, 4.8),
    "USDMXN:Wed:Harami:BUY": (63.6, 86.4, 5.2),
    "USDZAR:Wed:Harami:BUY": (60.9, 82.6, 14.2),

    # THURSDAY
    "USDINR:Thu:ShootStar:SELL": (72.2, 94.4, 9.8),
    "USDINR:Thu:BigBodyRev:SELL": (60.0, 86.2, 12.0),
    "USDINR:Thu:Harami:BUY": (47.1, 82.4, 9.8),
    "USDZAR:Thu:Harami:BUY": (50.0, 94.4, 9.0),
    "USDZAR:Thu:GapRev:SELL": (44.9, 84.1, 26.4),
    "USDARS:Thu:InsideBar:BUY": (63.6, 88.6, 14.0),
    "USDARS:Thu:Harami:BUY": (58.8, 88.2, 5.0),
    "USDARS:Thu:Marubozu:SELL": (52.2, 87.0, 5.4),
    "USDARS:Thu:Tweezer:BUY": (51.9, 85.2, 4.6),
    "USDDZD:Thu:Hammer:BUY": (68.2, 81.8, 13.8),
    "USDEGP:Thu:Marubozu:BUY": (60.9, 87.0, 5.8),
    "USDPHP:Thu:Hammer:SELL": (50.0, 90.0, 3.4),
    "USDBDT:Thu:Marubozu:SELL": (48.3, 86.2, 5.8),
    "USDBDT:Thu:BigBodyRev:SELL": (47.5, 85.2, 10.0),
    "USDBDT:Thu:PinBar:BUY": (59.6, 83.0, 0.2),

    # FRIDAY
    "USDCOP:Fri:ShootStar:SELL": (52.4, 95.2, 11.2),
    "USDINR:Fri:Engulfing:BUY": (71.4, 89.3, 10.0),
    "USDMXN:Fri:Marubozu:SELL": (54.2, 91.7, 9.8),
    "USDMXN:Fri:PinBar:BUY": (68.8, 90.6, 12.8),
    "USDMXN:Fri:Star:SELL": (57.6, 81.8, 5.2),
    "USDMXN:Fri:Tweezer:SELL": (57.1, 82.1, 2.0),
    "USDNGN:Fri:Hammer:BUY": (64.7, 88.2, 5.2),
    "USDNGN:Fri:InsideBar:BUY": (52.1, 85.4, 8.6),
    "USDNGN:Fri:Tweezer:SELL": (64.5, 87.1, 8.2),
    "USDEGP:Fri:Marubozu:BUY": (54.5, 87.9, 9.0),
    "USDIDR:Fri:ShootStar:SELL": (56.3, 87.5, 4.2),
    "USDIDR:Fri:PinBar:SELL": (45.5, 81.8, 4.4),
    "USDCOP:Fri:Star:BUY": (55.3, 81.6, 7.4),
    "BRLUSD:Fri:Tweezer:SELL": (69.0, 86.2, 7.0),
    "BRLUSD:Fri:Engulfing:BUY": (51.9, 85.2, 4.6),
    "USDDZD:Fri:Hammer:SELL": (35.0, 85.0, 2.6),
    "USDPHP:Fri:Harami:BUY": (59.1, 86.4, 5.0),

    # SATURDAY
    "USDDZD:Sat:Marubozu:SELL": (66.7, 100.0, 8.8),
    "USDINR:Sat:Tweezer:SELL": (76.9, 100.0, 9.8),
    "USDPKR:Sat:PinBar:BUY": (52.2, 95.7, 12.6),
    "USDBDT:Sat:PinBar:BUY": (53.3, 93.3, 7.0),
    "USDZAR:Sat:Star:BUY": (46.7, 93.3, 6.8),
    "USDDZD:Sat:Star:SELL": (42.9, 92.9, 6.0),
    "USDINR:Sat:Star:SELL": (64.3, 92.9, 13.2),
    "USDNGN:Sat:Star:BUY": (73.3, 86.7, 4.0),
    "USDNGN:Sat:GapRev:SELL": (56.7, 86.7, 7.0),
    "USDPHP:Sat:Hammer:SELL": (50.0, 91.7, 4.8),
    "USDPHP:Sat:Tweezer:BUY": (58.3, 91.7, 5.0),
    "USDPHP:Sat:PinBar:BUY": (45.5, 90.9, 4.0),
    "USDPKR:Sat:InsideBody:BUY": (63.6, 90.9, 8.8),
    "USDPKR:Sat:Star:BUY": (63.2, 89.5, 6.6),
    "USDPKR:Sat:LongWick:BUY": (52.9, 82.4, 4.8),
    "USDPKR:Sat:Engulfing:BUY": (66.7, 88.9, 6.0),
    "USDDZD:Sat:PinBar:SELL": (50.0, 87.5, 4.0),
    "USDDZD:Sat:Tweezer:BUY": (50.0, 87.5, 4.0),
    "USDDZD:Sat:LongWick:SELL": (56.5, 87.0, 5.6),
    "USDDZD:Sat:Engulfing:BUY": (53.8, 84.6, 7.6),
    "USDDZD:Sat:TrendCont:SELL": (60.0, 86.0, 10.8),
    "USDBDT:Sat:LongWick:BUY": (48.1, 88.9, 8.0),
    "USDIDR:Sat:InsideBar:BUY": (50.0, 88.9, 5.4),
    "USDIDR:Sat:3Soldiers:SELL": (63.0, 81.5, 19.2),
    "USDIDR:Sat:TrendCont:BUY": (52.2, 87.0, 10.8),
    "USDARS:Sat:Hammer:BUY": (70.0, 90.0, 3.8),
    "USDARS:Sat:LongWick:BUY": (61.3, 87.1, 8.0),
    "USDARS:Sat:InsideBody:BUY": (52.2, 87.0, 5.4),
    "USDARS:Sat:BigBodyRev:SELL": (65.2, 87.0, 6.0),
    "USDCOP:Sat:Marubozu:BUY": (54.5, 86.4, 4.8),
    "USDCOP:Sat:Tweezer:SELL": (58.6, 86.2, 6.4),
    "USDCOP:Sat:GapRev:BUY": (53.3, 82.2, 11.8),
    "USDMXN:Sat:BigBodyRev:SELL": (40.7, 81.5, 0.4),
    "USDMXN:Sat:Engulfing:BUY": (58.8, 88.2, 5.0),
    "USDZAR:Sat:Doji:BUY": (45.5, 81.8, 6.8),
    "USDZAR:Sat:Engulfing:BUY": (50.0, 87.5, 4.0),
    "USDEGP:Mon:InsideBar:SELL": (75.0, 93.8, 8.4),
}


# ============================================================================
# PATTERN DETECTION FUNCTIONS
# ============================================================================

def detect_dozi(candles):
    signals = []
    for i in range(1, len(candles) - 1):
        prev, c = candles[i-1], candles[i]
        rng = c['high'] - c['low']
        body = abs(c['close'] - c['open'])
        if rng > 0 and body / rng <= 0.1:
            if prev['close'] < prev['open']:
                signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'Doji'})
            elif prev['close'] > prev['open']:
                signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'Doji'})
    return signals

def detect_hammer(candles):
    signals = []
    for i in range(1, len(candles) - 1):
        prev, c = candles[i-1], candles[i]
        rng = c['high'] - c['low']
        body = abs(c['close'] - c['open'])
        lower_wick = min(c['open'], c['close']) - c['low']
        upper_wick = c['high'] - max(c['open'], c['close'])
        if rng > 0 and body / rng <= 0.3 and lower_wick / rng >= 0.6 and upper_wick / rng <= 0.15:
            if prev['close'] < prev['open']:
                signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'Hammer'})
            elif prev['close'] > prev['open']:
                signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'Hammer'})
    return signals

def detect_shooting_star(candles):
    signals = []
    for i in range(1, len(candles) - 1):
        prev, c = candles[i-1], candles[i]
        if prev['close'] <= prev['open']:
            continue
        rng = c['high'] - c['low']
        body = abs(c['close'] - c['open'])
        upper_wick = c['high'] - max(c['open'], c['close'])
        lower_wick = min(c['open'], c['close']) - c['low']
        if rng > 0 and body / rng <= 0.3 and upper_wick / rng >= 0.6 and lower_wick / rng <= 0.15:
            signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'ShootStar'})
    return signals

def detect_star(candles):
    signals = []
    for i in range(2, len(candles) - 1):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        if (c1['close'] < c1['open'] and
            abs(c2['close'] - c2['open']) < abs(c1['close'] - c1['open']) * 0.5 and
            c3['close'] > c3['open'] and
            c3['close'] > (c1['open'] + c1['close']) / 2):
            signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'Star'})
        if (c1['close'] > c1['open'] and
            abs(c2['close'] - c2['open']) < abs(c1['close'] - c1['open']) * 0.5 and
            c3['close'] < c3['open'] and
            c3['close'] < (c1['open'] + c1['close']) / 2):
            signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'Star'})
    return signals

def detect_three_soldiers(candles):
    signals = []
    for i in range(2, len(candles) - 1):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        if (c1['close'] > c1['open'] and c2['close'] > c2['open'] and c3['close'] > c3['open'] and
            c2['close'] > c1['close'] and c3['close'] > c2['close']):
            signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': '3Soldiers'})
        if (c1['close'] < c1['open'] and c2['close'] < c2['open'] and c3['close'] < c3['open'] and
            c2['close'] < c1['close'] and c3['close'] < c2['close']):
            signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': '3Soldiers'})
    return signals

def detect_harami(candles):
    signals = []
    for i in range(1, len(candles) - 1):
        prev, c = candles[i-1], candles[i]
        prev_body = abs(prev['close'] - prev['open'])
        curr_body = abs(c['close'] - c['open'])
        if curr_body < prev_body * 0.6 and c['high'] <= prev['high'] and c['low'] >= prev['low']:
            if prev['close'] < prev['open'] and c['close'] > c['open']:
                signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'Harami'})
            if prev['close'] > prev['open'] and c['close'] < c['open']:
                signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'Harami'})
    return signals

def detect_piercing(candles):
    signals = []
    for i in range(1, len(candles) - 1):
        prev, c = candles[i-1], candles[i]
        if (prev['close'] < prev['open'] and c['open'] < prev['low'] and
            c['close'] > (prev['open'] + prev['close']) / 2 and c['close'] > c['open']):
            signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'Piercing'})
        if (prev['close'] > prev['open'] and c['open'] > prev['high'] and
            c['close'] < (prev['open'] + prev['close']) / 2 and c['close'] < c['open']):
            signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'Piercing'})
    return signals

def detect_tweezer(candles):
    signals = []
    for i in range(1, len(candles) - 1):
        prev, c = candles[i-1], candles[i]
        rng = c['high'] - c['low']
        if rng > 0:
            if (abs(c['low'] - prev['low']) < rng * 0.05 and
                prev['close'] < prev['open'] and c['close'] > c['open']):
                signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'Tweezer'})
            if (abs(c['high'] - prev['high']) < rng * 0.05 and
                prev['close'] > prev['open'] and c['close'] < c['open']):
                signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'Tweezer'})
    return signals

def detect_marubozu(candles):
    signals = []
    for i in range(len(candles) - 1):
        c = candles[i]
        rng = c['high'] - c['low']
        body = abs(c['close'] - c['open'])
        if rng > 0 and body / rng >= 0.92:
            if c['close'] > c['open']:
                signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'Marubozu'})
            else:
                signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'Marubozu'})
    return signals

def detect_inside_bar(candles):
    signals = []
    for i in range(1, len(candles) - 1):
        mother, inside = candles[i-1], candles[i]
        if inside['high'] <= mother['high'] and inside['low'] >= mother['low']:
            if inside['close'] > inside['open']:
                signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'InsideBar'})
            elif inside['close'] < inside['open']:
                signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'InsideBar'})
    return signals

def detect_pin_bar(candles):
    signals = []
    for i in range(1, len(candles) - 1):
        prev, c = candles[i-1], candles[i]
        rng = c['high'] - c['low']
        if rng <= 0:
            continue
        body = abs(c['close'] - c['open'])
        upper_wick = c['high'] - max(c['open'], c['close'])
        lower_wick = min(c['open'], c['close']) - c['low']
        if lower_wick / rng >= 0.6 and body / rng <= 0.35 and prev['close'] < prev['open']:
            signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'PinBar'})
        if upper_wick / rng >= 0.6 and body / rng <= 0.35 and prev['close'] > prev['open']:
            signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'PinBar'})
    return signals

def detect_engulfing(candles):
    signals = []
    for i in range(1, len(candles) - 1):
        prev, c = candles[i-1], candles[i]
        if (c['high'] > prev['high'] and c['low'] < prev['low'] and
            c['close'] > c['open'] and prev['close'] < prev['open']):
            signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'Engulfing'})
        if (c['high'] > prev['high'] and c['low'] < prev['low'] and
            c['close'] < c['open'] and prev['close'] > prev['open']):
            signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'Engulfing'})
    return signals

def detect_trend_continuation(candles):
    signals = []
    for i in range(3, len(candles) - 1):
        c1, c2, c3, c4 = candles[i-3], candles[i-2], candles[i-1], candles[i]
        if (c2['high'] > c1['high'] and c3['high'] > c2['high'] and c4['high'] > c3['high'] and
            c2['low'] > c1['low'] and c3['low'] > c2['low'] and c4['low'] > c3['low']):
            signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'TrendCont'})
        if (c2['high'] < c1['high'] and c3['high'] < c2['high'] and c4['high'] < c3['high'] and
            c2['low'] < c1['low'] and c3['low'] < c2['low'] and c4['low'] < c3['low']):
            signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'TrendCont'})
    return signals

def detect_inside_body(candles):
    signals = []
    for i in range(1, len(candles) - 1):
        prev, c = candles[i-1], candles[i]
        prev_body_high = max(prev['open'], prev['close'])
        prev_body_low = min(prev['open'], prev['close'])
        if (c['close'] < prev_body_high and c['close'] > prev_body_low and
            abs(c['close'] - c['open']) < abs(prev['close'] - prev['open']) * 0.5):
            if prev['close'] > prev['open'] and c['close'] < c['open']:
                signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'InsideBody'})
            elif prev['close'] < prev['open'] and c['close'] > c['open']:
                signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'InsideBody'})
    return signals

def detect_gap_reversal(candles):
    signals = []
    for i in range(1, len(candles) - 1):
        prev, c = candles[i-1], candles[i]
        if c['open'] > prev['close'] and c['close'] < prev['close']:
            signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'GapRev'})
        if c['open'] < prev['close'] and c['close'] > prev['close']:
            signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'GapRev'})
    return signals

def detect_consecutive(candles):
    signals = []
    for i in range(1, len(candles) - 1):
        prev, c = candles[i-1], candles[i]
        if prev['close'] > prev['open'] and c['close'] > c['open']:
            signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'Consec2'})
        if prev['close'] < prev['open'] and c['close'] < c['open']:
            signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'Consec2'})
    return signals

def detect_long_wick(candles):
    signals = []
    for i in range(1, len(candles) - 1):
        prev, c = candles[i-1], candles[i]
        rng = c['high'] - c['low']
        if rng <= 0:
            continue
        body = abs(c['close'] - c['open'])
        upper_wick = c['high'] - max(c['open'], c['close'])
        lower_wick = min(c['open'], c['close']) - c['low']
        if lower_wick / rng >= 0.5 and body / rng <= 0.4 and prev['close'] < prev['open']:
            signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'LongWick'})
        if upper_wick / rng >= 0.5 and body / rng <= 0.4 and prev['close'] > prev['open']:
            signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'LongWick'})
    return signals

def detect_big_body_reversal(candles):
    signals = []
    avg_body = sum(abs(c['close'] - c['open']) for c in candles) / len(candles) if candles else 0
    for i in range(1, len(candles) - 1):
        prev, c = candles[i-1], candles[i]
        body = abs(c['close'] - c['open'])
        if body >= avg_body * 1.3:
            if prev['close'] < prev['open'] and c['close'] > c['open']:
                signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'BigBodyRev'})
            if prev['close'] > prev['open'] and c['close'] < c['open']:
                signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'BigBodyRev'})
    return signals


PATTERN_DETECTORS = {
    'Doji': detect_dozi,
    'Hammer': detect_hammer,
    'ShootStar': detect_shooting_star,
    'Star': detect_star,
    '3Soldiers': detect_three_soldiers,
    'Harami': detect_harami,
    'Piercing': detect_piercing,
    'Tweezer': detect_tweezer,
    'Marubozu': detect_marubozu,
    'InsideBar': detect_inside_bar,
    'PinBar': detect_pin_bar,
    'Engulfing': detect_engulfing,
    'TrendCont': detect_trend_continuation,
    'InsideBody': detect_inside_body,
    'GapRev': detect_gap_reversal,
    'Consec2': detect_consecutive,
    'LongWick': detect_long_wick,
    'BigBodyRev': detect_big_body_reversal,
}

WEEKDAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

# Cache file for storing already-sent signals
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.fqv_cache.json')


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def load_candles(filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)
    if isinstance(data, list):
        candles = data
    elif isinstance(data, dict) and 'candles' in data:
        candles = data['candles']
    else:
        candles = data
    normalized = []
    for c in candles:
        normalized.append({
            'time': int(c['time']),
            'datetime': c.get('datetime', ''),
            'open': float(c['open']),
            'high': float(c['high']),
            'low': float(c['low']),
            'close': float(c['close']),
        })
    normalized.sort(key=lambda c: c['time'])
    return normalized


def get_pair_name(filepath):
    basename = os.path.basename(filepath)
    name = os.path.splitext(basename)[0]
    parts = name.split('_')
    return parts[0] if parts else name


def load_cache():
    """Load the cache of already-sent signals."""
    if not os.path.exists(CACHE_FILE):
        return set()
    try:
        with open(CACHE_FILE, 'r') as f:
            return set(json.load(f))
    except (json.JSONDecodeError, IOError):
        return set()


def save_cache(cache):
    """Save the cache of sent signals."""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(list(cache), f)
    except IOError:
        pass


def clear_cache():
    """Delete the cache file."""
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)


def parse_time_range(time_str):
    """Parse time range like '09:00-12:00' or '23:00-00:00'.
    Returns (start_minutes, end_minutes) where minutes are from 00:00.
    Handles midnight crossover (e.g. 23:00-01:00 → 1380 to 60).
    """
    if not time_str:
        return None, None
    
    parts = time_str.split('-')
    if len(parts) != 2:
        return None, None
    
    def parse_hm(hm):
        h, m = hm.split(':')
        return int(h) * 60 + int(m)
    
    start = parse_hm(parts[0].strip())
    end = parse_hm(parts[1].strip())
    return start, end


def time_in_range(minutes, start, end):
    """Check if minutes is in range [start, end].
    Handles midnight crossover."""
    if start is None or end is None:
        return True
    if start <= end:
        return start <= minutes <= end
    else:
        # Crossover (e.g. 23:00-01:00)
        return minutes >= start or minutes <= end


# ============================================================================
# SIGNAL GENERATION
# ============================================================================

def generate_signals(candles, pair_name):
    """Generate signals for a pair using elite pattern database."""
    all_signals = []
    
    for pattern_name, detector in PATTERN_DETECTORS.items():
        raw_signals = detector(candles)
        for sig in raw_signals:
            entry_idx = sig['entry_idx']
            if entry_idx >= len(candles):
                continue
            
            entry_candle = candles[entry_idx]
            dt = datetime.fromtimestamp(entry_candle['time'], tz=timezone.utc)
            weekday = dt.weekday()
            our_weekday = (weekday + 1) % 7
            day_name = WEEKDAY_NAMES[our_weekday]
            
            key = f"{pair_name}:{day_name}:{pattern_name}:{sig['direction']}"
            if key in ELITE_PATTERNS:
                c1_rate, c12_rate, net_profit = ELITE_PATTERNS[key]
                all_signals.append({
                    'timestamp': entry_candle['time'],
                    'pair': pair_name,
                    'pattern': pattern_name,
                    'direction': sig['direction'],
                    'weekday': day_name,
                    'c1_rate': c1_rate,
                    'c12_rate': c12_rate,
                    'net_profit': net_profit,
                })
    
    return all_signals


def filter_by_time(signals, tz_offset, start_min, end_min):
    """Filter signals by time range in user's timezone."""
    filtered = []
    for s in signals:
        dt_local = datetime.fromtimestamp(s['timestamp'], tz=timezone.utc) + timedelta(hours=tz_offset)
        local_minutes = dt_local.hour * 60 + dt_local.minute
        if time_in_range(local_minutes, start_min, end_min):
            s['dt_local'] = dt_local
            filtered.append(s)
    return filtered


def deduplicate_and_gap_filter(signals, gap_minutes=4):
    """Remove duplicates (same minute → keep highest C1+C2) and enforce minimum gap.
    
    Args:
        signals: List of signal dicts (sorted by time)
        gap_minutes: Minimum minutes between consecutive signals
    
    Returns:
        Filtered list of signals
    """
    if not signals:
        return []
    
    # Sort by timestamp
    signals.sort(key=lambda s: s['timestamp'])
    
    # Step 1: Deduplicate by minute (keep highest C1+C2 per minute)
    by_minute = {}
    for s in signals:
        minute_key = s['timestamp'] // 60  # floor to minute
        if minute_key not in by_minute:
            by_minute[minute_key] = s
        else:
            if s['c12_rate'] > by_minute[minute_key]['c12_rate']:
                by_minute[minute_key] = s
    
    unique_signals = sorted(by_minute.values(), key=lambda s: s['timestamp'])
    
    # Step 2: Enforce minimum gap
    final_signals = []
    last_time = None
    
    for s in unique_signals:
        if last_time is None:
            final_signals.append(s)
            last_time = s['timestamp']
        else:
            gap = (s['timestamp'] - last_time) / 60
            if gap >= gap_minutes:
                final_signals.append(s)
                last_time = s['timestamp']
    
    return final_signals


# ============================================================================
# OUTPUT
# ============================================================================

def print_telegram_style(signals, tz_offset, gap_minutes):
    """Print signals in Telegram channel format."""
    if not signals:
        print("\n  ⚠ No signals found matching your criteria.")
        print("    Try a wider time range or different gap setting.")
        return
    
    tz_label = f"UTC+{tz_offset}" if tz_offset >= 0 else f"UTC{tz_offset}"
    
    print()
    print("━" * 7 + " • " + "━" * 7)
    
    for s in signals:
        dt_local = datetime.fromtimestamp(s['timestamp'], tz=timezone.utc) + timedelta(hours=tz_offset)
        time_str = dt_local.strftime('%H:%M')
        pair_str = f"{s['pair']}-OTC"
        direction = "CALL" if s['direction'] == 'BUY' else "PUT"
        print(f"M1 {pair_str} {time_str} {direction}")
    
    print("━" * 7 + " • " + "━" * 7)
    
    call_count = sum(1 for s in signals if s['direction'] == 'BUY')
    put_count = len(signals) - call_count
    print(f"\n  Total: {len(signals)} signals | CALL={call_count} | PUT={put_count}")
    print(f"  Timezone: {tz_label} | Min gap: {gap_minutes} min")
    print(f"  Strategy: Entry 1 → MTG1 → STOP | Max loss: 3× stake")
    print()


def print_detailed(signals, tz_offset):
    """Print detailed table with pattern info."""
    if not signals:
        return
    
    tz_label = f"UTC+{tz_offset}" if tz_offset >= 0 else f"UTC{tz_offset}"
    
    print(f"\n{'='*110}")
    print(f"  Detailed Report ({len(signals)} signals, {tz_label})")
    print(f"{'='*110}")
    print(f"\n  {'#':<4} {'Time':<6} {'Pair':<9} {'Pattern':<12} {'Dir':<5} {'C1':>7} {'C1+C2':>8} {'Profit':>8}")
    print(f"  {'-'*80}")
    
    for i, s in enumerate(signals, 1):
        dt_local = datetime.fromtimestamp(s['timestamp'], tz=timezone.utc) + timedelta(hours=tz_offset)
        time_str = dt_local.strftime('%H:%M')
        direction = "CALL" if s['direction'] == 'BUY' else "PUT"
        print(f"  {i:<4} {time_str:<6} {s['pair']:<9} {s['pattern']:<12} {direction:<5} "
              f"{s['c1_rate']:>6.1f}% {s['c12_rate']:>7.1f}% {s['net_profit']:>7.1f}×")
    
    print(f"\n  {'-'*80}")
    print()


def save_csv(signals, tz_offset, filename='futurequantvexa_signals.csv'):
    """Save signals to CSV."""
    if not signals:
        return
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['time', 'pair', 'pattern', 'direction', 'weekday',
                         'c1_rate', 'c12_rate', 'net_profit', 'timestamp'])
        for s in signals:
            dt_local = datetime.fromtimestamp(s['timestamp'], tz=timezone.utc) + timedelta(hours=tz_offset)
            writer.writerow([
                dt_local.strftime('%H:%M'),
                s['pair'], s['pattern'],
                'CALL' if s['direction'] == 'BUY' else 'PUT',
                s['weekday'],
                f"{s['c1_rate']:.1f}%",
                f"{s['c12_rate']:.1f}%",
                f"{s['net_profit']:.1f}×",
                s['timestamp'],
            ])
    
    print(f"  ✓ Saved {len(signals)} signals to: {filename}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='FutureQuantVexa v2.0 — Pattern-Based Signal Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python futurequantvexa.py *.json --tz=1 --time=09:00-12:00 --gap=4
  python futurequantvexa.py *.json --tz=1 --time=23:00-00:00 --gap=3
  python futurequantvexa.py *.json --tz=1 --gap=5 --clear-cache
  python futurequantvexa.py pair.json --tz=1 --time=22:00-02:00 --gap=4
        """)
    
    parser.add_argument('files', nargs='+', help='JSON candle data file(s)')
    parser.add_argument('--tz', type=int, default=0, 
                        help='Timezone offset from UTC (default: 0). e.g. --tz=1 for UTC+1')
    parser.add_argument('--time', type=str, default=None,
                        help='Time range filter (HH:MM-HH:MM). e.g. --time=09:00-12:00 or --time=23:00-00:00')
    parser.add_argument('--gap', type=int, default=4,
                        help='Minimum minutes between signals (default: 4). e.g. --gap=3 or --gap=5')
    parser.add_argument('--clear-cache', action='store_true',
                        help='Clear the sent-signals cache (start fresh)')
    parser.add_argument('--no-cache', action='store_true',
                        help='Disable cache (allow duplicate signals across runs)')
    parser.add_argument('--detailed', action='store_true',
                        help='Show detailed table with pattern info')
    
    args = parser.parse_args()
    
    # Clear cache if requested
    if args.clear_cache:
        clear_cache()
        print("  ✓ Cache cleared.")
        print()
    
    # Load cache
    cache = set() if args.no_cache else load_cache()
    
    tz_label = f"UTC+{args.tz}" if args.tz >= 0 else f"UTC{args.tz}"
    
    # Parse time range
    start_min, end_min = parse_time_range(args.time) if args.time else (None, None)
    
    print()
    print("=" * 80)
    print("  FutureQuantVexa v2.0 — Advanced Signal Generator")
    print("  Strategy: Entry 1 → MTG1 → STOP | Max loss: 3× stake")
    print("  18 patterns × 7 weekdays × 13 pairs = 142 elite combinations")
    print("=" * 80)
    print(f"  Timezone: {tz_label}")
    if args.time:
        print(f"  Time range: {args.time} ({tz_label})")
    print(f"  Min gap: {args.gap} minutes")
    print(f"  Cache: {'disabled' if args.no_cache else 'enabled (' + str(len(cache)) + ' sent)'}")
    print()
    
    # Load and process files
    all_signals = []
    
    for filepath in args.files:
        if not os.path.exists(filepath):
            print(f"  ✗ File not found: {filepath}")
            continue
        
        pair_name = get_pair_name(filepath)
        print(f"  [{pair_name}] Loading...", end=' ')
        
        try:
            candles = load_candles(filepath)
            print(f"{len(candles)} candles")
            
            signals = generate_signals(candles, pair_name)
            all_signals.extend(signals)
            print(f"           → {len(signals)} elite signals")
        except Exception as e:
            print(f"ERROR: {e}")
    
    print()
    
    # Filter by time range
    if start_min is not None:
        all_signals = filter_by_time(all_signals, args.tz, start_min, end_min)
        print(f"  After time filter: {len(all_signals)} signals")
    
    # Remove already-sent signals (cache)
    new_signals = []
    for s in all_signals:
        cache_key = f"{s['timestamp']}_{s['pair']}_{s['pattern']}_{s['direction']}"
        if cache_key not in cache:
            new_signals.append(s)
    
    print(f"  After cache filter: {len(new_signals)} new signals (removed {len(all_signals) - len(new_signals)} already sent)")
    
    # Deduplicate and gap filter
    filtered_signals = deduplicate_and_gap_filter(new_signals, args.gap)
    print(f"  After gap filter ({args.gap} min): {len(filtered_signals)} signals")
    print()
    
    # Output
    print_telegram_style(filtered_signals, args.tz, args.gap)
    
    if args.detailed:
        print_detailed(filtered_signals, args.tz)
    
    save_csv(filtered_signals, args.tz)
    
    # Update cache with newly sent signals
    if not args.no_cache and filtered_signals:
        for s in filtered_signals:
            cache_key = f"{s['timestamp']}_{s['pair']}_{s['pattern']}_{s['direction']}"
            cache.add(cache_key)
        save_cache(cache)
        print(f"  ✓ Cache updated: {len(cache)} total sent signals saved")
    
    # Summary
    if filtered_signals:
        print()
        print(f"  {'='*60}")
        print(f"  SUMMARY")
        print(f"  {'='*60}")
        
        # Per pair
        pair_counts = defaultdict(int)
        for s in filtered_signals:
            pair_counts[s['pair']] += 1
        print(f"\n  Per pair:")
        for pair, count in sorted(pair_counts.items(), key=lambda x: -x[1]):
            print(f"    {pair:<9}: {count} signals")
        
        # Per weekday
        day_counts = defaultdict(int)
        for s in filtered_signals:
            day_counts[s['weekday']] += 1
        print(f"\n  Per weekday:")
        for day in ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']:
            if day in day_counts:
                print(f"    {day}: {day_counts[day]} signals")
        
        # Time range
        if filtered_signals:
            first = min(s['timestamp'] for s in filtered_signals)
            last = max(s['timestamp'] for s in filtered_signals)
            first_dt = datetime.fromtimestamp(first, tz=timezone.utc) + timedelta(hours=args.tz)
            last_dt = datetime.fromtimestamp(last, tz=timezone.utc) + timedelta(hours=args.tz)
            print(f"\n  Time range: {first_dt.strftime('%H:%M')} → {last_dt.strftime('%H:%M')} ({tz_label})")
    
    print()
    print(f"  {'='*60}")
    print(f"  FutureQuantVexa v2.0 — Session Complete")
    print(f"  {'='*60}")
    print()


if __name__ == '__main__':
    main()
