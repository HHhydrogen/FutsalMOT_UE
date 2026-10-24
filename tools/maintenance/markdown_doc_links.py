"""纯函数Markdown链接改写；Windows词法路径，不resolve、不读取链接目标。"""
import ntpath
import re
from urllib.parse import unquote,quote

PROJECT='D:/projects/FutsalMOT_UEDataset'


def links(text):
    """读取非代码围栏中的本地Markdown链接，供暂存检查使用。"""
    fence = False
    for line in text.splitlines():
        if re.match(r'^\s*(`{3,}|~{3,})', line):
            fence = not fence
            continue
        if fence:
            continue
        line = re.sub(r'`[^`]*`', '', line)
        for target in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)', line):
            yield target.strip('<>')

def key(path):return ntpath.normcase(ntpath.normpath(str(path).replace('/','\\')))

def rewrite_target(target,old_file,new_file,mapping,project=PROJECT):
    angle=target.startswith('<') and target.endswith('>');raw=target[1:-1] if angle else target
    if not raw or raw.startswith(('#','//')) or re.match(r'^[a-zA-Z][\w+.-]*:',raw) and not re.match(r'^[a-zA-Z]:[/\\]',raw):return target
    pathpart,sep,fragment=raw.partition('#');pathpart,qsep,query=pathpart.partition('?')
    if not pathpart:return target
    lexical=unquote(pathpart).replace('/','\\')
    if ntpath.isabs(lexical):absolute=ntpath.normpath(lexical)
    else:absolute=ntpath.normpath(ntpath.join(ntpath.dirname(old_file),lexical))
    try:
        if key(ntpath.commonpath([project,absolute]))!=key(project):return target
    except ValueError:return target
    destinations={key(a):str(b) for a,b in mapping.items()}
    absolute=destinations.get(key(absolute),absolute)
    relative=ntpath.relpath(absolute,ntpath.dirname(new_file)).replace('\\','/')
    if '%' in pathpart:relative=quote(relative,safe='/._-')
    suffix=('?'+query if qsep else '')+('#'+fragment if sep else '')
    value=relative+suffix
    return '<'+value+'>' if angle or ' ' in value else value

def rewrite_markdown(text,old_file,new_file,mapping,project=PROJECT):
    """保留代码围栏和行内代码；改普通/图片/引用式链接，不改代码或backtick路径。"""
    output=[];fence=None
    inline=re.compile(r'(!?\[[^\]\n]*\]\()(<[^>\n]+>|[^\s)]+)([^)\n]*\))')
    reference=re.compile(r'^(\s*\[[^\]]+\]:\s*)(<[^>\n]+>|\S+)(.*)$')
    for line in text.splitlines(keepends=True):
        hit=re.match(r'^\s*(`{3,}|~{3,})',line)
        if hit:
            if fence is None:fence=hit.group(1)[0]
            elif hit.group(1)[0]==fence:fence=None
            output.append(line);continue
        if fence:output.append(line);continue
        pieces=re.split(r'(`+[^`]*`+)',line)
        for i,piece in enumerate(pieces):
            if piece.startswith('`'):continue
            def convert(match):return match.group(1)+rewrite_target(match.group(2),old_file,new_file,mapping,project)+match.group(3)
            pieces[i]=inline.sub(convert,piece)
        changed=''.join(pieces)
        hit=reference.match(changed.rstrip('\r\n'))
        if hit:
            ending=changed[len(changed.rstrip('\r\n')):]
            changed=hit.group(1)+rewrite_target(hit.group(2),old_file,new_file,mapping,project)+hit.group(3)+ending
        output.append(changed)
    return ''.join(output)
