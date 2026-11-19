"""Resonite's native generic OSC input; paths belong to the user's in-world receiver."""
from urllib.parse import quote

PROFILE='resonite'
HEIGHT_PATH = '/midsden/height'
SCALE_PATH = '/midsden/scale'
DEFAULT_PORT=9002  # Our receiver convention, not a port mandated by Resonite.


def address(value):
    path=str(value).strip()
    if not path:raise ValueError('Enter an OSC receiver path.')
    if not path.startswith('/'):path='/midsden/'+path
    if not 1<len(path)<=256 or any(c.isspace() or ord(c)<32 or c in '*?[]{},#' for c in path):
        raise ValueError('Enter an exact OSC path, such as /midsden/tail.')
    if path.startswith('/avatar/'):
        raise ValueError('Use a Resonite receiver path, such as /midsden/height.')
    return path


def height_preset():
    return {
        'source': 'height', 'target': HEIGHT_PATH, 'kind': 'float',
        'mode': 'value', 'enabled': True, 'smooth': True, 'platform': PROFILE,
    }


def parameter_options(sources):
    result = [{'name': 'Avatar height', 'address': HEIGHT_PATH, 'source': 'height', 'kind': 'float', 'writable': True}]
    result.extend({
        'name': source['name'], 'address': '/midsden/measurements/' + quote(source['id'], safe='-_'),
        'source': source['id'], 'kind': 'float', 'writable': True,
    } for source in sources if source['id'] != 'height')
    return result

