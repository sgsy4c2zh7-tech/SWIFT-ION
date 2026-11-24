"""Idempotent SWIFT-ION source migration: observed-Kp classifications for foF2 skill.

Run from the repository root. No forecast model or predictor is altered.
Strong anchor checks prevent silently editing an unexpected version of source.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def once(text, before, after, label):
    if before not in text:
        raise RuntimeError(f"Missing expected source anchor: {label}. Source has changed; no files were written.")
    if text.count(before) != 1:
        raise RuntimeError(f"Unexpected source anchor count for {label}: {text.count(before)}")
    return text.replace(before, after)


def upgrade_tec(s):
    if "kp3day_by_observed_activity" in s:
        return s
    s = once(s,
        "from build_prospective_skill import iso, parse_utc, next_utc_hour, save\n",
        "from build_prospective_skill import iso, parse_utc, next_utc_hour, save\n"
        "from observed_kp_support import backfill_verified_matches\n",
        "tec imports")
    s = once(s,
        "    by_activity={group:[r for r in kp3day if kp_activity(r.get('kp_forecast'))==group]\n"
        "                 for group in ('QUIET_KP_LT_4','ACTIVE_KP_4_TO_5','STORM_KP_GE_5','UNKNOWN')}\n",
        "    by_activity={group:[r for r in kp3day if kp_activity(r.get('kp_forecast'))==group]\n"
        "                 for group in ('QUIET_KP_LT_4','ACTIVE_KP_4_TO_5','STORM_KP_GE_5','UNKNOWN')}\n"
        "    # NEW MAIN BREAKDOWN: categorize the issued predictions by ACTUAL geomagnetic activity.\n"
        "    # Observed Kp arrives only after the 3-hour bin closes; unknown stays unknown.\n"
        "    by_observed_activity={group:[r for r in kp3day if kp_activity(r.get('kp_observed'))==group]\n"
        "                          for group in ('QUIET_KP_LT_4','ACTIVE_KP_4_TO_5','STORM_KP_GE_5','UNKNOWN')}\n"
        "    observed_pairs=sum(len(by_observed_activity[g]) for g in ('QUIET_KP_LT_4','ACTIVE_KP_4_TO_5','STORM_KP_GE_5'))\n",
        "tec groups")
    s = once(s,
        "            'kp3day_by_activity':{group:{'paired_count':len(cohort),\n"
        "                 'iri':metric(cohort,'predicted_fof2_iri_mhz'),\n"
        "                 'tec':metric(cohort,'predicted_fof2_tec_mhz')}\n"
        "                 for group,cohort in by_activity.items()},\n",
        "            'kp3day_by_activity':{group:{'paired_count':len(cohort),\n"
        "                 'iri':metric(cohort,'predicted_fof2_iri_mhz'),\n"
        "                 'tec':metric(cohort,'predicted_fof2_tec_mhz')}\n"
        "                 for group,cohort in by_activity.items()},\n"
        "             'kp3day_by_observed_activity':{group:{'paired_count':len(cohort),\n"
        "                 'iri':metric(cohort,'predicted_fof2_iri_mhz'),\n"
        "                 'tec':metric(cohort,'predicted_fof2_tec_mhz')}\n"
        "                 for group,cohort in by_observed_activity.items()},\n"
        "             'observed_kp_paired_count':observed_pairs,\n"
        "             'observed_kp_unknown_count':len(kp3day)-observed_pairs,\n",
        "tec observed rollup")
    s = once(s,
        "        'kp_3day_main_skill_requires_exact_same_run_source':True,\n",
        "        'kp_3day_main_skill_requires_exact_same_run_source':True,\n"
        "         'kp_grouping_main':'NOAA_SWPC_ESTIMATED_OBSERVED_KP_AFTER_3H_BIN_END',\n"
        "         'kp_grouping_reference':'ISSUED_NOAA_3DAY_FORECAST_KP',\n"
        "         'kp_missing_policy':'UNKNOWN_NOT_ZERO_AND_NOT_ASSUMED_FORECAST',\n",
        "tec report metadata")
    s = once(s,
        "           'forecast_kp_quiet_n','forecast_kp_storm_n']\n",
        "           'forecast_kp_quiet_n','forecast_kp_storm_n',\n"
        "           'observed_kp_quiet_n','observed_kp_active_n','observed_kp_storm_n','observed_kp_unknown_n']\n",
        "tec csv headers")
    s = once(s,
        "            'forecast_kp_storm_n':s['kp3day_by_activity']['STORM_KP_GE_5']['paired_count']}\n",
        "            'forecast_kp_storm_n':s['kp3day_by_activity']['STORM_KP_GE_5']['paired_count'],\n"
        "            'observed_kp_quiet_n':s['kp3day_by_observed_activity']['QUIET_KP_LT_4']['paired_count'],\n"
        "            'observed_kp_active_n':s['kp3day_by_observed_activity']['ACTIVE_KP_4_TO_5']['paired_count'],\n"
        "            'observed_kp_storm_n':s['kp3day_by_observed_activity']['STORM_KP_GE_5']['paired_count'],\n"
        "            'observed_kp_unknown_n':s['kp3day_by_observed_activity']['UNKNOWN']['paired_count']}\n",
        "tec csv values")
    s = once(s,
        "    count=store_matches(history,matches,now)\n",
        "    count=store_matches(history,matches,now)\n"
        "    # Audit-only label: match observed Kp to already-issued foF2 forecasts.\n"
        "    kp_observed_audit=backfill_verified_matches(history,now)\n",
        "tec observed labeling")
    s = once(s,
        "    payload['archive']={'new_snapshot_issued':snapshot is not None,\n",
        "    payload['archive']={'new_snapshot_issued':snapshot is not None,\n"
        "        'observed_kp_audit':kp_observed_audit,\n",
        "tec archive audit")
    return s


def upgrade_year(s):
    if "kp3day_by_observed_activity" in s:
        return s
    s = once(s,
        '<h3>磁気活動別の予報精度（予報Kpで分類）</h3>',
        '<h3>磁気活動別のfoF2予報精度（観測Kpで分類）</h3>',
        'year title')
    s = once(s,
        '<p class="small">平穏：予報Kp &lt;4 ／ 活動的：4以上5未満 ／ 磁気嵐相当：5以上。<b>これは観測された磁気嵐の検証ではなく、発表時の予報Kpに基づく分類</b>です。Kpが不明なら分類不能とします。</p>',
        '<p class="small">主分類はNOAA SWPCの<b>観測Kp</b>です。平穏：Kp &lt;4 ／ 活動的：4以上5未満 ／ 磁気嵐相当：5以上。予報値は発表時点の予報Kpで計算したものを変更しません。観測Kpは3時間区間終了後に対応付けます。未取得はKp不明として記録し、予報Kpで代用しません。NOAAの値は速報的推定値であり、GFZの確定Kpとは異なります。</p>',
        'year activity explanation')
    s = once(s,
        '<th>予報Kp区分</th><th>評価件数</th>',
        '<th>観測Kp区分</th><th>評価件数</th>',
        'year observed table heading')
    s = once(s,
        '<tbody id="mainWeatherRows"></tbody></table></div></div>',
        '<tbody id="mainWeatherRows"></tbody></table></div>'
        '<details style="margin-top:14px"><summary>参考：発表時の予報Kpで分類した場合</summary>'
        '<p class="small">こちらは予報で想定した磁気活動ごとの結果です。実際の磁気嵐時の精度とは区別してください。</p>'
        '<div class="scroll"><table><thead><tr><th>予報Kp区分</th><th>評価件数</th><th>的中率 ±2 MHz</th><th>MAE（MHz）</th><th>IRI比MAE改善率</th></tr></thead><tbody id="forecastKpRows"></tbody></table></div>'
        '</details></div>',
        'year forecast reference table')
    # Replace only the rendering loop; the rest of the score cards are unchanged.
    start = " const body=$('mainWeatherRows');body.replaceChildren();\n"
    end = " $('mainStatus').textContent=n?\n"
    if s.count(start) != 1 or s.count(end) != 1:
        raise RuntimeError('year rendering anchors changed; no files were written')
    begin, finish = s.index(start), s.index(end)
    old_loop = s[begin:finish]
    if 'kp3day_by_activity' not in old_loop or 'for(const [key,label] of groups)' not in old_loop:
        raise RuntimeError('year renderer is not the expected revision')
    new_loop = """ for(const [id,selector] of [['mainWeatherRows','kp3day_by_observed_activity'],['forecastKpRows','kp3day_by_activity']]){
  const body=$(id);body.replaceChildren();
  for(const [key,label] of groups){
   const g=metricSum(days,s=>s[selector]?.[key]?.tec);
   const b=metricSum(days,s=>s[selector]?.[key]?.iri);
   const improvement=g.n&&b.n===g.n&&b.mae>0?fmt(100*(b.mae-g.mae)/b.mae,1)+'%':'—';
   const tr=body.insertRow();
   for(const val of [label,g.n,g.n?fmt(100*g.hits[2]/g.n)+'%':'—',g.n?fmt(g.mae,3):'—',improvement])tr.insertCell().textContent=String(val);
  }
 }
 const observedKpCount=groups.slice(0,3).reduce((count,[key])=>count+metricSum(days,s=>s.kp3day_by_observed_activity?.[key]?.tec).n,0);
