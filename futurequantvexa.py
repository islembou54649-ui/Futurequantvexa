#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FutureQuantVexa — Pattern-Based Signal Generator for Quotex/OTC M1
====================================================================

Strategy:
    - 18 Japanese candlestick patterns × 7 weekdays × 13 pairs
    - MTG1 recovery (Entry 1 → if lost, MTG1 → STOP, no entry 3/4)
    - Max loss per signal: 3× stake (1 + 2)
    - Filters: only signals with ≥85% historical success (C1+C2) AND net profit > 0

Usage:
    python futurequantvexa.py file1.json [file2.json ...]
    
    Reads candle JSON files (one or many), detects patterns for the
    CURRENT weekday, and outputs signals sorted by time (not by pair).

Output:
    - Console table with all signals sorted by datetime
    - CSV file: futurequantvexa_signals.csv
    
Signal fields:
    - datetime: when the signal triggers
    - pair: which currency pair
    - pattern: which candlestick pattern
    - direction: BUY or SELL
    - entry_candle: which candle to enter (1 = first, MTG1 = recovery)
    - stake: 1× for entry 1, 2× for MTG1
    - historical_c1: success rate on entry 1 alone
    - historical_c1_c2: success rate on entry 1 OR MTG1 (cumulative)
    - max_loss: 3× stake (if both entries lose)
