"""ChilloutVR's native avatar-parameter OSC interface (no universal scaling endpoint)."""
DEFAULT_PORT=9000
MANUAL_PROFILE='chilloutvr:manual'


def profile_key(discovery):
    if not discovery or discovery.get('platform')!='chilloutvr':return MANUAL_PROFILE
    key='chilloutvr:'+str(discovery.get('avatar') or 'manual')
    if discovery.get('avatarProfile') is not None:key+=':profile:'+str(discovery['avatarProfile'])
    return key


def scale_mapping():
    # AAS scale sliders have avatar-authored ranges; never invent a universal Scale parameter.
    return {'source':'height','target':'','kind':'float','mode':'range','enabled':True,'smooth':True,
            'platform':'chilloutvr','inputMin':0,'inputMax':10,'outputMin':0,'outputMax':1}


def setup_text(config,items,sources):
    names={s['id']:s for s in sources}
    lines=["Mid's Den → ChilloutVR",'',
           'Enable OSC in Settings → Implementation → OSC.',
           'Use the default OSCQuery name prefix ChilloutVR so the companion can identify the game.',
           f"Destination: {config['oscHost']}:{config['oscPort']}. OSCQuery's advertised receive port is used when available.",
           'VRChat and ChilloutVR both default to UDP 9000. If running both, give one a different listener port; use --osc-listener-port=<port> in ChilloutVR.',
           '', 'Avatar setup:',
           'Wear an avatar with a writable animator/AAS parameter that drives the desired property.',
           'The mapping picker lists parameters exposed by OSCQuery, including read-only entries which cannot be selected.',
           'Discovery confirms the ChilloutVR OSCQuery service, not delivery of UDP packets or a visible effect.',
           '', 'Scaling:',
           'Scale mapping starts an editor with Height selected and no target. Pick the actual scaling parameter from your avatar.',
           'There is no universal Scale parameter or documented VRChat-style /avatar/eyeheight endpoint here.',
           'For an AAS slider authored from a minimum to maximum avatar height, choose Map a range and enter those height limits in the website measurement’s unit, and the parameter’s corresponding limits (commonly 0–1).',
           'The initial 0–10 → 0–1 editor values are examples, not detected avatar limits. Replace them before saving.',
           'Use Growth ratio only if the avatar parameter explicitly expects current height ÷ starting height. Do not assume metres equal a scale factor.',
           'An avatar without a scaling animation/parameter needs that setup in Unity/CCK first; the companion cannot add it.',
           '', 'Mappings:']
    for i in items:
        source=names.get(i['source'],{})
        detail=i['mode']
        if i['mode']=='range':detail=f"{i['inputMin']:g}–{i['inputMax']:g} {source.get('unit','')} → {i['outputMin']:g}–{i['outputMax']:g}"
        elif i['mode']=='value':detail='value in '+source.get('unit','saved units')
        elif i['mode']=='ratio':detail='current ÷ original (dimensionless)'
        lines.append(f"- {source.get('name',i['source'])} → {i['target']} · {i['kind']} · {detail}")
    lines += ['', 'Mappings and saved ports are separate from VRChat and Resonite. Detected avatar/profile changes select separate ChilloutVR mapping sets.',
              'Mappings are sent only to a verified ChilloutVR service and writable matching parameters. If discovery fails, no ChilloutVR writes are sent.',
              'Custom OSCQuery prefixes are not auto-identified: restore --osc-query-prefix=ChilloutVR if needed. For an mDNS-blocked network, oscQueryPort in the saved config can specify its TCP query port.',
              'Smooth mode, pace, curves, duration limits, linked measurements and Finish now work as in the other companion modes. Custom units stay in saved units.',
              '', 'Official documentation:',
              'https://docs.chilloutvr.net/chilloutvr/game/osc/',
              'https://docs.chilloutvr.net/chilloutvr/game/launch-arguments/',
              'https://docs.chilloutvr.net/cck/components/cvr-avatar/']
    return '\n'.join(lines)
