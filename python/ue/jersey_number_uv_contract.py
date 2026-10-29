"""旧UE导入路径兼容入口；号码算法与参数统一放在共享纯Python模块。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from grf_ue_bridge.number_uv_contract import *
