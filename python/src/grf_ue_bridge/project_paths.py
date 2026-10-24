"""统一新项目布局路径；stdlib实现，UE/P1/研究环境均可只读使用。"""
from pathlib import Path


def project_root(anchor=None, required=True):
    """从明确uproject祖先定位项目，不回退已删除的Content代码目录。"""
    path=Path(anchor or __file__).absolute()
    base=path if path.is_dir() else path.parent
    for root in (base,*base.parents):
        if any(root.glob('*.uproject')):return root
    if required:raise FileNotFoundError('找不到UE项目根，请传入明确项目内anchor')
    return None


def python_root(anchor=None):return project_root(anchor)/'python'
def experiments_root(anchor=None):return project_root(anchor)/'experiments/sim2real'
def ue_scripts_root(anchor=None):return python_root(anchor)/'ue'
def saved_root(anchor=None):return project_root(anchor)/'Saved'
def research_root(anchor=None):return project_root(anchor).parent/'FutsalMOT_Research'


def p1_private_root(repo_root=None):
    """仅本项目代码根使用Saved；显式独立仓库不继承祖先机器配置。"""
    project = project_root(__file__, required=False)
    anchor = Path(repo_root).absolute() if repo_root is not None else None
    if project is not None and (anchor is None or anchor in (project, project / 'python')):
        return project / 'Saved/P1/.futsalmot'
    if anchor is None:
        raise FileNotFoundError('独立使用时必须提供repo_root')
    return anchor / '.futsalmot'


def p1_runtime_root(repo_root=None):return p1_private_root(repo_root)/'runtime'


def research_path(path):
    """新研究元数据/输出必须实际在DResearch；历史G准入不因此自动有效。"""
    actual=Path(path).resolve();root=research_root().resolve()
    if root.drive.upper()!='D:' or actual!=root and root not in actual.parents:
        raise ValueError('未来研究元数据/输出只允许实际D:/projects/FutsalMOT_Research')
    return actual


def research_media_path(path):
    """核实际DResearch/GDataset媒体边界，但保留images词法以维持labels配对。"""
    lexical=Path(path).absolute();actual=lexical.resolve()
    roots=(research_root().resolve(),Path('G:/FutsalMOT_Dataset').resolve())
    if not any(actual==root or root in actual.parents for root in roots):
        raise ValueError('媒体只允许DResearch输入或G:/FutsalMOT_Dataset成品')
    return lexical
