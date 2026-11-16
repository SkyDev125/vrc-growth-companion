"""Resonite's native generic OSC input; paths belong to the user's in-world receiver."""
from urllib.parse import quote

PROFILE='resonite'
DEFAULT_PORT=9002  # Our receiver convention, not a port mandated by Resonite.


def address(value):
    path=str(value).strip()
    if not path:raise ValueError('Enter an OSC receiver path.')
    if not path.startswith('/'):path='/midsden/'+path
    if not 1<len(path)<=256 or any(c.isspace() or ord(c)<32 or c in '*?[]{},#' for c in path):
        raise ValueError('Enter an exact OSC path, such as /midsden/tail.')
    if path.startswith('/avatar/'):
        raise ValueError('Use a Resonite receiver path, such as /midsden/scale.')
    return path


def scale_preset():
    return {'source':'height','target':'/midsden/scale','kind':'float','mode':'ratio','enabled':True,'smooth':True,'platform':'resonite'}


def parameter_options(sources):
    result=[{'name':'Avatar scale','address':'/midsden/scale','kind':'float','writable':True}]
    result.extend({'name':s['name'],'address':'/midsden/measurements/'+quote(s['id'],safe='-_'),
                   'kind':'float','writable':True} for s in sources)
    return result


def setup_text(config, items, sources):
    by_id={s['id']:s for s in sources}
    lines=["Mid's Den → Resonite",'',
        f"Companion destination: {config['oscHost']}:{config['oscPort']} (UDP)",
        '1. Add an OSC_Receiver to a slot on your avatar. Set HandlingUser to its wearer.',
        f"2. Set Port to {config['oscPort']}, AccessReason to Mid's Den growth, and allow OSC receiving when prompted.",
        '3. Add the matching OSC_Value<float> or OSC_Value<int> components below. Set Handler to this receiver, Path exactly as listed, ArgumentIndex 0.',
        '', 'Receiver paths:']
    for item in items:
        source=by_id.get(item['source'],{})
        kind='int (0/1)' if item['kind']=='bool' else item['kind']
        unit='dimensionless current ÷ starting amount' if item['mode']=='ratio' else source.get('unit','saved unit') if item['mode']=='value' else item['mode']
        lines.append(f"- {item['target']} · {kind} · {source.get('name',item['source'])} · {unit}"+(' · disabled' if not item.get('enabled',True) else ''))
    lines += ['', 'Avatar scale preset:',
        '/midsden/scale is a multiplier, not height in metres. 1 means the website starting height.',
        'Calibrate once per avatar: match your current avatar height to the website starting height. Capture User Root Global Scale into a stored BaselineScale value, then keep that baseline fixed.',
        'On changes to the received scale value: target scale = BaselineScale × received /midsden/scale.',
        'Pass that target to Set User Scale, with UserRoot = the wearer’s UserRoot (Local User Root, guarded so only the wearer executes it), AnimationTime = 0.',
        'The companion animates intermediate values. Set User Scale ignores new requests while its own animation is running, so do not add a second animation time.',
        'Do not multiply by the current live user scale each time: that would compound growth.',
        'Recalibrate when changing avatars or changing the baseline/parent scale. Do not read the baseline continuously during growth.',
        'Keep the received scale positive before applying it; a new uninitialized OSC_Value starts at zero.',
        '', 'Other measurements:',
        'Use OSC_Field<float/int> to drive a chosen matching scalar field directly, or route OSC_Value through ProtoFlux for conversions, blendshapes, volumes or other properties.',
        'On/off mappings are transmitted as int 0/1; compare with zero in ProtoFlux when a bool is needed.',
        'Custom measurements stay in their saved units. A volume is not a length: choose the correct source and mapping.',
        '', 'Status and retries:',
        'UDP sending does not confirm Resonite received it. Check OSC_Receiver.IsListening and OSC_Value.Value in-world.',
        'The suggested paths are conventions, not automatically discovered Resonite fields. Use Resend after equipping/reloading the receiver or changing worlds.',
        'The receiver and its ProtoFlux must be configured in Resonite once. This guide is not an importable avatar asset.',
        '', 'Official references:',
        'https://wiki.resonite.com/OSC',
        'https://wiki.resonite.com/Component:OSC_Receiver',
        'https://wiki.resonite.com/Component:OSC_Value',
        'https://wiki.resonite.com/Component:OSC_Field',
        'https://wiki.resonite.com/ProtoFlux:SetUserScale',
        'https://wiki.resonite.com/ProtoFlux:UserRootGlobalScale']
    return '\n'.join(lines)
