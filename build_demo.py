"""Build clearly labelled synthetic demonstration data, never live forecast."""
import json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pathlib import Path
from src.core.layers import describe_layers,integrated_tec_tecu
from src.gnss.delay import ionospheric_group_delay_m
from src.hf.assessment import assess_route
from src.propagation.assessment import assess_link
from src.alerts.assessment import assess_alerts
h=list(range(60,601,5))
def gaussian(x,mu,sigma,amplitude):return amplitude*math.exp(-.5*((x-mu)/sigma)**2)
ne=[gaussian(x,80,12,2e8)+gaussian(x,110,17,1.2e11)+gaussian(x,185,28,1.8e11)+gaussian(x,310,85,9e11) for x in h]
result={'metadata':{'mode':'SYNTHETIC DEMONSTRATION','is_forecast':False,'is_observation':False,'warning':'Not suitable for operational decisions','coverage_km':[60,600]},'profile':{'altitude_km':h,'ne_m3':ne},'layers':describe_layers(h,ne),'tec_60_600_tecu':integrated_tec_tecu(h,ne),'hf':assess_route([{'lat':0,'lon':0},{'lat':1,'lon':1}]),'gnss':{'example_L1_delay_m':ionospheric_group_delay_m(10,1575.42e6),'note':'Illustrative 10 TECU, not a position-error prediction'},'propagation':assess_link(),'alerts':assess_alerts()}
p=Path('docs/demo.json');p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(result,indent=2),encoding='utf-8')
print('Wrote',p)
