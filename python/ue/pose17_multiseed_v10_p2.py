"""v10显式scope入口；沿用真实绿色/native事务，不重定义采样数值。"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python/ue'))
from pose17_green_kit_p2 import main

if __name__=='__main__':main(ROOT/'Saved/AppearancePlanning/multiseed_v10_a01')
