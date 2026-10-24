"""检查暂存Markdown本地文档链接；只读Git索引，不跟随媒体或联接。"""
import json
import ntpath
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote
from markdown_doc_links import links

ROOT=Path(__file__).resolve().parents[2]
def git(*args):
    return subprocess.check_output(['git','-C',str(ROOT),*args])

indexed=set(filter(None,git('ls-files','-z').decode().replace('\\','/').split('\0')))
changed=[p for p in git('diff','--cached','--name-only','--diff-filter=ACMR','-z').decode().split('\0') if p.endswith('.md')]
errors=[]
for doc in changed:
    text=git('show',':'+doc).decode('utf-8-sig')
    for target in links(text):
        path=unquote(target.partition('#')[0].partition('?')[0])
        if not path.lower().endswith('.md') or re.match(r'^[a-zA-Z][\w+.-]*:',path) or path.startswith('//'):continue
        actual=ntpath.normpath(ntpath.join(ntpath.dirname(doc),path)).replace('\\','/')
        if actual not in indexed:errors.append({'file':doc,'target':target,'resolved_index_path':actual})
report={'staged_markdown_files_checked':len(changed),'missing_index_targets':errors,'media_read':False}
print(json.dumps(report,ensure_ascii=False))
raise SystemExit(bool(errors))
