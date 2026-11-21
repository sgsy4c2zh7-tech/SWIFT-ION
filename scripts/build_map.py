import json,math
from pathlib import Path
def build():
    bands={'D':(80,2e8),'E':(110,1.2e11),'F1':(185,1.8e11),'F2':(310,9e11)}
    cells=[]
    for lat in range(-85,86,10):
        for lon in range(-175,176,10):
            f=.65+.25*math.cos(math.radians(lat))+.1*math.cos(2*math.radians(lon))
            cells.append({'lat':lat,'lon':lon,'layers':{k:{'ne_m3':round(n*f,2),'height_km':round(h+8*math.sin(math.radians(lat))*math.cos(math.radians(lon)),1)} for k,(h,n) in bands.items()}})
    return {'metadata':{'mode':'SYNTHETIC DEMONSTRATION','is_forecast':False,'is_observation':False,'grid_degrees':[10,10]},'cells':cells}
if __name__=='__main__':
    p=Path(__file__).resolve().parents[1]/'docs/map.json'
    p.write_text(json.dumps(build(),separators=(',',':')),encoding='utf-8')
    print('Created',p)
