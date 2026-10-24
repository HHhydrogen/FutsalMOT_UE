"""只提取显式绑定的既有数值函数，不执行旧Trainer顶层布局/旧准入。"""
import ast
from collections import Counter,OrderedDict
from copy import copy,deepcopy
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

def numeric_helpers(bundle):
    bundle=Path(bundle);folder=bundle/'experiments/sim2real';identities=[]
    common=dict(Counter=Counter,OrderedDict=OrderedDict,copy=copy,deepcopy=deepcopy,csv=csv,hashlib=hashlib,json=json,
        os=os,Path=Path,random=random,signal=signal,subprocess=subprocess,sys=sys,time=time)
    def extract(filename,names,namespace):
        path=folder/filename;source=path.read_text(encoding='utf-8-sig');tree=ast.parse(source)
        selected=[]
        for name in names:
            matches=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name==name]
            if len(matches)!=1:raise ValueError('数值函数白名单缺失/重复:'+name)
            node=matches[0];selected.append(node)
            identities.append(dict(source=str(path),symbol=name,source_segment_sha256=hashlib.sha256(ast.get_source_segment(source,node).encode()).hexdigest()))
        exec(compile(ast.Module(body=selected,type_ignores=[]),str(path),'exec'),namespace)
    base=dict(common)
    extract('train_pose_location_control.py',['require','sha','read','rows','canonical','bound_file','editor_running','CachedDataset','state_hash','source_key'],base)
    retry=dict(common,DELAYS=(.05,.1,.2,.4,.8))
    extract('run_pose_location_control_windows.py',['retry_replace'],retry)
    v3=dict(common,require=base['require'],canonical=base['canonical'],RETRY=SimpleNamespace(**retry))
    extract('train_pose_location_poseonly_v3.py',['replace_owned','atomic_json','append_exposure','model_copy','update_ema_preserve_frozen'],v3)
    prior_tree=ast.parse((folder/'train_pose_location_poseonly_v3.py').read_text(encoding='utf-8-sig'))
    policy_node=next(n for n in prior_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='POLICY' for t in n.targets))
    exec(compile(ast.Module(body=[policy_node],type_ignores=[]),'v3_policy','exec'),v3)
    numeric=dict(common,BASE=SimpleNamespace(**base),V3=SimpleNamespace(**v3),require=base['require'],canonical=base['canonical'],
        rows=base['rows'],read=base['read'],atomic_json=v3['atomic_json'],append_exposure=v3['append_exposure'],SCHEMA='futsalmot_longpair_location_checkpoint_v5')
    tree=ast.parse((folder/'train_pose_location_separate_v4.py').read_text(encoding='utf-8-sig'))
    constants=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('NORMALIZATION','POLICY') for t in n.targets)]
    exec(compile(ast.Module(body=constants,type_ignores=[]),'v4_numeric_policy','exec'),numeric)
    extract('train_pose_location_separate_v4.py',['save_last','reconcile_resume','train_loop'],numeric)
    return SimpleNamespace(**numeric),identities
