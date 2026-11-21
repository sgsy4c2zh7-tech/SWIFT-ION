"""No alerts without verified and timestamped observations."""
def assess_alerts(observations=None):
    return {'status':'unavailable','alerts':[],'reason':'No verified live observations or validated alert thresholds configured'}
