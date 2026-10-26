"""源PNG退休后，以已验导入资产的原始package摘要核验地板；不生成或修改资产。"""
import hashlib
from pathlib import Path


def verify_imported_floor_asset_bytes(project, report, current_binding=None):
    project=Path(project)
    prefix='/Game/FutsalMOT/Environment/Floors/V1/'
    expected={'M_FloorTint_v1','T_FloorNeutral_Albedo_v1'}|{'MI_sport_'+n+'_v1' for n in ('blue','gray','teal','terracotta')}
    if current_binding is not None:
        if current_binding.get('policy')!='pinned_current_git_floor_assets_v1' or current_binding.get('worktree_assets_match_git') is not True:
            raise ValueError('当前地板资产必须由独立Git干净基线明确绑定')
        refs=current_binding['asset_sha256']
    else:
        refs=report.get('asset_sha256_after',{})
    if {p[len(prefix):] for p in refs if p.startswith(prefix)}!=expected or len(refs)!=6:
        raise ValueError('必须是原已验六个地板资产的明确package清单')
    result=[]
    for package, digest in refs.items():
        path=project/'Content'/(package[len('/Game/'):]+'.uasset')
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=digest:raise ValueError('地板导入资产已偏离原已验版本：'+package)
        result.append(dict(package=package,sha256=actual))
    return result
