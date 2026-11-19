"""Read-only checks and explicit status for the CLIP study."""
import argparse
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['kiem-tra', 'trang-thai', 'chuan-bi', 'kiem-tra-mo-hinh'])
    parser.add_argument('--bao-cao', action='store_true')
    args = parser.parse_args()
    if args.bao_cao:
        import src.vqa_research.chuyen_giao.core as core
        core.OUT = core.REPORT_OUT
    from src.vqa_research.chuyen_giao.core import OUT, StudyData
    if args.command == 'trang-thai':
        p = OUT / 'status.json'
        print(p.read_text() if p.exists() else 'Chưa khởi chạy hàng đợi.')
    elif args.command == 'chuan-bi':
        from src.vqa_research.chuyen_giao.features import prepare_model
        prepare_model()
    elif args.command == 'kiem-tra-mo-hinh':
        from src.vqa_research.chuyen_giao.features import cpu_smoke
        print(json.dumps(cpu_smoke(), indent=2))
    else:
        from src.vqa_research.chuyen_giao.pipeline import preflight
        from src.vqa_research.chuyen_giao.core import MODEL
        from src.vqa_research.chuyen_giao.features import tokenizer_check
        data = StudyData()
        result = preflight(data, compact=args.bao_cao)
        if (MODEL / 'tokenizer_config.json').exists():
            tokenizer_check(data)
        print(json.dumps({k: result[k] for k in ('status', 'source_runs', 'target_runs',
                                                'group_directions', 'family_directions')}, indent=2))


if __name__ == '__main__':
    main()