"""
    s = s[:begin] + new_loop + s[finish:]
    s = once(s,
        '   `確認済み：同一SWIFT-TEC実行で使用したNOAA 3日間Kp予報。${n}件を事前発表した最終TEC連動foF2と事後観測で照合。±2 MHzを主指標、±1/±3 MHzは参考。`:\n',
        '   `確認済み：同一SWIFT-TEC実行で使用したNOAA 3日間Kp予報で発表したfoF2を観測と照合 ${n}件。観測Kp分類できたのは${observedKpCount}件、未取得${n-observedKpCount}件。±2 MHzが主指標です。`:\n',
        'year status')
    return s


def apply(root):
    root = Path(root)
    updates = {}
    locations = [
        (root / 'scripts/build_tec_skill.py', upgrade_tec),
        (root / 'docs/year.html', upgrade_year),
    ]
    for path, func in locations:
        if not path.is_file():
            raise RuntimeError(f'Missing repository file: {path}')
        old = path.read_text(encoding='utf-8')
        new = func(old)
        compile(new, str(path), 'exec') if path.suffix == '.py' else None
        updates[path] = (old, new)
    # No changes to any existing file until ALL source anchors pass.
    for path, (old, new) in updates.items():
        if old != new:
            path.write_text(new, encoding='utf-8')
            print('Updated:', path.relative_to(root))
        else:
            print('Already patched:', path.relative_to(root))
    return sum(old != new for old, new in updates.values())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='.', type=Path)
    args = p.parse_args()
    print('Changed files:', apply(args.root))


if __name__ == '__main__':
    main()
