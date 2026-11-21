"""HF module: explicitly unavailable until a validated ray-tracing engine exists."""
def assess_route(route):
    if not isinstance(route,list) or len(route)<2:raise ValueError('Route needs at least two points')
    return {'status':'not_implemented','muf_mhz':None,'luf_mhz':None,'fot_mhz':None,'reason':'Requires validated propagation model, endpoints, antenna/noise and temporal conditions'}
