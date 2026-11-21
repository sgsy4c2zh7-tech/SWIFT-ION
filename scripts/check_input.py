import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pathlib import Path
from src.ingestion.swift_tec import load_export
p=Path('data/input/swift_tec.json')
if not p.exists():
    print('No SWIFT-TEC export found. See docs/SWIFT_TEC_CONTRACT.md')
else:
    data=load_export(p)
    print('Validated read-only export:',len(data['cells']),'cells, valid_at',data['valid_at'])
