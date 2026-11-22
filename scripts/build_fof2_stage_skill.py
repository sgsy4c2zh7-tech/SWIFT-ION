"""Independent 365-day prospective foF2 verification of three deployed stages.

Evaluation uses archived values issued BEFORE a later independent observation.
For comparisons, both methods must have a prediction for the SAME observation.
No hindcast, no filling missing model stages with retrospective recalculation.
"""
from __future__ import annotations
import argparse,csv,json,math
from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import defaultdict
from statistics import mean
from build_year_archive import dates,read_daily,valid_number,RETENTION_DAYS
from build_prospective_skill import HORIZONS_H,iso,parse_utc

ROOT=Path(__file__).resolve().parents[1]
FIELDS={'physics':'predicted_fof2_physics_mhz','empirical':'predicted_fof2_empirical_mhz','ai':'predicted_fof2_ai_mhz'}

def score(rows,key):
    f=FIELDS[key];errors=[r[f]-r['observed_fof2_mhz'] for r in rows
                          if valid_number(r.get(f)) and valid_number(r.get('observed_fof2_mhz'))]
    n=len(errors)
    return {'n':n,'hits':sum(abs(e)<=1 for e in errors),
            'hit_pct':round(sum(abs(e)<=1 for e in errors)*100/n,2) if n else None,
            'mae_mhz':round(mean(abs(e) for e in errors),4) if n else None,
            'rmse_mhz':round(math.sqrt(mean(e*e for e in errors)),4) if n else None,
            'bias_mhz':round(mean(errors),4) if n else None}

def rollup(rows):
    # Main 3-stage skill is strict and longitudinally comparable. Retain
    # low-confidence extended physics values separately as provisional only.
    standard=[r for r in rows if r.get('fof2_quality','STANDARD')=='STANDARD']
    extended=[r for r in rows if r.get('fof2_quality')=='EXTENDED']
    s={key:score(standard,key) for key in FIELDS}
    pe=[r for r in standard if all(valid_number(r.get(FIELDS[k])) for k in ('physics','empirical'))]
    ea=[r for r in standard if all(valid_number(r.get(FIELDS[k])) for k in ('empirical','ai'))]
    all3=[r for r in standard if all(valid_number(r.get(FIELDS[k])) for k in FIELDS)]
    def pair(arr, a,b):
        aa=score(arr,a);bb=score(arr,b)
        return {'n':len(arr),a:aa,b:bb,'gain_hit_pp':round(bb['hit_pct']-aa['hit_pct'],2) if arr else None,
                'mae_gain_mhz':round(aa['mae_mhz']-bb['mae_mhz'],4) if arr else None}
    return {'records':len(rows),'strict_records':len(standard),'extended_records':len(extended),
            'extended_provisional_physics':score(extended,'physics'),
            'stages':s,'physics_empirical_same_observations':pair(pe,'physics','empirical'),
            'empirical_ai_same_observations':pair(ea,'empirical','ai'),
            'all_three_same_observations':{'n':len(all3), 'stages':{k:score(all3,k) for k in FIELDS}}}

def report(history,now):
    first=now.date()-timedelta(days=RETENTION_DAYS-1)
    daily_rows=defaultdict(list);monthly_rows=defaultdict(list);lead_rows=defaultdict(list)
    n=0
    for day in dates(first,now.date()):
        for item in read_daily(Path(history)/'tec_matches',day):
            try:
                lead=int(item['nominal_horizon_h'])
                if lead not in HORIZONS_H:continue
                # Pre-v2.1 records have no published stage fields and are not
                # retroactively populated; only post-deployment issued fields count.
                if not any(valid_number(item.get(v)) for v in FIELDS.values()):continue
                if not (parse_utc(item['issued_at'])<parse_utc(item['valid_at'])<=now):continue
                if parse_utc(item['observed_at'])>now+timedelta(minutes=5):continue
                if not valid_number(item.get('observed_fof2_mhz')):continue
                lead_rows[lead].append(item)
                daily_rows[(day.isoformat(),lead)].append(item)
                monthly_rows[(day.strftime('%Y-%m'),lead)].append(item)
                n+=1
            except (KeyError,TypeError,ValueError):continue
    ds=[{'day_utc':day.isoformat(),'horizon_h':h,'summary':rollup(daily_rows[(day.isoformat(),h)])}
         for day in dates(first,now.date()) for h in HORIZONS_H]
    months=sorted({d.strftime('%Y-%m') for d in dates(first,now.date())})
    ms=[{'month_utc':month,'horizon_h':h,'summary':rollup(monthly_rows[(month,h)])}
         for month in months for h in HORIZONS_H]
    by={str(h):rollup(lead_rows[h]) for h in HORIZONS_H}
    return {'schema':'swift-ion-fof2-three-stage-skill-v1','status':'AVAILABLE' if n else 'AWAITING_FUTURE_OBSERVATIONS',
            'metadata':{'generated_at':iso(now),'retention_days':365,'start_utc':first.isoformat(),
                        'end_utc':now.date().isoformat(),'hit_definition':'abs(prediction-observation) <=1 MHz',
                        'comparison':'same independent observation, same location, target, lead and prospectively issued models',
                        'observations_license':'GIRO derived via KC2G CC BY-NC-SA 4.0: noncommercial / original station acknowledgements',
                        'predeployment_backfill':False,
                        'notes':['AI stage is only assessed when prospectively issued trained AI values exist.',
                                 'Overlapping target lead groups are not independent samples.',
                                 'The headline three-stage scores include only STANDARD source-quality predictions; EXTENDED provisional physics is separate.',
                                 'Missing data excluded, not scored as zero.',
                                 'Model selection holdout is separate from these prospective skill reports.']},
            'total_matches':n,'by_horizon':by,'daily':ds,'monthly':ms}

def write_csv(path,rows,key):
    headings=[key,'horizon_h','records','strict_records','extended_records','extended_physics_hit_pct_provisional','stage','n','hits','hit_pct','mae_mhz','rmse_mhz','bias_mhz','all_three_n']
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=headings);w.writeheader()
        for r in rows:
            s=r['summary']
            for stage,metrics in s['stages'].items():
                w.writerow({key:r[key],'horizon_h':r['horizon_h'],'records':s['records'],'strict_records':s['strict_records'],
                    'extended_records':s['extended_records'],
                    'extended_physics_hit_pct_provisional':s['extended_provisional_physics']['hit_pct'],
                    'stage':stage,
                    **metrics,'all_three_n':s['all_three_same_observations']['n']})

def run(history,docs,now=None):
    now=now or datetime.now(timezone.utc)
    out=report(history,now);docs=Path(docs);docs.mkdir(parents=True,exist_ok=True)
    (docs/'fof2_stage_skill.json').write_text(json.dumps(out,ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf-8')
    write_csv(docs/'fof2_stage_daily.csv',out['daily'],'day_utc')
    write_csv(docs/'fof2_stage_monthly.csv',out['monthly'],'month_utc')
    print('foF2 stages: prospective verified',out['total_matches'],'matched rows',flush=True)
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--history',type=Path,required=True);p.add_argument('--docs',type=Path,required=True);args=p.parse_args();run(args.history,args.docs)
if __name__=='__main__':main()
