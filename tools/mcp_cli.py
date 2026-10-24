"""真实Unreal MCP单次入口；请求与收据保存在项目Saved，不重放写调用。"""
import argparse
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'python/tools/production'))
from mcp_client import UnrealMCP


def saved_file(value, must_be_new=False):
    path = Path(value).resolve()
    root = (PROJECT / 'Saved').resolve()
    if root != PROJECT / 'Saved':
        raise ValueError('Saved必须为项目D盘原物理目录')
    if root not in path.parents:
        raise ValueError('请求与收据必须实际位于本项目Saved下')
    if must_be_new and path.exists():
        raise FileExistsError('收据已存在，请指定新名称')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--list', action='store_true')
    mode.add_argument('--describe')
    mode.add_argument('--request', help='Saved内的单次JSON请求，operation为call')
    parser.add_argument('--receipt', help='Saved内尚不存在的返回收据')
    args = parser.parse_args()
    receipt = saved_file(args.receipt, True) if args.receipt else None
    request = None
    if args.request:
        request = json.loads(saved_file(args.request).read_text(encoding='utf-8-sig'))
        if request.get('operation') != 'call':
            raise ValueError('请求operation必须为call；查询使用--list/--describe')
    client = UnrealMCP(timeout=120)
    if args.list:
        value = client.request('tools/call', {'name': 'list_toolsets', 'arguments': {}})
    elif args.describe:
        value = client.describe(args.describe)
    else:
        client.describe(request['toolset'])
        value = client.call(request['toolset'], request['tool'], request.get('arguments', {}))
    if receipt:
        receipt.parent.mkdir(parents=True, exist_ok=True)
        with receipt.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
    print(json.dumps(value, ensure_ascii=False))
    if isinstance(value, dict) and value.get('success') not in (None, True, 'true'):
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
