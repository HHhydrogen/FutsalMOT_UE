"""旧grf-ue命令已退役；不保留会改动数据的旧生成分支。"""
import sys


def app():
    print("旧 grf-ue/task 管线已移除。生成请使用 tools/dataset/single_seed_task.py；渲染请使用 tools/dataset/run_single_seed_partitions.py。", file=sys.stderr)
    if sys.argv[1:] not in (["--help"], ["-h"]):
        raise SystemExit(2)


if __name__ == "__main__":
    app()
