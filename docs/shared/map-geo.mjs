/** Exact Web Mercator vertical coordinate inversion for equirectangular forecast rasters.
 * Used by Leaflet ImageOverlay to keep numerical field samples aligned with tile maps.
 */
const RAD=Math.PI/180, DEG=180/Math.PI;
export function mercatorY(latitude){
 if(!Number.isFinite(latitude)||Math.abs(latitude)>85.051129)throw RangeError('Latitude outside Web Mercator');
 return Math.log(Math.tan(Math.PI/4+(latitude*RAD)/2));
}
export function latitudeAtMercatorFraction(north,south,fraction){
 if(!(north>south)||!Number.isFinite(fraction)||fraction<0||fraction>1)throw RangeError('Invalid geographic bounds/fraction');
 const y=mercatorY(north)*(1-fraction)+mercatorY(south)*fraction;
 return Math.atan(Math.sinh(y))*DEG;
}
export function mercatorFractionAtLatitude(north,south,latitude){
 if(!(north>south))throw RangeError('Invalid bounds');
 return (mercatorY(north)-mercatorY(latitude))/(mercatorY(north)-mercatorY(south));
}
