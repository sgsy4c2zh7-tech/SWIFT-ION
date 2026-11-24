"""Safely patch SWIFT-ION station sampling to balance a 32-station global catalog.

Run from SWIFT-ION repository root (or --repo-root PATH). This patches the
current repository files rather than shipping stale full-file replacements.
Does not change TEC, foF2 physics, scoring tolerances, quality gates or history.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path

PATCH_TAG = 'STATION_COVERAGE_V1'


def substitution(source: str, old: str, new: str, path: str) -> str:
    if new in source:
        return source  # Re-running after successful patch is safe.
    if source.count(old) != 1:
        raise ValueError(f'{path}: missing or repeated anchor: {old[:110]!r}')
    return source.replace(old, new, 1)


def replace_global_sample(source: str, path: str) -> str:
    new = '''def global_sample(records, limit):
    """Geographically balanced selection among the source's REAL stations.

    Deterministically favors underrepresented latitude/longitude sectors.
    It never creates missing observation coordinates or values.
    """
    from station_coverage import balanced_global_sample
    return balanced_global_sample(records, limit)


'''
    expr = r'def global_sample\(records, limit\):\n.*?\n\n(?=def error_stats\()'
    m = re.search(expr, source, flags=re.S)
    if m is None:
        if new in source:
            return source
        raise ValueError(f'{path}: global_sample structure changed; refusing unsafe patch')
    return source[:m.start()] + new + source[m.end():]


def patch_relative(root: Path, rel: str, updater):
    file = root / rel
    if not file.is_file():
        raise FileNotFoundError(f'Missing repository file: {rel}')
    old = file.read_text(encoding='utf-8')
    new = updater(old, rel)
    if new != old:
        file.write_text(new, encoding='utf-8')
        print('PATCHED:', rel)
        return True
    print('UNCHANGED:', rel)
    return False


def patch_validation(s, path):
    s = replace_global_sample(s, path)
    s = substitution(s, 'def evaluate(raw, now=None, max_stations=16,',
                     'def evaluate(raw, now=None, max_stations=32,',path)
    s = substitution(s, "parser.add_argument('--max-stations', type=int, default=16)",
                     "parser.add_argument('--max-stations', type=int, default=32)",path)
    s = substitution(s,
        "    base['sampled_stations'] = len(stations)\n",
        "    base['sampled_stations'] = len(stations)\n"
        "    from station_coverage import coverage_summary\n"
        "    base['coverage'] = coverage_summary(records, stations)\n",path)
    s = substitution(s,
        "    base['evaluated_stations'] = len(matched)\n",
        "    base['evaluated_stations'] = len(matched)\n"
        "    base['coverage']['iri_comparisons_succeeded'] = len(matched)\n",path)
    return s


def patch_prospective(s,path):
    return substitution(s,
        'horizons=HORIZONS_H, max_stations=16,',
        'horizons=HORIZONS_H, max_stations=32,',path)


def patch_year_archive(s,path):
    return substitution(s,
        'outlook=build_outlook(observations,iri_function,now,max_stations=12,published_at=published_at)',
        'outlook=build_outlook(observations,iri_function,now,max_stations=32,published_at=published_at)',path)


def patch_tec_skill(s,path):
    s=substitution(s,'MAX_STATIONS = 16','MAX_STATIONS = 32',path)
    # The fixed NICT slots are unchanged. Select a balanced set of the other
    # actual stations instead of simply taking their arbitrary input order.
    s=substitution(s,
        "    station_list=nict_fixed+list(observations.get('stations', []))",
        "    from station_coverage import balanced_global_sample\n"
        "    station_list=nict_fixed+balanced_global_sample(list(observations.get('stations', [])), max_stations)",
        path)
    return s


def patch_workflow(s,path):
    s=substitution(s,'            --max-stations 16 \\', '            --max-stations 32 \\',path)
    s=substitution(s,
      "          print('Ionosonde status:', d['status'], 'matched:', d['evaluated_stations'])\n",
      "          print('Ionosonde status:', d['status'], 'matched:', d['evaluated_stations'])\n"
      "          c=d.get('coverage',{})\n"
      "          print('Coverage (source eligible / selected / successful / occupied 30x60deg regions):',\n"
      "                c.get('source_usable_stations'),c.get('selected_stations'),\n"
      "                c.get('iri_comparisons_succeeded'),c.get('selected_occupied_regions'))\n", path)
    return s


def patch_year_html(s,path):
    return substitution(s,'<nav><a href="#main-skill">',
                        '<nav><a href="./station_coverage.html">観測所分布</a><a href="#main-skill">',path)


CHANGES = (
    ('scripts/validate_ionosondes.py', patch_validation),
    ('scripts/build_prospective_skill.py', patch_prospective),
    ('scripts/build_year_archive.py', patch_year_archive),
    ('scripts/build_tec_skill.py', patch_tec_skill),
    ('.github/workflows/pages.yml', patch_workflow),
    ('docs/year.html', patch_year_html),
)


def apply(root: Path) -> int:
    root=root.resolve()
    # Preflight ALL changes in memory first, so an unmatched version leaves
    # everything untouched rather than breaking half a workflow.
    originals={}
    replacements={}
    for rel, fn in CHANGES:
        path = root / rel
        if not path.is_file():
            raise FileNotFoundError(f'Required SWIFT-ION file missing: {rel}')
        originals[rel] = path.read_text(encoding='utf-8')
        replacements[rel] = fn(originals[rel], rel)
    for rel, _ in CHANGES:
        if replacements[rel] != originals[rel]:
            (root/rel).write_text(replacements[rel],encoding='utf-8')
            print('PATCHED:',rel)
        else:
            print('ALREADY PATCHED:',rel)
    return sum(replacements[x]!=originals[x] for x in originals)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[1])
    a=p.parse_args()
    n=apply(a.repo_root)
    print('SWIFT-ION global station patch: OK;',n,'files changed')

if __name__=='__main__':
    main()
