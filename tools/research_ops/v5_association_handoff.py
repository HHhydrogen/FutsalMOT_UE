"""等待既有v5真完成/进程退出后唯一交接；不导入模型，不在训练期间推理。"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from v5_association_runtime import read,sha,require,bound,training_complete
from v5_association_driver import atomic,PYTHON

def assert_static(config,config_sha,path):
    require(sha(path)==config_sha,'已启用config改变，停止保留')
    for entry in config['handoff_frozen_inputs']:bound(entry)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    config=read(args.config);identity=sha(args.config);require(config.get('execution_authorized') is True and config.get('approved_by')=='root','root尚未启用交接')
    assert_static(config,identity,args.config)
    if not args.execute:print(json.dumps(dict(status='readonly_handoff_bindings_valid_no_launch')));return
    root=Path(config['handoff_root']);require(not root.exists(),'已有交接/partial，拒绝重复启动');root.mkdir(parents=True)
    with (root/'driver.lock').open('x',encoding='utf-8') as stream:stream.write(json.dumps(dict(pid=os.getpid(),source_sha256=sha(__file__))))
    state=dict(schema='v5_association_handoff_state_v1',status='waiting_existing_ninearm_training',pid=os.getpid(),config_sha256=identity,source_sha256=sha(__file__),started_unix=time.time())
    path=root/'state.json';atomic(path,state)
    try:
        while True:
            assert_static(config,identity,args.config);training=read(config['training_state'])
            require(time.time()-state['started_unix']<=21600,'等待超过6小时，停止保留')
            require(not (Path(config['training_root'])/'STOP_AFTER_CURRENT').exists() and not (root/'STOP').exists(),'用户停止标记存在，禁止自动接续')
            require(not training.get('status','').startswith(('stopped','failed')),'既有训练已停止/失败；不自动恢复')
            complete=training_complete(config,require_absent=False)
            if complete is not None:
                try:training_complete(config,require_absent=True)
                except ValueError as error:
                    # terminal落盘与venvlauncher退栈可短暂先后；继续等待而非判失败。
                    if '训练/评价/launcher仍未真实退出' not in str(error):raise
                    time.sleep(10);continue
                break
            time.sleep(10)
        state.update(status='checking_tracking_readonly_preflight',training_summary_sha256=complete['summary_sha256']);atomic(path,state)
        driver=Path(config['association_bundle'])/'tools/research_ops/v5_association_driver.py';command=[str(PYTHON),'-B',str(driver),'--config',str(args.config)]
        result=subprocess.run(command,check=True,capture_output=True,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));report=json.loads(result.stdout.strip().splitlines()[-1])
        require(report['status']=='readonly_prerequisites_complete_no_launch','tracking预飞未通过')
        state.update(status='tracking_running',readonly_preflight=report);atomic(path,state)
        with (root/'tracking_driver.log').open('x',encoding='utf-8') as stream:
            child=subprocess.Popen(command+['--execute','--driver-sha256',config['association_driver_sha256']],stdout=stream,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));state['child_pid']=child.pid;atomic(path,state);code=child.wait()
        require(code==0,'trackingdriver失败；不重放');final=read(Path(config['output_root'])/'driver_state.json');require(final['status']=='complete_all_nine_association_and_metrics','trackingdriver非完整终态')
        state.update(status='complete_handoff_and_ninearm_tracking',child_pid=None,tracking_summary=final['summary']);atomic(path,state);(root/'driver.lock').unlink()
    except BaseException as error:
        state.update(status='stopped_preserved_no_replay',error_type=type(error).__name__,error=str(error));atomic(path,state);raise
if __name__=='__main__':main()
