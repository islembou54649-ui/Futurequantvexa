#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FutureQuantVexa v3.1 — Interactive Signal Generator (Telegram-ready)
====================================================================

Pipeline:
  1. SCAN:     Reads candle JSON → detects all 18 patterns → stores ALL signals
  2. EXTRACT:  User picks day/direction/time/gap interactively → output list
  3. Interactive menu with numbered buttons (ready for Telegram bot)

Usage:
  python fqv3.py scan *.json          # Stage 1: scan candle files
  python fqv3.py extract [options]    # Stage 2: extract (CLI mode)
  python fqv3.py interactive          # Stage 2: extract (interactive menu)
  python fqv3.py clear-cache          # Clear sent cache
"""

import os, sys, json, re, csv, argparse
from datetime import datetime, timedelta, timezone
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(SCRIPT_DIR, '.fqv_raw')
SENT_CACHE = os.path.join(SCRIPT_DIR, '.fqv_sent.json')

# ============================================================================
# ELITE PATTERN DATABASE
# ============================================================================
ELITE_PATTERNS = {
    "USDPHP:Sun:GapRev:BUY":(50.0,86.7,6.6),"USDNGN:Sun:InsideBody:SELL":(50.0,89.3,8.8),
    "USDIDR:Sun:InsideBar:SELL":(70.0,95.0,11.2),"USDIDR:Sun:PinBar:SELL":(50.0,94.4,9.0),
    "USDIDR:Sun:ShootStar:SELL":(33.3,91.7,4.4),"USDIDR:Sun:LongWick:SELL":(52.4,90.5,7.6),
    "USDIDR:Sun:Harami:SELL":(60.0,90.0,3.6),"USDMXN:Sun:Doji:SELL":(55.6,94.4,9.2),
    "USDMXN:Sun:Marubozu:BUY":(50.0,92.9,6.2),"USDMXN:Sun:LongWick:SELL":(57.6,87.9,9.2),
    "USDMXN:Sun:PinBar:SELL":(55.0,85.0,3.4),"USDMXN:Sun:Harami:BUY":(58.3,83.3,7.8),
    "USDMXN:Sun:InsideBody:BUY":(50.0,81.3,4.0),"USDCOP:Sun:Engulfing:SELL":(58.3,91.7,5.0),
    "USDCOP:Sun:BigBodyRev:SELL":(59.5,86.5,8.6),"USDCOP:Sun:Marubozu:SELL":(66.7,86.7,3.8),
    "USDZAR:Sun:Tweezer:SELL":(68.2,86.4,5.4),"USDZAR:Sun:InsideBar:BUY":(60.0,85.0,3.6),
    "USDZAR:Sun:PinBar:SELL":(47.1,82.4,9.8),"USDARS:Sun:GapRev:BUY":(60.6,90.9,13.0),
    "USDARS:Sun:Engulfing:BUY":(52.4,90.5,7.6),"USDARS:Sun:Marubozu:BUY":(55.0,85.0,3.4),
    "USDBDT:Sun:Doji:BUY":(55.6,83.3,10.8),"USDDZD:Sun:PinBar:SELL":(71.4,85.7,3.2),
    "USDEGP:Sun:Tweezer:SELL":(71.4,85.7,3.2),"USDEGP:Sun:Marubozu:BUY":(40.0,86.7,3.0),
    "USDEGP:Sun:BigBodyRev:SELL":(51.4,82.9,20.6),"BRLUSD:Wed:ShootStar:SELL":(50.0,85.0,3.2),
    "USDINR:Mon:PinBar:BUY":(66.7,100.0,11.0),"USDZAR:Mon:Doji:BUY":(75.0,100.0,9.0),
    "USDEGP:Mon:InsideBar:SELL":(75.0,93.8,8.4),"USDMXN:Mon:Marubozu:SELL":(73.3,93.3,7.6),
    "USDCOP:Mon:Star:BUY":(70.6,94.1,9.0),"USDARS:Mon:Star:BUY":(80.0,93.3,7.8),
    "USDARS:Mon:Harami:SELL":(30.0,90.0,3.0),"USDINR:Mon:Tweezer:BUY":(60.0,86.7,3.6),
    "BRLUSD:Mon:Engulfing:SELL":(66.7,91.7,5.2),"BRLUSD:Mon:PinBar:BUY":(68.4,89.5,6.8),
    "BRLUSD:Mon:LongWick:BUY":(57.7,88.5,7.8),"BRLUSD:Mon:Hammer:BUY":(64.3,85.7,3.0),
    "BRLUSD:Mon:Harami:BUY":(38.5,84.6,8.0),"USDDZD:Mon:Tweezer:BUY":(69.2,92.3,6.0),
    "USDDZD:Mon:InsideBar:BUY":(50.0,89.3,8.8),"USDDZD:Mon:LongWick:BUY":(56.7,83.3,19.4),
    "USDPHP:Mon:Marubozu:SELL":(46.2,92.3,5.4),"USDPHP:Mon:Star:BUY":(71.4,85.7,3.2),
    "USDPHP:Mon:PinBar:BUY":(43.8,81.3,9.0),"USDNGN:Mon:InsideBar:BUY":(59.3,88.9,8.6),
    "USDNGN:Mon:InsideBody:BUY":(60.0,85.0,3.6),"USDEGP:Mon:Star:BUY":(56.3,87.5,4.2),
    "USDINR:Tue:PinBar:BUY":(60.0,95.0,10.8),"USDINR:Tue:ShootStar:SELL":(20.0,90.0,2.8),
    "USDINR:Tue:Marubozu:SELL":(50.0,90.0,3.4),"USDNGN:Tue:Engulfing:BUY":(58.3,91.7,5.0),
    "USDNGN:Tue:InsideBar:SELL":(63.2,89.5,6.6),"USDNGN:Tue:LongWick:SELL":(57.7,88.5,7.8),
    "USDNGN:Tue:BigBodyRev:SELL":(57.1,82.9,5.8),"USDNGN:Tue:Tweezer:BUY":(59.5,85.7,8.6),
    "USDARS:Tue:PinBar:SELL":(71.4,85.7,3.2),"USDARS:Tue:GapRev:BUY":(60.0,85.7,7.2),
    "USDARS:Tue:LongWick:SELL":(65.4,84.6,1.4),"USDPKR:Tue:InsideBody:BUY":(69.4,91.7,15.8),
    "USDPKR:Tue:GapRev:BUY":(53.7,87.8,11.0),"USDPKR:Tue:Star:BUY":(51.6,83.9,18.2),
    "USDPKR:Tue:Harami:SELL":(54.5,81.8,7.0),"USDIDR:Tue:Engulfing:SELL":(56.3,87.5,4.2),
    "USDIDR:Tue:PinBar:SELL":(39.1,87.0,4.8),"USDIDR:Tue:ShootStar:SELL":(10.0,90.0,2.8),
    "USDIDR:Tue:Doji:SELL":(42.9,82.1,15.6),"USDIDR:Tue:Tweezer:SELL":(65.6,87.5,9.0),
    "USDIDR:Tue:InsideBar:BUY":(53.3,83.3,4.0),"USDIDR:Tue:BigBodyRev:BUY":(46.3,82.9,24.8),
    "USDZAR:Tue:Hammer:SELL":(58.3,91.7,5.0),"USDZAR:Tue:Doji:SELL":(65.0,85.0,3.8),
    "USDZAR:Tue:Marubozu:BUY":(52.4,85.7,4.0),"USDMXN:Tue:Doji:SELL":(53.3,86.7,3.4),
    "USDCOP:Tue:3Soldiers:BUY":(60.9,85.5,13.8),"USDCOP:Tue:Consec2:BUY":(57.9,81.7,33.0),
    "BRLUSD:Fri:Engulfing:BUY":(51.9,85.2,4.6),
    "USDPHP:Wed:Harami:SELL":(56.3,93.8,7.8),"USDPHP:Wed:InsideBar:SELL":(48.1,86.5,11.0),
    "USDNGN:Wed:Harami:BUY":(62.5,87.5,4.4),"USDNGN:Wed:InsideBar:BUY":(51.1,87.2,11.4),
    "USDNGN:Wed:Tweezer:BUY":(59.5,85.7,8.6),"USDARS:Wed:Star:SELL":(69.2,87.2,10.8),
    "USDDZD:Wed:PinBar:SELL":(54.8,90.3,11.2),"USDDZD:Wed:ShootStar:SELL":(58.8,88.2,5.0),
    "USDDZD:Wed:LongWick:SELL":(54.4,84.2,4.0),"USDDZD:Tue:TrendCont:BUY":(63.6,85.5,11.2),
    "USDMXN:Wed:ShootStar:SELL":(54.5,86.4,4.8),"USDMXN:Wed:Harami:BUY":(63.6,86.4,5.2),
    "USDZAR:Wed:Harami:BUY":(60.9,82.6,14.2),
    "USDINR:Thu:ShootStar:SELL":(72.2,94.4,9.8),"USDINR:Thu:BigBodyRev:SELL":(60.0,86.2,12.0),
    "USDINR:Thu:Harami:BUY":(47.1,82.4,9.8),"USDZAR:Thu:Harami:BUY":(50.0,94.4,9.0),
    "USDZAR:Thu:GapRev:SELL":(44.9,84.1,26.4),"USDARS:Thu:InsideBar:BUY":(63.6,88.6,14.0),
    "USDARS:Thu:Harami:BUY":(58.8,88.2,5.0),"USDARS:Thu:Marubozu:SELL":(52.2,87.0,5.4),
    "USDARS:Thu:Tweezer:BUY":(51.9,85.2,4.6),"USDDZD:Thu:Hammer:BUY":(68.2,81.8,13.8),
    "USDEGP:Thu:Marubozu:BUY":(60.9,87.0,5.8),"USDPHP:Thu:Hammer:SELL":(50.0,90.0,3.4),
    "USDBDT:Thu:Marubozu:SELL":(48.3,86.2,5.8),"USDBDT:Thu:BigBodyRev:SELL":(47.5,85.2,10.0),
    "USDBDT:Thu:PinBar:BUY":(59.6,83.0,0.2),
    "USDCOP:Fri:ShootStar:SELL":(52.4,95.2,11.2),"USDINR:Fri:Engulfing:BUY":(71.4,89.3,10.0),
    "USDMXN:Fri:Marubozu:SELL":(54.2,91.7,9.8),"USDMXN:Fri:PinBar:BUY":(68.8,90.6,12.8),
    "USDMXN:Fri:Star:SELL":(57.6,81.8,5.2),"USDMXN:Fri:Tweezer:SELL":(57.1,82.1,2.0),
    "USDNGN:Fri:Hammer:BUY":(64.7,88.2,5.2),"USDNGN:Fri:InsideBar:BUY":(52.1,85.4,8.6),
    "USDNGN:Fri:Tweezer:SELL":(64.5,87.1,8.2),"USDEGP:Fri:Marubozu:BUY":(54.5,87.9,9.0),
    "USDIDR:Fri:ShootStar:SELL":(56.3,87.5,4.2),"USDIDR:Fri:PinBar:SELL":(45.5,81.8,4.4),
    "USDCOP:Fri:Star:BUY":(55.3,81.6,7.4),"BRLUSD:Fri:Tweezer:SELL":(69.0,86.2,7.0),
    "USDDZD:Fri:Hammer:SELL":(35.0,85.0,2.6),"USDPHP:Fri:Harami:BUY":(59.1,86.4,5.0),
    "USDDZD:Sat:Marubozu:SELL":(66.7,100.0,8.8),"USDINR:Sat:Tweezer:SELL":(76.9,100.0,9.8),
    "USDPKR:Sat:PinBar:BUY":(52.2,95.7,12.6),"USDBDT:Sat:PinBar:BUY":(53.3,93.3,7.0),
    "USDZAR:Sat:Star:BUY":(46.7,93.3,6.8),"USDDZD:Sat:Star:SELL":(42.9,92.9,6.0),
    "USDINR:Sat:Star:SELL":(64.3,92.9,13.2),"USDNGN:Sat:Star:BUY":(73.3,86.7,4.0),
    "USDNGN:Sat:GapRev:SELL":(56.7,86.7,7.0),"USDPHP:Sat:Hammer:SELL":(50.0,91.7,4.8),
    "USDPHP:Sat:Tweezer:BUY":(58.3,91.7,5.0),"USDPHP:Sat:PinBar:BUY":(45.5,90.9,4.0),
    "USDPKR:Sat:InsideBody:BUY":(63.6,90.9,8.8),"USDPKR:Sat:Star:BUY":(63.2,89.5,6.6),
    "USDPKR:Sat:LongWick:BUY":(52.9,82.4,4.8),"USDPKR:Sat:Engulfing:BUY":(66.7,88.9,6.0),
    "USDDZD:Sat:PinBar:SELL":(50.0,87.5,4.0),"USDDZD:Sat:Tweezer:BUY":(50.0,87.5,4.0),
    "USDDZD:Sat:LongWick:SELL":(56.5,87.0,5.6),"USDDZD:Sat:Engulfing:BUY":(53.8,84.6,7.6),
    "USDDZD:Sat:TrendCont:SELL":(60.0,86.0,10.8),"USDBDT:Sat:LongWick:BUY":(48.1,88.9,8.0),
    "USDIDR:Sat:InsideBar:BUY":(50.0,88.9,5.4),"USDIDR:Sat:3Soldiers:SELL":(63.0,81.5,19.2),
    "USDIDR:Sat:TrendCont:BUY":(52.2,87.0,10.8),"USDARS:Sat:Hammer:BUY":(70.0,90.0,3.8),
    "USDARS:Sat:LongWick:BUY":(61.3,87.1,8.0),"USDARS:Sat:InsideBody:BUY":(52.2,87.0,5.4),
    "USDARS:Sat:BigBodyRev:SELL":(65.2,87.0,6.0),"USDCOP:Sat:Marubozu:BUY":(54.5,86.4,4.8),
    "USDCOP:Sat:Tweezer:SELL":(58.6,86.2,6.4),"USDCOP:Sat:GapRev:BUY":(53.3,82.2,11.8),
    "USDMXN:Sat:BigBodyRev:SELL":(40.7,81.5,0.4),"USDMXN:Sat:Engulfing:BUY":(58.8,88.2,5.0),
    "USDZAR:Sat:Doji:BUY":(45.5,81.8,6.8),"USDZAR:Sat:Engulfing:BUY":(50.0,87.5,4.0),
    "USDEGP:Mon:InsideBar:SELL":(75.0,93.8,8.4),
}

# ============================================================================
# PATTERN DETECTION (18 patterns — compact)
# ============================================================================
def _p(c, fn):
    s=[]
    for i in range(max(1, fn.get('start',1)), min(len(c)-1, fn.get('end', len(c)-1))):
        pass
    return s

def detect_doji(c):
    s=[]
    for i in range(1,len(c)-1):
        p,x=c[i-1],c[i];r=x['high']-x['low'];b=abs(x['close']-x['open'])
        if r>0 and b/r<=0.1:
            if p['close']<p['open']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'Doji'})
            elif p['close']>p['open']:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'Doji'})
    return s
def detect_hammer(c):
    s=[]
    for i in range(1,len(c)-1):
        p,x=c[i-1],c[i];r=x['high']-x['low'];b=abs(x['close']-x['open'])
        lw=min(x['open'],x['close'])-x['low'];uw=x['high']-max(x['open'],x['close'])
        if r>0 and b/r<=0.3 and lw/r>=0.6 and uw/r<=0.15:
            if p['close']<p['open']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'Hammer'})
            elif p['close']>p['open']:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'Hammer'})
    return s
def detect_shooting_star(c):
    s=[]
    for i in range(1,len(c)-1):
        p,x=c[i-1],c[i]
        if p['close']<=p['open']:continue
        r=x['high']-x['low'];b=abs(x['close']-x['open'])
        uw=x['high']-max(x['open'],x['close']);lw=min(x['open'],x['close'])-x['low']
        if r>0 and b/r<=0.3 and uw/r>=0.6 and lw/r<=0.15:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'ShootStar'})
    return s
def detect_star(c):
    s=[]
    for i in range(2,len(c)-1):
        c1,c2,c3=c[i-2],c[i-1],c[i]
        if c1['close']<c1['open'] and abs(c2['close']-c2['open'])<abs(c1['close']-c1['open'])*0.5 and c3['close']>c3['open'] and c3['close']>(c1['open']+c1['close'])/2:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'Star'})
        if c1['close']>c1['open'] and abs(c2['close']-c2['open'])<abs(c1['close']-c1['open'])*0.5 and c3['close']<c3['open'] and c3['close']<(c1['open']+c1['close'])/2:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'Star'})
    return s
def detect_three_soldiers(c):
    s=[]
    for i in range(2,len(c)-1):
        c1,c2,c3=c[i-2],c[i-1],c[i]
        if c1['close']>c1['open'] and c2['close']>c2['open'] and c3['close']>c3['open'] and c2['close']>c1['close'] and c3['close']>c2['close']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'3Soldiers'})
        if c1['close']<c1['open'] and c2['close']<c2['open'] and c3['close']<c3['open'] and c2['close']<c1['close'] and c3['close']<c2['close']:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'3Soldiers'})
    return s
def detect_harami(c):
    s=[]
    for i in range(1,len(c)-1):
        p,x=c[i-1],c[i];pb=abs(p['close']-p['open']);cb=abs(x['close']-x['open'])
        if cb<pb*0.6 and x['high']<=p['high'] and x['low']>=p['low']:
            if p['close']<p['open'] and x['close']>x['open']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'Harami'})
            if p['close']>p['open'] and x['close']<x['open']:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'Harami'})
    return s
def detect_piercing(c):
    s=[]
    for i in range(1,len(c)-1):
        p,x=c[i-1],c[i]
        if p['close']<p['open'] and x['open']<p['low'] and x['close']>(p['open']+p['close'])/2 and x['close']>x['open']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'Piercing'})
        if p['close']>p['open'] and x['open']>p['high'] and x['close']<(p['open']+p['close'])/2 and x['close']<x['open']:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'Piercing'})
    return s
def detect_tweezer(c):
    s=[]
    for i in range(1,len(c)-1):
        p,x=c[i-1],c[i];r=x['high']-x['low']
        if r>0:
            if abs(x['low']-p['low'])<r*0.05 and p['close']<p['open'] and x['close']>x['open']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'Tweezer'})
            if abs(x['high']-p['high'])<r*0.05 and p['close']>p['open'] and x['close']<x['open']:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'Tweezer'})
    return s
def detect_marubozu(c):
    s=[]
    for i in range(len(c)-1):
        x=c[i];r=x['high']-x['low'];b=abs(x['close']-x['open'])
        if r>0 and b/r>=0.92:
            if x['close']>x['open']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'Marubozu'})
            else:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'Marubozu'})
    return s
def detect_inside_bar(c):
    s=[]
    for i in range(1,len(c)-1):
        m,ins=c[i-1],c[i]
        if ins['high']<=m['high'] and ins['low']>=m['low']:
            if ins['close']>ins['open']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'InsideBar'})
            elif ins['close']<ins['open']:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'InsideBar'})
    return s
def detect_pin_bar(c):
    s=[]
    for i in range(1,len(c)-1):
        p,x=c[i-1],c[i];r=x['high']-x['low']
        if r<=0:continue
        b=abs(x['close']-x['open']);uw=x['high']-max(x['open'],x['close']);lw=min(x['open'],x['close'])-x['low']
        if lw/r>=0.6 and b/r<=0.35 and p['close']<p['open']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'PinBar'})
        if uw/r>=0.6 and b/r<=0.35 and p['close']>p['open']:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'PinBar'})
    return s
def detect_engulfing(c):
    s=[]
    for i in range(1,len(c)-1):
        p,x=c[i-1],c[i]
        if x['high']>p['high'] and x['low']<p['low'] and x['close']>x['open'] and p['close']<p['open']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'Engulfing'})
        if x['high']>p['high'] and x['low']<p['low'] and x['close']<x['open'] and p['close']>p['open']:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'Engulfing'})
    return s
def detect_trend_cont(c):
    s=[]
    for i in range(3,len(c)-1):
        c1,c2,c3,c4=c[i-3],c[i-2],c[i-1],c[i]
        if c2['high']>c1['high'] and c3['high']>c2['high'] and c4['high']>c3['high'] and c2['low']>c1['low'] and c3['low']>c2['low'] and c4['low']>c3['low']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'TrendCont'})
        if c2['high']<c1['high'] and c3['high']<c2['high'] and c4['high']<c3['high'] and c2['low']<c1['low'] and c3['low']<c2['low'] and c4['low']<c3['low']:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'TrendCont'})
    return s
def detect_inside_body(c):
    s=[]
    for i in range(1,len(c)-1):
        p,x=c[i-1],c[i];pbh=max(p['open'],p['close']);pbl=min(p['open'],p['close'])
        if x['close']<pbh and x['close']>pbl and abs(x['close']-x['open'])<abs(p['close']-p['open'])*0.5:
            if p['close']>p['open'] and x['close']<x['open']:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'InsideBody'})
            elif p['close']<p['open'] and x['close']>x['open']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'InsideBody'})
    return s
def detect_gap_rev(c):
    s=[]
    for i in range(1,len(c)-1):
        p,x=c[i-1],c[i]
        if x['open']>p['close'] and x['close']<p['close']:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'GapRev'})
        if x['open']<p['close'] and x['close']>p['close']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'GapRev'})
    return s
def detect_consec(c):
    s=[]
    for i in range(1,len(c)-1):
        p,x=c[i-1],c[i]
        if p['close']>p['open'] and x['close']>x['open']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'Consec2'})
        if p['close']<p['open'] and x['close']<x['open']:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'Consec2'})
    return s
def detect_long_wick(c):
    s=[]
    for i in range(1,len(c)-1):
        p,x=c[i-1],c[i];r=x['high']-x['low']
        if r<=0:continue
        b=abs(x['close']-x['open']);uw=x['high']-max(x['open'],x['close']);lw=min(x['open'],x['close'])-x['low']
        if lw/r>=0.5 and b/r<=0.4 and p['close']<p['open']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'LongWick'})
        if uw/r>=0.5 and b/r<=0.4 and p['close']>p['open']:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'LongWick'})
    return s
def detect_big_body_rev(c):
    s=[]
    ab=sum(abs(x['close']-x['open']) for x in c)/len(c) if c else 0
    for i in range(1,len(c)-1):
        p,x=c[i-1],c[i];b=abs(x['close']-x['open'])
        if b>=ab*1.3:
            if p['close']<p['open'] and x['close']>x['open']:s.append({'entry_idx':i+1,'direction':'BUY','pattern':'BigBodyRev'})
            if p['close']>p['open'] and x['close']<x['open']:s.append({'entry_idx':i+1,'direction':'SELL','pattern':'BigBodyRev'})
    return s

PATTERN_DETECTORS = {
    'Doji':detect_doji,'Hammer':detect_hammer,'ShootStar':detect_shooting_star,
    'Star':detect_star,'3Soldiers':detect_three_soldiers,'Harami':detect_harami,
    'Piercing':detect_piercing,'Tweezer':detect_tweezer,'Marubozu':detect_marubozu,
    'InsideBar':detect_inside_bar,'PinBar':detect_pin_bar,'Engulfing':detect_engulfing,
    'TrendCont':detect_trend_cont,'InsideBody':detect_inside_body,'GapRev':detect_gap_rev,
    'Consec2':detect_consec,'LongWick':detect_long_wick,'BigBodyRev':detect_big_body_rev,
}
WEEKDAY_NAMES = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']
WEEKDAY_FULL = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']

# ============================================================================
# UTILITY
# ============================================================================
def load_candles(filepath):
    with open(filepath, 'r') as f: data = json.load(f)
    candles = data if isinstance(data, list) else data.get('candles', data)
    return sorted([{'time':int(c['time']),'datetime':c.get('datetime',''),'open':float(c['open']),'high':float(c['high']),'low':float(c['low']),'close':float(c['close'])} for c in candles], key=lambda c: c['time'])

def get_pair_name(filepath):
    return os.path.splitext(os.path.basename(filepath))[0].split('_')[0]

def generate_signals(candles, pair_name):
    all_signals = []
    for pattern_name, detector in PATTERN_DETECTORS.items():
        for sig in detector(candles):
            entry_idx = sig['entry_idx']
            if entry_idx >= len(candles): continue
            entry_candle = candles[entry_idx]
            dt = datetime.fromtimestamp(entry_candle['time'], tz=timezone.utc)
            our_weekday = (dt.weekday() + 1) % 7
            day_name = WEEKDAY_NAMES[our_weekday]
            key = f"{pair_name}:{day_name}:{pattern_name}:{sig['direction']}"
            if key in ELITE_PATTERNS:
                c1, c12, profit = ELITE_PATTERNS[key]
                all_signals.append({'timestamp':entry_candle['time'],'pair':pair_name,'pattern':pattern_name,'direction':sig['direction'],'weekday':day_name,'weekday_full':WEEKDAY_FULL[our_weekday],'c1_rate':c1,'c12_rate':c12,'net_profit':profit})
    return all_signals

def parse_time_range(time_str):
    if not time_str: return None, None
    parts = time_str.split('-')
    if len(parts) != 2: return None, None
    def parse_hm(hm):
        h, m = hm.split(':'); return int(h) * 60 + int(m)
    return parse_hm(parts[0].strip()), parse_hm(parts[1].strip())

def time_in_range(minutes, start, end):
    if start is None: return True
    if start <= end: return start <= minutes <= end
    return minutes >= start or minutes <= end

def load_sent_cache():
    if not os.path.exists(SENT_CACHE): return set()
    try:
        with open(SENT_CACHE, 'r') as f: return set(json.load(f))
    except: return set()

def save_sent_cache(cache):
    try:
        with open(SENT_CACHE, 'w') as f: json.dump(list(cache), f)
    except: pass

def detect_current_day(tz_offset):
    """Detect current weekday using system time + tz offset."""
    now = datetime.now(timezone.utc) + timedelta(hours=tz_offset)
    our_weekday = (now.weekday() + 1) % 7  # Sun=0..Sat=6
    return our_weekday, WEEKDAY_NAMES[our_weekday], WEEKDAY_FULL[our_weekday]

# ============================================================================
# CORE: Extract signals (shared by CLI and interactive modes)
# ============================================================================
def extract_signals(day_str, direction, time_range, gap, tz_offset, use_cache=True, detailed=False):
    """Extract filtered signals. Returns (signals_list, stats_dict)."""
    day_map = {WEEKDAY_NAMES[i].lower(): i for i in range(7)}
    day_map.update({WEEKDAY_FULL[i].lower(): i for i in range(7)})
    
    if day_str.lower() == 'all' or day_str.lower() == 'auto':
        days_to_process = list(range(7))
    else:
        if day_str.lower() not in day_map:
            return [], {'error': f'Unknown day: {day_str}'}
        days_to_process = [day_map[day_str.lower()]]
    
    dir_lower = direction.lower()
    if dir_lower not in ('call', 'put', 'both'):
        return [], {'error': f'Invalid direction: {direction}'}
    
    start_min, end_min = parse_time_range(time_range) if time_range else (None, None)
    sent_cache = load_sent_cache() if use_cache else set()
    
    # Load raw signals
    all_signals = []
    for day_idx in days_to_process:
        raw_file = os.path.join(RAW_DIR, f'{WEEKDAY_NAMES[day_idx]}_signals.json')
        if not os.path.exists(raw_file): continue
        with open(raw_file, 'r') as f:
            all_signals.extend(json.load(f))
    
    if not all_signals:
        return [], {'error': 'No scan data found. Run: python fqv3.py scan *.json'}
    
    # Direction filter
    if dir_lower == 'call':
        all_signals = [s for s in all_signals if s['direction'] == 'BUY']
    elif dir_lower == 'put':
        all_signals = [s for s in all_signals if s['direction'] == 'SELL']
    
    # Time filter
    if start_min is not None:
        filtered = []
        for s in all_signals:
            dt_local = datetime.fromtimestamp(s['timestamp'], tz=timezone.utc) + timedelta(hours=tz_offset)
            local_min = dt_local.hour * 60 + dt_local.minute
            if time_in_range(local_min, start_min, end_min):
                filtered.append(s)
        all_signals = filtered
    
    # Cache filter
    new_signals = [s for s in all_signals if f"{s['timestamp']}_{s['pair']}_{s['pattern']}_{s['direction']}" not in sent_cache]
    
    # Sort
    new_signals.sort(key=lambda s: s['timestamp'])
    
    # Dedup same minute (keep highest C1+C2)
    by_minute = {}
    for s in new_signals:
        mk = s['timestamp'] // 60
        if mk not in by_minute or s['c12_rate'] > by_minute[mk]['c12_rate']:
            by_minute[mk] = s
    unique = sorted(by_minute.values(), key=lambda s: s['timestamp'])
    
    # Gap filter
    final = []
    last_ts = None
    for s in unique:
        if last_ts is None or (s['timestamp'] - last_ts) / 60 >= gap:
            final.append(s)
            last_ts = s['timestamp']
    
    # Update cache
    if use_cache:
        for s in final:
            sent_cache.add(f"{s['timestamp']}_{s['pair']}_{s['pattern']}_{s['direction']}")
        save_sent_cache(sent_cache)
    
    stats = {
        'total_raw': len(all_signals) + (len(all_signals) - len(new_signals)),
        'after_direction': len(all_signals),
        'after_cache': len(new_signals),
        'after_dedup': len(unique),
        'after_gap': len(final),
        'days': [WEEKDAY_FULL[d] for d in days_to_process],
        'direction': dir_lower,
        'time_range': time_range or 'all day',
        'gap': gap,
        'tz_offset': tz_offset,
        'cache_used': use_cache,
        'cache_total': len(sent_cache),
    }
    return final, stats

def format_output(signals, stats, detailed=False):
    """Format signals as Telegram-style list."""
    if not signals:
        return "\n  ⚠ No signals match your criteria.\n"
    
    tz = stats['tz_offset']
    tz_label = f"UTC+{tz}" if tz >= 0 else f"UTC{tz}"
    
    lines = []
    lines.append('')
    lines.append('━' * 7 + ' • ' + '━' * 7)
    
    for s in signals:
        dt_local = datetime.fromtimestamp(s['timestamp'], tz=timezone.utc) + timedelta(hours=tz)
        time_str = dt_local.strftime('%H:%M')
        pair_str = f"{s['pair']}-OTC"
        direction = "CALL" if s['direction'] == 'BUY' else "PUT"
        lines.append(f'M1 {pair_str} {time_str} {direction}')
    
    lines.append('━' * 7 + ' • ' + '━' * 7)
    
    call_count = sum(1 for s in signals if s['direction'] == 'BUY')
    put_count = len(signals) - call_count
    lines.append(f'\n  Total: {len(signals)} signals | CALL={call_count} | PUT={put_count}')
    lines.append(f'  Day: {", ".join(stats["days"])}')
    if stats['time_range'] != 'all day':
        lines.append(f'  Time: {stats["time_range"]} ({tz_label})')
    lines.append(f'  Gap: {stats["gap"]} min | Timezone: {tz_label}')
    lines.append(f'  Strategy: Entry 1 → MTG1 → STOP | Max loss: 3× stake')
    
    if detailed:
        lines.append(f'\n{"="*100}')
        lines.append(f'  Detailed Report')
        lines.append(f'{"="*100}')
        lines.append(f'\n  {"#":<4} {"Time":<6} {"Pair":<9} {"Pattern":<12} {"Dir":<5} {"C1":>7} {"C1+C2":>8} {"Profit":>8}')
        lines.append(f'  {"-"*80}')
        for i, s in enumerate(signals, 1):
            dt_local = datetime.fromtimestamp(s['timestamp'], tz=timezone.utc) + timedelta(hours=tz)
            d = "CALL" if s['direction'] == 'BUY' else "PUT"
            lines.append(f'  {i:<4} {dt_local.strftime("%H:%M"):<6} {s["pair"]:<9} {s["pattern"]:<12} {d:<5} {s["c1_rate"]:>6.1f}% {s["c12_rate"]:>7.1f}% {s["net_profit"]:>7.1f}×')
    
    # Per pair
    pair_counts = defaultdict(int)
    for s in signals: pair_counts[s['pair']] += 1
    lines.append(f'\n  Per pair:')
    for pair, count in sorted(pair_counts.items(), key=lambda x: -x[1]):
        lines.append(f'    {pair:<9}: {count} signals')
    
    return '\n'.join(lines)

# ============================================================================
# INTERACTIVE MODE (Telegram-ready)
# ============================================================================
def interactive_mode():
    """Interactive menu system — ready for Telegram bot integration."""
    
    print()
    print('=' * 60)
    print('  FutureQuantVexa v3.1 — Interactive Mode')
    print('  (Telegram Bot Ready)')
    print('=' * 60)
    
    # Check if scan data exists
    if not os.path.exists(RAW_DIR) or not os.listdir(RAW_DIR):
        print('\n  ⚠ No scan data found!')
        print('  Run first: python fqv3.py scan *.json')
        return
    
    # Step 1: Timezone
    print('\n📋 Step 1: Select your timezone')
    print('  [1] UTC+0 (London)')
    print('  [2] UTC+1 (Algeria, Tunisia)')
    print('  [3] UTC+2 (Egypt, South Africa)')
    print('  [4] UTC+3 (Moscow, Saudi)')
    print('  [5] UTC-5 (New York)')
    print('  [6] Custom (enter manually)')
    
    tz_map = {'1': 0, '2': 1, '3': 2, '4': 3, '5': -5}
    tz_choice = input('\n  Select [1-6] (default 2): ').strip() or '2'
    
    if tz_choice == '6':
        try:
            tz_offset = int(input('  Enter UTC offset (e.g. 1, -5, 3): ').strip())
        except ValueError:
            print('  Invalid input. Using UTC+1.')
            tz_offset = 1
    else:
        tz_offset = tz_map.get(tz_choice, 1)
    
    tz_label = f'UTC+{tz_offset}' if tz_offset >= 0 else f'UTC{tz_offset}'
    
    # Auto-detect current day
    day_idx, day_short, day_full = detect_current_day(tz_offset)
    now_local = datetime.now(timezone.utc) + timedelta(hours=tz_offset)
    current_time = now_local.strftime('%H:%M')
    
    print(f'\n  ✅ Timezone: {tz_label}')
    print(f'  📅 Today: {day_full}')
    print(f'  🕐 Current time: {current_time} ({tz_label})')
    
    # Step 2: Day
    print(f'\n📋 Step 2: Select day')
    print(f'  [0] Today ({day_full}) ← auto-detected')
    for i, (sname, fname) in enumerate(zip(WEEKDAY_NAMES, WEEKDAY_FULL)):
        print(f'  [{i+1}] {fname}')
    print('  [8] All days')
    
    day_choice = input(f'\n  Select [0-8] (default 0 = today): ').strip() or '0'
    
    if day_choice == '0':
        selected_day = day_short
    elif day_choice == '8':
        selected_day = 'all'
    elif day_choice.isdigit() and 1 <= int(day_choice) <= 7:
        selected_day = WEEKDAY_NAMES[int(day_choice) - 1]
    else:
        selected_day = day_short
    
    # Step 3: Direction
    print(f'\n📋 Step 3: Select direction')
    print('  [1] CALL (Buy) 🟢')
    print('  [2] PUT (Sell) 🔴')
    print('  [3] Both 🔵')
    
    dir_choice = input('\n  Select [1-3] (default 3): ').strip() or '3'
    direction_map = {'1': 'call', '2': 'put', '3': 'both'}
    direction = direction_map.get(dir_choice, 'both')
    
    # Step 4: Time range
    print(f'\n📋 Step 4: Select time range ({tz_label})')
    print(f'  [0] All day (00:00 - 23:59)')
    print(f'  [1] Morning (06:00 - 12:00)')
    print(f'  [2] Afternoon (12:00 - 18:00)')
    print(f'  [3] Evening (18:00 - 23:59)')
    print(f'  [4] Night (22:00 - 02:00)')
    print(f'  [5] Late night (23:00 - 00:00)')
    print(f'  [6] Custom (enter manually)')
    
    time_map = {
        '0': None,
        '1': '06:00-12:00',
        '2': '12:00-18:00',
        '3': '18:00-23:59',
        '4': '22:00-02:00',
        '5': '23:00-00:00',
    }
    
    time_choice = input('\n  Select [0-6] (default 0): ').strip() or '0'
    
    if time_choice == '6':
        time_range = input('  Enter time range (HH:MM-HH:MM, e.g. 09:00-12:00): ').strip()
    else:
        time_range = time_map.get(time_choice)
    
    # Step 5: Gap
    print(f'\n📋 Step 5: Select minimum gap between signals')
    print('  [1] 3 minutes')
    print('  [2] 4 minutes (recommended)')
    print('  [3] 5 minutes')
    print('  [4] Custom')
    
    gap_map = {'1': 3, '2': 4, '3': 5}
    gap_choice = input('\n  Select [1-4] (default 2): ').strip() or '2'
    
    if gap_choice == '4':
        try:
            gap = int(input('  Enter gap in minutes: ').strip())
        except ValueError:
            gap = 4
    else:
        gap = gap_map.get(gap_choice, 4)
    
    # Step 6: Cache
    print(f'\n📋 Step 6: Cache (prevent duplicate signals)')
    print('  [1] Enable cache (recommended)')
    print('  [2] Disable cache (show all)')
    
    cache_choice = input('\n  Select [1-2] (default 1): ').strip() or '1'
    use_cache = cache_choice != '2'
    
    # Summary
    print(f'\n{"="*60}')
    print(f'  Summary')
    print(f'{"="*60}')
    print(f'  Timezone:  {tz_label}')
    print(f'  Day:       {selected_day if selected_day != "all" else "All days"}')
    print(f'  Direction: {direction.upper()}')
    print(f'  Time:      {time_range or "All day"}')
    print(f'  Gap:       {gap} min')
    print(f'  Cache:     {"enabled" if use_cache else "disabled"}')
    print(f'{"="*60}')
    
    confirm = input('\n  Generate signals? [Y/n]: ').strip().lower() or 'y'
    if confirm != 'y':
        print('\n  ❌ Cancelled.')
        return
    
    # Extract
    signals, stats = extract_signals(
        day_str=selected_day,
        direction=direction,
        time_range=time_range,
        gap=gap,
        tz_offset=tz_offset,
        use_cache=use_cache,
        detailed=False,
    )
    
    # Output
    output = format_output(signals, stats, detailed=False)
    print(output)
    
    # Save CSV
    if signals:
        csv_file = 'futurequantvexa_signals.csv'
        with open(csv_file, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['time','pair','pattern','direction','weekday','c1_rate','c12_rate','net_profit','timestamp'])
            for s in signals:
                dt_local = datetime.fromtimestamp(s['timestamp'], tz=timezone.utc) + timedelta(hours=tz_offset)
                w.writerow([dt_local.strftime('%H:%M'), s['pair'], s['pattern'],
                            'CALL' if s['direction']=='BUY' else 'PUT', s['weekday'],
                            f"{s['c1_rate']:.1f}%", f"{s['c12_rate']:.1f}%", f"{s['net_profit']:.1f}×",
                            s['timestamp']])
        print(f'\n  ✓ Saved to: {csv_file}')
    
    print(f'\n  {"="*60}')
    print(f'  FutureQuantVexa v3.1 — Complete')
    print(f'  {"="*60}\n')

# ============================================================================
# SCAN COMMAND
# ============================================================================
def cmd_scan(args):
    print(f'\n{"="*60}')
    print('  FutureQuantVexa v3.1 — SCAN')
    print(f'{"="*60}\n')
    
    os.makedirs(RAW_DIR, exist_ok=True)
    files = sorted(args.files)
    print(f'  Scanning {len(files)} file(s)...\n')
    
    all_signals = []
    for filepath in files:
        if not os.path.exists(filepath):
            print(f'  ✗ Not found: {filepath}'); continue
        pair = get_pair_name(filepath)
        try:
            candles = load_candles(filepath)
            signals = generate_signals(candles, pair)
            all_signals.extend(signals)
            print(f'  [{pair:<9}] {len(candles)} candles → {len(signals)} signals')
        except Exception as e:
            print(f'  [{pair:<9}] ERROR: {e}')
    
    by_day = defaultdict(list)
    for s in all_signals:
        dt = datetime.fromtimestamp(s['timestamp'], tz=timezone.utc)
        our_weekday = (dt.weekday() + 1) % 7
        by_day[our_weekday].append(s)
    
    print(f'\n  Saving to: {RAW_DIR}/')
    total = 0
    for day_idx in range(7):
        day_signals = by_day.get(day_idx, [])
        day_signals.sort(key=lambda s: s['timestamp'])
        with open(os.path.join(RAW_DIR, f'{WEEKDAY_NAMES[day_idx]}_signals.json'), 'w') as f:
            json.dump(day_signals, f)
        print(f'    {WEEKDAY_FULL[day_idx]:<10}: {len(day_signals):>5} signals')
        total += len(day_signals)
    
    print(f'\n  ✓ Total: {total} signals stored')
    print(f'  ✓ Run "extract" or "interactive" to filter.\n')

# ============================================================================
# EXTRACT COMMAND (CLI mode)
# ============================================================================
def cmd_extract(args):
    signals, stats = extract_signals(
        day_str=args.day,
        direction=args.dir,
        time_range=args.time,
        gap=args.gap,
        tz_offset=args.tz,
        use_cache=not args.no_cache,
        detailed=args.detailed,
    )
    
    if 'error' in stats:
        print(f'\n  ⚠ {stats["error"]}')
        return
    
    print(format_output(signals, stats, detailed=args.detailed))
    
    if signals:
        csv_file = 'futurequantvexa_signals.csv'
        with open(csv_file, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['time','pair','pattern','direction','weekday','c1_rate','c12_rate','net_profit','timestamp'])
            for s in signals:
                dt_local = datetime.fromtimestamp(s['timestamp'], tz=timezone.utc) + timedelta(hours=args.tz)
                w.writerow([dt_local.strftime('%H:%M'), s['pair'], s['pattern'],
                            'CALL' if s['direction']=='BUY' else 'PUT', s['weekday'],
                            f"{s['c1_rate']:.1f}%", f"{s['c12_rate']:.1f}%", f"{s['net_profit']:.1f}×",
                            s['timestamp']])
        print(f'\n  ✓ Saved to: {csv_file}')
    
    print(f'\n  {"="*60}')
    print(f'  FutureQuantVexa v3.1 — Complete')
    print(f'  {"="*60}\n')

# ============================================================================
# MAIN
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description='FutureQuantVexa v3.1 — Signal Generator (Telegram-ready)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  scan *.json              → Scan candle files and store all signals
  extract [options]        → Extract signals (CLI mode)
  interactive              → Interactive menu (6 steps, Telegram-ready)
  clear-cache              → Clear sent-signal cache

Interactive mode (recommended for Telegram bot):
  python fqv3.py interactive

CLI mode:
  python fqv3.py scan *.json
  python fqv3.py extract --day=Sunday --dir=CALL --time=23:00-00:00 --gap=4 --tz=1
  python fqv3.py extract --day=auto --dir=both --gap=5 --tz=1

  --day=     Sun/Mon/Tue/Wed/Thu/Fri/Sat/all/auto (auto=today)
  --dir=     call/put/both
  --time=    HH:MM-HH:MM (e.g. 09:00-12:00, 23:00-00:00)
  --gap=     N minutes (3/4/5/etc)
  --tz=      UTC offset (0/1/2/-5/etc)
  --detailed Show pattern info
  --no-cache Disable cache
""")
    
    subparsers = parser.add_subparsers(dest='command')
    
    # SCAN
    sp = subparsers.add_parser('scan', help='Scan candle files')
    sp.add_argument('files', nargs='+', help='JSON files')
    
    # EXTRACT
    ep = subparsers.add_parser('extract', help='Extract filtered signals')
    ep.add_argument('--day', default='auto', help='Day (default: auto=today)')
    ep.add_argument('--dir', default='both', help='call/put/both')
    ep.add_argument('--time', default=None, help='HH:MM-HH:MM')
    ep.add_argument('--gap', type=int, default=4, help='Min gap (default: 4)')
    ep.add_argument('--tz', type=int, default=1, help='UTC offset (default: 1)')
    ep.add_argument('--no-cache', action='store_true', help='Disable cache')
    ep.add_argument('--detailed', action='store_true', help='Show details')
    
    # INTERACTIVE
    subparsers.add_parser('interactive', help='Interactive menu mode')
    
    # CLEAR-CACHE
    subparsers.add_parser('clear-cache', help='Clear sent cache')
    
    args = parser.parse_args()
    
    if args.command == 'scan':
        cmd_scan(args)
    elif args.command == 'extract':
        cmd_extract(args)
    elif args.command == 'interactive':
        interactive_mode()
    elif args.command == 'clear-cache':
        if os.path.exists(SENT_CACHE):
            os.remove(SENT_CACHE)
            print('  ✓ Cache cleared.')
        else:
            print('  Cache already empty.')
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
