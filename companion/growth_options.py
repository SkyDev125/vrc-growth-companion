"""Shared validation for saved growth preferences and desktop controls."""
import math

DEFAULTS={'speed':1.,'curve':'gentle','maxDuration':120.}
CURVES=('gentle','steady','quickStart')


def normalize(raw=None, strict=False):
    if not isinstance(raw,dict):
        if strict:raise ValueError('Invalid growth settings.')
        raw={}
    result=dict(DEFAULTS)
    for key,low,high in (('speed',.25,4.),('maxDuration',3.,120.)):
        value=raw.get(key,DEFAULTS[key])
        try:
            if isinstance(value,bool):raise ValueError()
            value=float(value)
            if not math.isfinite(value) or not low<=value<=high:raise ValueError()
            result[key]=value
        except (ValueError,TypeError):
            label={'speed':'Pace','maxDuration':'Maximum duration'}[key]
            if strict:raise ValueError(f'{label} must be between {low:g} and {high:g}.') from None
    curve=raw.get('curve',DEFAULTS['curve'])
    if curve in CURVES:result['curve']=curve
    elif strict:raise ValueError('Choose Gentle, Steady, or Quick start.')
    return result
