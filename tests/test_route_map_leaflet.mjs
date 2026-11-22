import assert from 'node:assert/strict';
import {createRouteMapEditor} from '../docs/shared/route-map-editor.mjs';
function layerFactory(kind){return (position,opts)=>{
  const events={};return {kind,position,opts,on(name,fn){events[name]=fn;return this},fire(name,data){events[name]?.(data)},getLatLng(){return {lat:this.position[0],lng:this.position[1]}},addTo(map){map.layers.add(this);return this}};
}}
const container={classList:{toggle(){}}},ev={},map={layers:new Set(),on(n,fn){ev[n]=fn},off(n){delete ev[n]},removeLayer(x){this.layers.delete(x)},getContainer(){return container},latLngToContainerPoint(p){return {x:p.lng,y:p.lat}},fitBounds(){}};
const globalL={marker:layerFactory('marker'),polyline:layerFactory('line'),divIcon:x=>x,latLng:(lat,lng)=>({lat,lng}),latLngBounds:x=>({pad:()=>x})};globalThis.L=globalL;
const changes=[];const editor=createRouteMapEditor({map,points:[[35,139],[26,127]],onChange:p=>changes.push(p)});
assert.equal(editor.getStats().count,2);
editor.setMode('add');ev.click({latlng:{lat:33,lng:132}});
assert.equal(editor.getPoints().length,3);
let marker=[...map.layers].find(x=>x.kind==='marker');
marker.position=[36,140];marker.fire('dragend');
assert.deepEqual(editor.getPoints()[0],[36,140]);
editor.setMode('insert');const line=[...map.layers].find(x=>x.kind==='line');
line.fire('click',{latlng:{lat:30,lng:130}});
assert.equal(editor.getPoints().length,4);
assert.equal(changes.length,3);
editor.clear();assert.equal(editor.getPoints().length,0);
editor.dispose();assert.equal(map.layers.size,0);
console.log('Leaflet mock: tap, drag, insert, clear, and disposal passed');
