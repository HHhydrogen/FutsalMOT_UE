"""绿色对照独立评价身份；TrackEval与player GT口径完全沿用冻结v9。"""
import argparse
import configparser
from contextlib import redirect_stdout
import importlib.util
import inspect
import io
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from green_kit_runtime import EXPERIMENT, checked, load_reference, physical_output, read, require, sha, validate_protocol
SEQUENCE = {'game4': 'SNMOT-060', 'game6': 'SNMOT-097', 'game9': 'SNMOT-151'}


def evaluate(config, tracking, output):
    cfg, _ = validate_protocol(config); _, old = load_reference(cfg)
    path = Path(old['bundle'])/'tools/research_ops/v9_metric.py'
    spec = importlib.util.spec_from_file_location('green_reference_metric_numeric', path)
    numeric = importlib.util.module_from_spec(spec); spec.loader.exec_module(numeric)
    tracking = Path(tracking); receipt = read(tracking/'receipt.json')
    require(receipt['schema'] == 'green_kit_gated_tracking_v1' and receipt['status'] == 'complete'
            and receipt['protocol_sha256'] == sha(config) and receipt['frames'] == 750
            and receipt['GT_read'] is False, '独立绿色预测身份缺失')
    fold = receipt['fold']; sequence = SEQUENCE[fold]; require(sequence == receipt['sequence'], 'heldout身份不同')
    source_cfg = read(checked(old['source_config']))
    source = next(s for s in source_cfg['sources'] if s['domain'] == 'real' and s['game'] == fold)
    require(source['cache'] == receipt['cache'], '固定输入cache不同')
    info = configparser.ConfigParser(); info.read(checked(source['gameinfo']), encoding='utf-8-sig')
    seqinfo = configparser.ConfigParser(); seqinfo.read(checked(source['seqinfo']), encoding='utf-8-sig')
    require('game'+info['Sequence']['gameID'] == fold and seqinfo['Sequence']['name'] == sequence
            and float(seqinfo['Sequence']['frameRate']) == 25, '实际比赛/序列不同')
    players = {int(k.split('_')[-1]) for k, v in info['Sequence'].items() if k.startswith('trackletid_')
               and (v.strip().lower().startswith('player ') or v.strip().lower().startswith('goalkeeper'))}
    require(players, '真实player roster缺失')
    gt = []
    for line in checked(source['gt']).read_text(encoding='utf-8-sig').splitlines():
        row = line.split(','); frame, identity = int(row[0]), int(row[1])
        if 1 <= frame <= 750 and identity in players and int(float(row[6])) == 1:
            gt.append(','.join(row[:6]+['1', '1', '1']))
    pred = tracking/'data'/(sequence+'.txt'); require(sha(pred) == receipt['mot_sha256'], '预测文本变化')
    predicted = [line for line in pred.read_text(encoding='utf-8').splitlines() if line]
    require(len(predicted) == receipt['tracked_rows'], '预测不准GT筛行')
    output = physical_output(output); require(not output.exists(), '全新绿色评价目录')
    output.mkdir(parents=True); gtroot = output/'derived_player_gt'; folder = gtroot/sequence/'gt'; folder.mkdir(parents=True)
    (folder/'gt.txt').write_text('\n'.join(gt)+'\n', encoding='utf-8')
    (gtroot/sequence/'seqinfo.ini').write_text('[Sequence]\nname='+sequence+'\nimDir=img1\nframeRate=25\nseqLength=750\nimWidth='+
        seqinfo['Sequence']['imWidth']+'\nimHeight='+seqinfo['Sequence']['imHeight']+'\nimExt=.jpg\n', encoding='utf-8')
    import trackeval
    require(trackeval.__version__ == '1.3.0', '固定TrackEval1.3.0')
    capture = io.StringIO()
    dataset_config = dict(GT_FOLDER=str(gtroot), TRACKERS_FOLDER=str(tracking.parent), OUTPUT_FOLDER=str(output/'trackeval'),
        TRACKERS_TO_EVAL=[tracking.name], SKIP_SPLIT_FOL=True, SEQ_INFO={sequence: 750}, DO_PREPROC=False,
        BENCHMARK='MOT17', SPLIT_TO_EVAL='train', PRINT_CONFIG=False, CLASSES_TO_EVAL=['pedestrian'],
        TRACKER_SUB_FOLDER='data', INPUT_AS_ZIP=False)
    evaluation_config = dict(USE_PARALLEL=False, PRINT_CONFIG=False, PRINT_RESULTS=False, PLOT_CURVES=False,
        TIME_PROGRESS=False, OUTPUT_SUMMARY=True, OUTPUT_DETAILED=True, BREAK_ON_ERROR=True, LOG_ON_ERROR=str(output/'errors.txt'))
    with redirect_stdout(capture):
        evaluator = trackeval.Evaluator(evaluation_config); dataset = trackeval.datasets.MotChallenge2DBox(dataset_config)
        require(dataset.do_preproc is False, '不得隐式过滤预测')
        metrics = [trackeval.metrics.HOTA(), trackeval.metrics.CLEAR(dict(PRINT_CONFIG=False)), trackeval.metrics.Identity(dict(PRINT_CONFIG=False))]
        results, messages = evaluator.evaluate([dataset], metrics)
    require(messages['MotChallenge2DBox'][tracking.name] == 'Success', '评价失败')
    raw = numeric.plain(results['MotChallenge2DBox'][tracking.name]); require(set(raw) == {sequence, 'COMBINED_SEQ'}, '不扩大scope')
    summary = {}
    for name, classes in raw.items():
        value = classes['pedestrian']; numeric.validate_count(name, value['Count'], len(predicted), len(gt), sequence)
        fraction = {}
        for group, keys in [('HOTA', ('HOTA', 'AssA', 'DetA')), ('Identity', ('IDF1',)), ('CLEAR', ('MOTA',))]:
            for key in keys:
                v = value[group][key]; fraction[key] = sum(v)/len(v) if isinstance(v, list) else float(v)
        summary[name] = dict(metrics_fraction=fraction, metrics_percent={k: 100*v for k, v in fraction.items()}, IDSW_count=int(value['CLEAR']['IDSW']))
    result = dict(schema='green_kit_gated_trackeval_v1', status='complete', protocol_sha256=sha(config),
        tracking_receipt_sha256=sha(tracking/'receipt.json'), fold=fold, sequence=sequence, mode=receipt['mode'],
        binding=receipt['binding'], frames=750, summary=summary, raw_results=raw, DO_PREPROC=False, test_read=False,
        GT_used_only_for_metric=True, GT=dict(source=source['gt'], gameinfo=source['gameinfo'], seqinfo=source['seqinfo'],
        derived_sha256=sha(folder/'gt.txt'), rows=len(gt), selection='same v9 player/goalkeeper mark1 first750; predictions never GT filtered'),
        numerical_source_sha256={str(Path(inspect.getfile(type(x)))): sha(inspect.getfile(type(x))) for x in [evaluator, dataset]+metrics})
    (output/'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (output/'stdout.txt').write_text(capture.getvalue(), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'tracking', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    print(json.dumps(evaluate(args.config, args.tracking, args.output) if args.execute else
                     dict(status='readonly_green_metric_plan', GT_read=False), ensure_ascii=False))