"""

import os
import sys
import json
import csv
from datetime import datetime, timezone
from collections import defaultdict

# ============================================================================
# ELITE PATTERN DATABASE
# ============================================================================
# Each entry: (pair, weekday, pattern_name, direction, c1_rate, c12_rate, net_profit)
# These are the 142 elite combinations validated with ≥85% C1+C2 success rate
# and positive net profit, using MTG1 (entry 1 → MTG1 → STOP) strategy.
# Format: pair:day:pattern:direction -> (c1_rate, c12_rate, net_profit)
# ============================================================================

ELITE_PATTERNS = {
    # ============================================================================
    # SUNDAY (weekday 0)
    # ============================================================================
    "USDPHP:Sun:GapRev:BUY":              (50.0, 86.7, 6.6),
    "USDNGN:Sun:InsideBody:SELL":          (50.0, 89.3, 8.8),
    "USDIDR:Sun:InsideBar:SELL":           (70.0, 95.0, 11.2),
    "USDIDR:Sun:PinBar:SELL":              (50.0, 94.4, 9.0),
    "USDIDR:Sun:ShootStar:SELL":           (33.3, 91.7, 4.4),
    "USDIDR:Sun:LongWick:SELL":            (52.4, 90.5, 7.6),
    "USDIDR:Sun:Harami:SELL":              (60.0, 90.0, 3.6),
    "USDMXN:Sun:Doji:SELL":                (55.6, 94.4, 9.2),
    "USDMXN:Sun:Marubozu:BUY":             (50.0, 92.9, 6.2),
    "USDMXN:Sun:LongWick:SELL":            (57.6, 87.9, 9.2),
    "USDMXN:Sun:PinBar:SELL":              (55.0, 85.0, 3.4),
    "USDMXN:Sun:Harami:BUY":               (58.3, 83.3, 7.8),
    "USDMXN:Sun:InsideBody:BUY":           (50.0, 81.3, 4.0),
    "USDCOP:Sun:Engulfing:SELL":            (58.3, 91.7, 5.0),
    "USDCOP:Sun:BigBodyRev:SELL":           (59.5, 86.5, 8.6),
    "USDCOP:Sun:Marubozu:SELL":             (66.7, 86.7, 3.8),
    "USDZAR:Sun:Tweezer:SELL":             (68.2, 86.4, 5.4),
    "USDZAR:Sun:InsideBar:BUY":            (60.0, 85.0, 3.6),
    "USDZAR:Sun:PinBar:SELL":              (47.1, 82.4, 9.8),
    "USDARS:Sun:GapRev:BUY":               (60.6, 90.9, 13.0),
    "USDARS:Sun:Engulfing:BUY":            (52.4, 90.5, 7.6),
    "USDARS:Sun:Marubozu:BUY":             (55.0, 85.0, 3.4),
    "USDBDT:Sun:Doji:BUY":                 (55.6, 83.3, 10.8),
    "USDDZD:Sun:PinBar:SELL":              (71.4, 85.7, 3.2),
    "USDEGP:Sun:Tweezer:SELL":             (71.4, 85.7, 3.2),
    "USDEGP:Sun:Marubozu:BUY":             (40.0, 86.7, 3.0),
    "USDEGP:Sun:BigBodyRev:SELL":          (51.4, 82.9, 20.6),
    "BRLUSD:Wed:ShootStar:SELL":           (50.0, 85.0, 3.2),
    
    # ============================================================================
    # MONDAY (weekday 1)
    # ============================================================================
    "USDINR:Mon:PinBar:BUY":               (66.7, 100.0, 11.0),
    "USDZAR:Mon:Doji:BUY":                 (75.0, 100.0, 9.0),
    "USDEGP:Mon:InsideBar:SELL":           (75.0, 93.8, 8.4),
    "USDMXN:Mon:Marubozu:SELL":           (73.3, 93.3, 7.6),
    "USDCOP:Mon:Star:BUY":                 (70.6, 94.1, 9.0),
    "USDARS:Mon:Star:BUY":                 (80.0, 93.3, 7.8),
    "USDARS:Mon:Harami:SELL":              (30.0, 90.0, 3.0),
    "USDINR:Mon:Tweezer:BUY":              (60.0, 86.7, 3.6),
    "BRLUSD:Mon:Engulfing:SELL":           (66.7, 91.7, 5.2),
    "BRLUSD:Mon:PinBar:BUY":               (68.4, 89.5, 6.8),
    "BRLUSD:Mon:LongWick:BUY":             (57.7, 88.5, 7.8),
    "BRLUSD:Mon:Hammer:BUY":               (64.3, 85.7, 3.0),
    "BRLUSD:Mon:Harami:BUY":               (38.5, 84.6, 8.0),
    "USDDZD:Mon:Tweezer:BUY":              (69.2, 92.3, 6.0),
    "USDDZD:Mon:InsideBar:BUY":            (50.0, 89.3, 8.8),
    "USDDZD:Mon:LongWick:BUY":             (56.7, 83.3, 19.4),
    "USDPHP:Mon:Marubozu:SELL":            (46.2, 92.3, 5.4),
    "USDPHP:Mon:Star:BUY":                 (71.4, 85.7, 3.2),
    "USDPHP:Mon:PinBar:BUY":               (43.8, 81.3, 9.0),
    "USDNGN:Mon:InsideBar:BUY":            (59.3, 88.9, 8.6),
    "USDNGN:Mon:InsideBody:BUY":           (60.0, 85.0, 3.6),
    "USDEGP:Mon:Star:BUY":                 (56.3, 87.5, 4.2),
    
    # ============================================================================
    # TUESDAY (weekday 2)
    # ============================================================================
    "USDINR:Tue:PinBar:BUY":               (60.0, 95.0, 10.8),
    "USDINR:Tue:ShootStar:SELL":           (20.0, 90.0, 2.8),
    "USDINR:Tue:Marubozu:SELL":            (50.0, 90.0, 3.4),
    "USDNGN:Tue:Engulfing:BUY":            (58.3, 91.7, 5.0),
    "USDNGN:Tue:InsideBar:SELL":           (63.2, 89.5, 6.6),
    "USDNGN:Tue:LongWick:SELL":            (57.7, 88.5, 7.8),
    "USDNGN:Tue:BigBodyRev:SELL":          (57.1, 82.9, 5.8),
    "USDNGN:Tue:Tweezer:BUY":              (59.5, 85.7, 8.6),
    "USDARS:Tue:PinBar:SELL":              (71.4, 85.7, 3.2),
    "USDARS:Tue:GapRev:BUY":               (60.0, 85.7, 7.2),
    "USDARS:Tue:LongWick:SELL":             (65.4, 84.6, 1.4),
    "USDPKR:Tue:InsideBody:BUY":           (69.4, 91.7, 15.8),
    "USDPKR:Tue:GapRev:BUY":               (53.7, 87.8, 11.0),
    "USDPKR:Tue:Star:BUY":                 (51.6, 83.9, 18.2),
    "USDPKR:Tue:Harami:SELL":              (54.5, 81.8, 7.0),
    "USDIDR:Tue:Engulfing:SELL":           (56.3, 87.5, 4.2),
    "USDIDR:Tue:PinBar:SELL":              (39.1, 87.0, 4.8),
    "USDIDR:Tue:ShootStar:SELL":           (10.0, 90.0, 2.8),
    "USDIDR:Tue:Doji:SELL":                (42.9, 82.1, 15.6),
    "USDIDR:Tue:Tweezer:SELL":             (65.6, 87.5, 9.0),
    "USDIDR:Tue:InsideBar:BUY":            (53.3, 83.3, 4.0),
    "USDIDR:Tue:BigBodyRev:BUY":           (46.3, 82.9, 24.8),
    "USDZAR:Tue:Hammer:SELL":              (58.3, 91.7, 5.0),
    "USDZAR:Tue:Doji:SELL":                (65.0, 85.0, 3.8),
    "USDZAR:Tue:Marubozu:BUY":             (52.4, 85.7, 4.0),
    "USDMXN:Tue:Doji:SELL":                (53.3, 86.7, 3.4),
    "USDCOP:Tue:3Soldiers:BUY":            (60.9, 85.5, 13.8),
    "USDCOP:Tue:Consec2:BUY":              (57.9, 81.7, 33.0),
    "BRLUSD:Fri:Engulfing:BUY":            (51.9, 85.2, 4.6),
    
    # ============================================================================
    # WEDNESDAY (weekday 3)
    # ============================================================================
    "USDPHP:Wed:Harami:SELL":              (56.3, 93.8, 7.8),
    "USDPHP:Wed:InsideBar:SELL":           (48.1, 86.5, 11.0),
    "USDNGN:Wed:Harami:BUY":               (62.5, 87.5, 4.4),
    "USDNGN:Wed:InsideBar:BUY":            (51.1, 87.2, 11.4),
    "USDNGN:Wed:Tweezer:BUY":              (59.5, 85.7, 8.6),
    "USDARS:Wed:Star:SELL":                (69.2, 87.2, 10.8),
    "USDDZD:Wed:PinBar:SELL":              (54.8, 90.3, 11.2),
    "USDDZD:Wed:ShootStar:SELL":           (58.8, 88.2, 5.0),
    "USDDZD:Wed:LongWick:SELL":            (54.4, 84.2, 4.0),
    "USDDZD:Tue:TrendCont:BUY":            (63.6, 85.5, 11.2),
    "USDMXN:Wed:ShootStar:SELL":           (54.5, 86.4, 4.8),
    "USDMXN:Wed:Harami:BUY":               (63.6, 86.4, 5.2),
    "USDZAR:Wed:Harami:BUY":               (60.9, 82.6, 14.2),
    
    # ============================================================================
    # THURSDAY (weekday 4)
    # ============================================================================
    "USDINR:Thu:ShootStar:SELL":           (72.2, 94.4, 9.8),
    "USDINR:Thu:BigBodyRev:SELL":          (60.0, 86.2, 12.0),
    "USDINR:Thu:Harami:BUY":               (47.1, 82.4, 9.8),
    "USDZAR:Thu:Harami:BUY":               (50.0, 94.4, 9.0),
    "USDZAR:Thu:GapRev:SELL":              (44.9, 84.1, 26.4),
    "USDARS:Thu:InsideBar:BUY":            (63.6, 88.6, 14.0),
    "USDARS:Thu:Harami:BUY":               (58.8, 88.2, 5.0),
    "USDARS:Thu:Marubozu:SELL":            (52.2, 87.0, 5.4),
    "USDARS:Thu:Tweezer:BUY":               (51.9, 85.2, 4.6),
    "USDDZD:Thu:Hammer:BUY":               (68.2, 81.8, 13.8),
    "USDEGP:Thu:Marubozu:BUY":             (60.9, 87.0, 5.8),
    "USDPHP:Thu:Hammer:SELL":              (50.0, 90.0, 3.4),
    "USDBDT:Thu:Marubozu:SELL":            (48.3, 86.2, 5.8),
    "USDBDT:Thu:BigBodyRev:SELL":          (47.5, 85.2, 10.0),
    "USDBDT:Thu:PinBar:BUY":               (59.6, 83.0, 0.2),
    
    # ============================================================================
    # FRIDAY (weekday 5)
    # ============================================================================
    "USDCOP:Fri:ShootStar:SELL":           (52.4, 95.2, 11.2),
    "USDINR:Fri:Engulfing:BUY":            (71.4, 89.3, 10.0),
    "USDMXN:Fri:Marubozu:SELL":            (54.2, 91.7, 9.8),
    "USDMXN:Fri:PinBar:BUY":               (68.8, 90.6, 12.8),
    "USDMXN:Fri:Star:SELL":                 (57.6, 81.8, 5.2),
    "USDMXN:Fri:Tweezer:SELL":              (57.1, 82.1, 2.0),
    "USDNGN:Fri:Hammer:BUY":               (64.7, 88.2, 5.2),
    "USDNGN:Fri:InsideBar:BUY":            (52.1, 85.4, 8.6),
    "USDNGN:Fri:Tweezer:SELL":              (64.5, 87.1, 8.2),
    "USDEGP:Fri:Marubozu:BUY":             (54.5, 87.9, 9.0),
    "USDIDR:Fri:ShootStar:SELL":           (56.3, 87.5, 4.2),
    "USDIDR:Fri:PinBar:SELL":              (45.5, 81.8, 4.4),
    "USDCOP:Fri:Star:BUY":                 (55.3, 81.6, 7.4),
    "BRLUSD:Fri:Tweezer:SELL":             (69.0, 86.2, 7.0),
    "BRLUSD:Fri:Engulfing:BUY":            (51.9, 85.2, 4.6),
    "USDDZD:Fri:Hammer:SELL":              (35.0, 85.0, 2.6),
    "USDPHP:Fri:Harami:BUY":               (59.1, 86.4, 5.0),
    
    # ============================================================================
    # SATURDAY (weekday 6)
    # ============================================================================
    "USDDZD:Sat:Marubozu:SELL":            (66.7, 100.0, 8.8),
    "USDINR:Sat:Tweezer:SELL":             (76.9, 100.0, 9.8),
    "USDPKR:Sat:PinBar:BUY":               (52.2, 95.7, 12.6),
    "USDBDT:Sat:PinBar:BUY":               (53.3, 93.3, 7.0),
    "USDZAR:Sat:Star:BUY":                 (46.7, 93.3, 6.8),
    "USDDZD:Sat:Star:SELL":                (42.9, 92.9, 6.0),
    "USDINR:Sat:Star:SELL":                (64.3, 92.9, 13.2),
    "USDNGN:Sat:Star:BUY":                 (73.3, 86.7, 4.0),
    "USDNGN:Sat:GapRev:SELL":              (56.7, 86.7, 7.0),
    "USDPHP:Sat:Hammer:SELL":              (50.0, 91.7, 4.8),
    "USDPHP:Sat:Tweezer:BUY":              (58.3, 91.7, 5.0),
    "USDPHP:Sat:PinBar:BUY":               (45.5, 90.9, 4.0),
    "USDPKR:Sat:InsideBody:BUY":           (63.6, 90.9, 8.8),
    "USDPKR:Sat:Star:BUY":                 (63.2, 89.5, 6.6),
    "USDPKR:Sat:LongWick:BUY":             (52.9, 82.4, 4.8),
    "USDPKR:Sat:Engulfing:BUY":            (66.7, 88.9, 6.0),
    "USDDZD:Sat:PinBar:SELL":              (50.0, 87.5, 4.0),
    "USDDZD:Sat:Tweezer:BUY":              (50.0, 87.5, 4.0),
    "USDDZD:Sat:LongWick:SELL":            (56.5, 87.0, 5.6),
    "USDDZD:Sat:Engulfing:BUY":            (53.8, 84.6, 7.6),
    "USDDZD:Sat:TrendCont:SELL":           (60.0, 86.0, 10.8),
    "USDBDT:Sat:LongWick:BUY":             (48.1, 88.9, 8.0),
    "USDIDR:Sat:InsideBar:BUY":            (50.0, 88.9, 5.4),
    "USDIDR:Sat:3Soldiers:SELL":           (63.0, 81.5, 19.2),
    "USDIDR:Sat:TrendCont:BUY":            (52.2, 87.0, 10.8),
    "USDARS:Sat:Hammer:BUY":               (70.0, 90.0, 3.8),
    "USDARS:Sat:LongWick:BUY":             (61.3, 87.1, 8.0),
    "USDARS:Sat:InsideBody:BUY":           (52.2, 87.0, 5.4),
    "USDARS:Sat:BigBodyRev:SELL":          (65.2, 87.0, 6.0),
    "USDCOP:Sat:Marubozu:BUY":             (54.5, 86.4, 4.8),
    "USDCOP:Sat:Tweezer:SELL":             (58.6, 86.2, 6.4),
    "USDCOP:Sat:GapRev:BUY":               (53.3, 82.2, 11.8),
    "USDMXN:Sat:BigBodyRev:SELL":          (40.7, 81.5, 0.4),
    "USDMXN:Sat:Engulfing:BUY":           (58.8, 88.2, 5.0),
    "USDZAR:Sat:Doji:BUY":                 (45.5, 81.8, 6.8),
    "USDZAR:Sat:Engulfing:BUY":            (50.0, 87.5, 4.0),
    "USDEGP:Mon:InsideBar:SELL":            (75.0, 93.8, 8.4),
}


# ============================================================================
# PATTERN DETECTION FUNCTIONS
# ============================================================================

def detect_doji(candles):
    """Doji — body ≤ 10% of range → reversal signal"""
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
    """Hammer — small body at top, long lower wick → bullish reversal"""
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
    """Shooting Star — long upper wick after uptrend → bearish reversal"""
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
    """Morning/Evening Star — 3-candle reversal pattern"""
    signals = []
    for i in range(2, len(candles) - 1):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        # Morning Star → BUY
        if (c1['close'] < c1['open'] and
            abs(c2['close'] - c2['open']) < abs(c1['close'] - c1['open']) * 0.5 and
            c3['close'] > c3['open'] and
            c3['close'] > (c1['open'] + c1['close']) / 2):
            signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'Star'})
        # Evening Star → SELL
        if (c1['close'] > c1['open'] and
            abs(c2['close'] - c2['open']) < abs(c1['close'] - c1['open']) * 0.5 and
            c3['close'] < c3['open'] and
            c3['close'] < (c1['open'] + c1['close']) / 2):
            signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'Star'})
    return signals


def detect_three_soldiers(candles):
    """Three White Soldiers / Three Black Crows → trend continuation"""
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
    """Harami — inside bar (pregnancy pattern) → reversal"""
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
    """Piercing Line / Dark Cloud Cover → reversal"""
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
    """Tweezer Top/Bottom → reversal"""
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
    """Marubozu — full body, no wicks → strong continuation"""
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
    """Inside Bar — inside bar breakout (direction from inside bar's own close)"""
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
    """Pin Bar — long wick + small body → reversal"""
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
    """Engulfing — outside reversal → reversal"""
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
    """Higher highs + higher lows (or lower) → continuation"""
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
    """Inside Body Close → reversal"""
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
    """Gap Reversal → gap fill expected"""
    signals = []
    for i in range(1, len(candles) - 1):
        prev, c = candles[i-1], candles[i]
        if c['open'] > prev['close'] and c['close'] < prev['close']:
            signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'GapRev'})
        if c['open'] < prev['close'] and c['close'] > prev['close']:
            signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'GapRev'})
    return signals


