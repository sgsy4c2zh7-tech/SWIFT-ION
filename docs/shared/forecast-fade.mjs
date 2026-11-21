/** Conservative coverage mask for sparse IRI point interpolation.
 * Pixels beyond a fixed distance are absent rather than fabricated.
 * The smooth opacity taper prevents hard disk-shaped cutoffs on maps.
 */
export const COVERAGE_LIMIT_KM=Object.freeze({japan:1100,global:3800});
const CORE_KM=Object.freeze({japan:250,global:700});
export function coverageAlpha(distanceKm,region){
 const far=COVERAGE_LIMIT_KM[region];const near=CORE_KM[region];
 if(!Number.isFinite(distanceKm)||!Number.isFinite(far)||distanceKm<0)return 0;
 if(distanceKm<=near)return 1;
 if(distanceKm>=far)return 0;
 const t=(distanceKm-near)/(far-near);
 return 1-t*t*(3-2*t);
}
