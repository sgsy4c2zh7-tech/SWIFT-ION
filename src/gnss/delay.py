"""First-order group delay only; not a positioning accuracy prediction."""
def ionospheric_group_delay_m(vtec_tecu,frequency_hz):
    if vtec_tecu<0 or frequency_hz<=0:raise ValueError('Invalid TEC/frequency')
    return 40.3*(vtec_tecu*1e16)/(frequency_hz**2)