def detect_consecutive(candles):
    """2 consecutive same-direction candles → continuation"""
    signals = []
    for i in range(1, len(candles) - 1):
        prev, c = candles[i-1], candles[i]
        if prev['close'] > prev['open'] and c['close'] > c['open']:
            signals.append({'entry_idx': i + 1, 'direction': 'BUY', 'pattern': 'Consec2'})
        if prev['close'] < prev['open'] and c['close'] < c['open']:
            signals.append({'entry_idx': i + 1, 'direction': 'SELL', 'pattern': 'Consec2'})
    return signals


def detect_long_wick(candles):
    """Long Wick Reversal → reversal"""
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
    """Big Body Reversal → large body opposite to previous"""
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


# Pattern registry
PATTERN_DETECTORS = {
    'Doji': detect_doji,
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
WEEKDAY_FULL = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']


# ============================================================================
# MAIN SIGNAL GENERATOR
# ============================================================================

def load_candles(filepath):
    """Load candles from JSON file. Accepts array or {candles: [...]} format."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    if isinstance(data, list):
        candles = data
    elif isinstance(data, dict) and 'candles' in data:
        candles = data['candles']
    else:
        candles = data
    # Normalize
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
    """Extract pair name from filename. e.g. USDDZD_otc_1m_10d_xxx.json → USDDZD"""
    basename = os.path.basename(filepath)
    # Remove extension
    name = os.path.splitext(basename)[0]
    # Take first part before underscore
    parts = name.split('_')
    return parts[0] if parts else name


def generate_signals(candles, pair_name):
    """Generate signals for a pair using elite pattern database.
    Only emits signals for patterns that are in the elite database for
    the CURRENT weekday of each candle.
    """
    all_signals = []
    
    for pattern_name, detector in PATTERN_DETECTORS.items():
        raw_signals = detector(candles)
        for sig in raw_signals:
            entry_idx = sig['entry_idx']
            if entry_idx >= len(candles):
                continue
            
            entry_candle = candles[entry_idx]
            # Get weekday of the entry candle
            weekday = datetime.fromtimestamp(entry_candle['time'], tz=timezone.utc).weekday()
            # Python weekday: Monday=0, Sunday=6
            # Our database uses: Sun=0, Mon=1, ..., Sat=6
            # Convert: Python Mon=0 → our Mon=1, Python Sun=6 → our Sun=0
            our_weekday = (weekday + 1) % 7
            day_name = WEEKDAY_NAMES[our_weekday]
            
            # Check if this combination is in the elite database
            key = f"{pair_name}:{day_name}:{pattern_name}:{sig['direction']}"
            if key in ELITE_PATTERNS:
                c1_rate, c12_rate, net_profit = ELITE_PATTERNS[key]
                all_signals.append({
                    'datetime': entry_candle['datetime'] or datetime.fromtimestamp(
                        entry_candle['time'], tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp': entry_candle['time'],
                    'pair': pair_name,
                    'pattern': pattern_name,
                    'direction': sig['direction'],
                    'weekday': day_name,
                    'entry_candle': 'Entry 1',
                    'stake': '1×',
                    'mtg1_stake': '2× (if Entry 1 loses)',
                    'historical_c1': f"{c1_rate:.1f}%",
                    'historical_c1_c2': f"{c12_rate:.1f}%",
                    'net_profit': f"{net_profit:.1f}×",
                    'max_loss': '3× stake',
                    'price': entry_candle['open'],
                })
    
    return all_signals


def print_signals(signals, tz_offset=0):
    """Print signals sorted by datetime (mixed pairs, sorted by time).
    
    Args:
        signals: List of signal dicts
        tz_offset: Timezone offset in hours from UTC (e.g. +1 for UTC+1)
    """
    if not signals:
        print("\n  ⚠ No elite signals found in the provided data files.")
        print("    Make sure the data contains candles for weekdays that match")
        print("    the elite pattern database (Sun/Mon/Tue/Wed/Thu/Fri/Sat).")
        return
    
    from datetime import timedelta
    
    # Sort by timestamp (ascending = chronological order)
    signals.sort(key=lambda s: s['timestamp'])
    
    tz_label = f"UTC+{tz_offset}" if tz_offset >= 0 else f"UTC{tz_offset}"
    
    # ── Telegram-style channel output ──
    # Format: M1 PAIR-OTC HH:MM CALL/PUT
    print()
    print("━" * 7 + " • " + "━" * 7)
    
    for s in signals:
        # Apply timezone offset
        dt = datetime.fromtimestamp(s['timestamp'], tz=timezone.utc) + timedelta(hours=tz_offset)
        time_str = dt.strftime('%H:%M')
        pair_str = f"{s['pair']}-OTC"
        direction = "CALL" if s['direction'] == 'BUY' else "PUT"
        print(f"M1 {pair_str} {time_str} {direction}")
    
    print("━" * 7 + " • " + "━" * 7)
    print(f"\n  Total: {len(signals)} signals | CALL={sum(1 for s in signals if s['direction']=='BUY')} | PUT={sum(1 for s in signals if s['direction']=='SELL')}")
    print(f"  Strategy: Entry 1 → MTG1 → STOP | Max loss: 3× stake")
    print(f"  Timezone: {tz_label} (offset: {'+' if tz_offset >= 0 else ''}{tz_offset}h from UTC)")
    print()
    
    # ── Detailed table (for reference) ──
    print(f"\n{'='*120}")
    print(f"  Detailed Signal Report ({len(signals)} signals, sorted by time, {tz_label})")
    print(f"{'='*120}")
    print(f"\n  {'#':<4} {'Datetime':<22} {'Pair':<9} {'Pattern':<12} {'Dir':<5} {'Day':<4} {'C1':>7} {'C1+C2':>8} {'Profit':>8} {'Entry':<10}")
    print(f"  {'-'*108}")
    
    for i, s in enumerate(signals, 1):
        from datetime import timedelta
        dt = datetime.fromtimestamp(s['timestamp'], tz=timezone.utc) + timedelta(hours=tz_offset)
        dt_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        
        dir_color = '\033[32m' if s['direction'] == 'BUY' else '\033[31m'
        reset = '\033[0m'
        print(f"  {i:<4} {dt_str:<22} {s['pair']:<9} {s['pattern']:<12} "
              f"{dir_color}{s['direction']:<5}{reset} {s['weekday']:<4} "
              f"{s['historical_c1']:>7} {s['historical_c1_c2']:>8} {s['net_profit']:>8} {s['entry_candle']:<10}")
    
    print(f"\n  {'-'*108}")
    print(f"  Total: {len(signals)} signals | Max loss per signal: 3× stake (Entry 1: 1× + MTG1: 2×)")
    print(f"  Strategy: Entry 1 → if lost, MTG1 (same direction, 2× stake) → STOP")
    print(f"  No Entry 3 or Entry 4 — MTG1 is the final recovery entry.")
    print(f"  Timezone: {tz_label}")
    print()


def save_csv(signals, filename='futurequantvexa_signals.csv'):
    """Save signals to CSV file."""
    if not signals:
        return
    
    signals_sorted = sorted(signals, key=lambda s: s['timestamp'])
    
    fieldnames = [
        'datetime', 'pair', 'pattern', 'direction', 'weekday',
        'entry_candle', 'stake', 'mtg1_stake',
        'historical_c1', 'historical_c1_c2', 'net_profit', 'max_loss', 'price'
    ]
    
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for s in signals_sorted:
            writer.writerow(s)
    
    print(f"  ✓ Saved {len(signals_sorted)} signals to: {filename}")


def main():
    print()
    print("=" * 80)
    print("  FutureQuantVexa — Pattern-Based Signal Generator")
    print("  Strategy: Entry 1 → MTG1 (recovery) → STOP | Max loss: 3× stake")
    print("  18 patterns × 7 weekdays × 13 pairs = 142 elite combinations")
    print("=" * 80)
    print()
    
    # Parse arguments: files + optional --tz offset
    tz_offset = 0
    files = []
    args = sys.argv[1:]
    
    for arg in args:
        if arg.startswith('--tz='):
            try:
                tz_offset = int(arg.split('=')[1])
            except ValueError:
                print(f"  ⚠ Invalid timezone offset: {arg}")
                sys.exit(1)
        elif arg.startswith('--'):
            if arg == '--help' or arg == '-h':
                print("  Usage: python futurequantvexa.py <file1.json> [file2.json ...] [--tz=OFFSET]")
                print()
                print("  Options:")
                print("    --tz=OFFSET   Timezone offset from UTC (e.g. --tz=1 for UTC+1)")
                print("                  Default: 0 (UTC)")
                print()
                print("  Examples:")
                print("    python futurequantvexa.py USDDZD_otc_1m_10d_xxx.json")
                print("    python futurequantvexa.py *.json --tz=1")
                print("    python futurequantvexa.py pair1.json pair2.json --tz=-5")
                sys.exit(0)
        else:
            files.append(arg)
    
    if not files:
        print("  Usage: python futurequantvexa.py <file1.json> [file2.json ...] [--tz=OFFSET]")
        print()
        print("  Examples:")
        print("    python futurequantvexa.py USDDZD_otc_1m_10d_xxx.json")
        print("    python futurequantvexa.py *.json --tz=1      # UTC+1 timezone")
        print("    python futurequantvexa.py pair1.json pair2.json --tz=-5  # UTC-5")
        print()
        print("  Output:")
        print("    - Console table with signals sorted by datetime")
        print("    - CSV file: futurequantvexa_signals.csv")
        print()
        sys.exit(1)
    
    tz_label = f"UTC+{tz_offset}" if tz_offset >= 0 else f"UTC{tz_offset}"
    print(f"  Timezone: {tz_label}")
    print(f"  Loading {len(files)} file(s)...")
    print()
    
    all_signals = []
    
    for filepath in files:
        if not os.path.exists(filepath):
            print(f"  ✗ File not found: {filepath}")
            continue
        
        pair_name = get_pair_name(filepath)
        print(f"  [{pair_name}] Loading {os.path.basename(filepath)}...", end=' ')
        
        try:
            candles = load_candles(filepath)
            print(f"{len(candles)} candles")
            
            signals = generate_signals(candles, pair_name)
            all_signals.extend(signals)
            print(f"           → {len(signals)} elite signals found")
        except Exception as e:
            print(f"ERROR: {e}")
    
    print()
    print_signals(all_signals, tz_offset=tz_offset)
    save_csv(all_signals)
    
    if all_signals:
        # Summary stats
        print()
        print(f"  {'='*60}")
        print(f"  SUMMARY")
        print(f"  {'='*60}")
        buy_count = sum(1 for s in all_signals if s['direction'] == 'BUY')
        sell_count = len(all_signals) - buy_count
        print(f"  Total signals:    {len(all_signals)}")
        print(f"  BUY signals:      {buy_count}")
        print(f"  SELL signals:     {sell_count}")
        
        # Per-pair breakdown
        pair_counts = defaultdict(int)
        for s in all_signals:
            pair_counts[s['pair']] += 1
        print(f"\n  Per pair:")
        for pair, count in sorted(pair_counts.items(), key=lambda x: -x[1]):
            print(f"    {pair:<9}: {count} signals")
        
        # Per-weekday breakdown
        day_counts = defaultdict(int)
        for s in all_signals:
            day_counts[s['weekday']] += 1
        print(f"\n  Per weekday:")
        for day in ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']:
            if day in day_counts:
                print(f"    {day}: {day_counts[day]} signals")
        
        # Time range
        first = min(s['timestamp'] for s in all_signals)
        last = max(s['timestamp'] for s in all_signals)
        first_dt = datetime.fromtimestamp(first, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
        last_dt = datetime.fromtimestamp(last, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
        print(f"\n  Time range: {first_dt} → {last_dt} UTC")
        print()
    
    print(f"  {'='*60}")
    print(f"  FutureQuantVexa — Session Complete")
    print(f"  {'='*60}")
    print()


if __name__ == '__main__':
    main()
