"""Scalar OSC mappings, VRChat discovery and explicit Resonite receiver paths."""
import copy
import ipaddress
import json
import math
import socket
import struct
import time
from urllib.request import Request, build_opener
import vrchat_companion as core
import resonite
try:
    from zeroconf import Zeroconf, ServiceBrowser, ServiceListener, IPVersion
except ImportError:
    Zeroconf = None

PREFIX = '/avatar/parameters/'
KINDS = {'f': 'float', 'i': 'int', 'T': 'bool', 'F': 'bool'}


def parameter_address(value):
    address = str(value).strip()
    if not address.startswith('/'):
        address = PREFIX + address
    if address != '/avatar/eyeheight' and (not address.startswith(PREFIX) or not address[len(PREFIX):] or len(address) > 256):
        raise ValueError('Choose an avatar parameter, such as /avatar/parameters/TailSize.')
    if any(ord(c) < 32 or c in '*?[]{},' for c in address):
        raise ValueError('Use an exact OSC parameter address without wildcard characters.')
    return address


def validate_mapping(mapping):
    result = copy.deepcopy(mapping)
    if result.get('platform','vrchat') not in ('vrchat','resonite'):raise ValueError('Choose VRChat or Resonite.')
    result['target'] = resonite.address(result.get('target','')) if result.get('platform')=='resonite' else parameter_address(result.get('target', ''))
    if not result.get('source') or result.get('kind') not in ('float', 'int', 'bool'):
        raise ValueError('Choose a website measurement and OSC value type.')
    if result['target'] == '/avatar/eyeheight' and (result['source'] != 'height' or result['kind'] != 'float'):
        raise ValueError('Eye height uses Height in meters and the float type.')
    mode = result.get('mode', 'range')
    if mode not in ('value', 'ratio', 'range', 'threshold'):
        raise ValueError('Choose Value, Growth ratio, Map range, or Threshold.')
    if result['kind'] == 'bool' and mode != 'threshold':
        raise ValueError('Boolean parameters use a threshold.')
    if result['kind'] != 'bool' and mode == 'threshold':
        raise ValueError('Threshold mode requires a boolean parameter.')
    keys = ('inputMin','inputMax','outputMin','outputMax') if mode == 'range' else ('threshold',) if mode == 'threshold' else ()
    for key in keys:
        result[key] = float(result.get(key, 0))
        if not math.isfinite(result[key]):
            raise ValueError('Mapping limits must be finite numbers.')
    if mode == 'range' and result['inputMax'] <= result['inputMin']:
        raise ValueError('The website maximum must be greater than its minimum.')
    result['mode'] = mode
    result['enabled'] = result.get('enabled', True) is True
    if 'smooth' in result:result['smooth']=result['smooth'] is True
    return result


def mapped_value(mapping, source):
    mapping = validate_mapping(mapping)
    value = float(source['value'])
    if not math.isfinite(value):
        raise ValueError('The measurement is not finite.')
    mode = mapping['mode']
    if mode == 'ratio':
        initial = float(source['originalValue'])
        if not math.isfinite(initial) or initial <= 0:
            raise ValueError('Growth ratio needs a positive starting amount.')
        value /= initial
    elif mode == 'range':
        ratio = max(0., min(1., (value-mapping['inputMin'])/(mapping['inputMax']-mapping['inputMin'])))
        value = mapping['outputMin'] + ratio*(mapping['outputMax']-mapping['outputMin'])
    elif mode == 'threshold':
        return value >= mapping['threshold']
    if not math.isfinite(value):
        raise ValueError('The mapped value is outside the numeric range.')
    if mapping['kind'] == 'int':
        value = math.floor(value+.5) if value >= 0 else math.ceil(value-.5)
        if not -(2**31) <= value < 2**31:
            raise ValueError('The mapped integer exceeds OSC’s 32-bit range.')
    elif abs(value) > 3.4028234e38:
        raise ValueError('The mapped float exceeds OSC’s 32-bit range.')
    if mapping['target'] == '/avatar/eyeheight':
        value = max(core.MIN_METERS, min(core.MAX_METERS, value))
    return value


def encode_parameter(address, kind, value, platform='vrchat'):
    address = resonite.address(address) if platform=='resonite' else parameter_address(address)
    if platform=='resonite' and kind=='bool':kind='int';value=int(bool(value))
    if kind == 'bool':
        tag, payload = ('T' if value else 'F'), b''
    elif kind == 'int':
        tag, payload = 'i', struct.pack('>i', int(value))
    elif kind == 'float':
        tag, payload = 'f', struct.pack('>f', float(value))
    else:
        raise ValueError('Unsupported OSC value type.')
    return core._osc_string(address) + core._osc_string(','+tag) + payload


def send_mapping(config, mapping, source):
    value = mapped_value(mapping, source)
    packet = encode_parameter(mapping['target'], mapping['kind'], value, mapping.get('platform','vrchat'))
    host = core.validate_osc_host(config['oscHost'])
    port = int(config['oscPort'])
    if not 1 <= port <= 65535:
        raise ValueError('OSC port must be between 1 and 65535.')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(packet, (host, port))
    return value


def parse_tree(tree):
    writable, all_parameters = {}, {}
    avatar = None
    eye_height=None;scaling_allowed=None
    def walk(node, path='/', inherited=0, depth=0):
        nonlocal avatar,eye_height,scaling_allowed
        if not isinstance(node, dict) or depth > 32:
            return
        path = node.get('FULL_PATH', path)
        try: access = int(node.get('ACCESS', inherited))
        except (ValueError, TypeError): access = 0
        values = node.get('VALUE', [])
        if path=='/avatar/eyeheight' and isinstance(values,list) and values:
            try:
                candidate=float(values[0])
                if math.isfinite(candidate) and core.MIN_METERS<=candidate<=core.MAX_METERS:eye_height=candidate
            except (TypeError,ValueError):pass
        if path=='/avatar/eyeheightscalingallowed' and isinstance(values,list) and values and type(values[0]) is bool:scaling_allowed=values[0]
        if path == '/avatar/change':
            value = values[0] if isinstance(values, list) and values else values
            if isinstance(value, str) and value.startswith('avtr_'):
                avatar = value
        if isinstance(path, str) and path.startswith(PREFIX):
            kind = KINDS.get(str(node.get('TYPE','')).lstrip(','))
            all_parameters[path] = {'kind': kind, 'writable': bool(access & 2)}
            if kind and access & 2:
                writable[path] = kind
        contents = node.get('CONTENTS', {})
        if isinstance(contents, dict):
            for key, child in contents.items():
                walk(child, str(path).rstrip('/')+'/'+key, access, depth+1)
    walk(tree)
    return {'avatar': avatar, 'parameters': writable, 'allParameters': all_parameters, 'eyeHeight':eye_height,'scalingAllowed':scaling_allowed}


def query_json(host, port, path='/'):
    host = core.validate_osc_host(host)
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError('Discovery port must be between 1 and 65535.')
    request = Request(f'http://{host}:{port}{path}', headers={'Accept':'application/json'})
    with build_opener(core.NoRedirect).open(request, timeout=1.5) as response:
        raw = response.read(2_097_153)
        if len(raw) > 2_097_152:
            raise ValueError('OSCQuery response is too large.')
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError('OSCQuery returned an invalid tree.')
        return value


def mdns_ports(host, wait=1.2):
    if Zeroconf is None:
        return []
    ports = set()
    allowed = {core.validate_osc_host(host)}
    if ipaddress.ip_address(host).is_loopback:
        import ifaddr
        allowed.update(address.ip for adapter in ifaddr.get_adapters() for address in adapter.ips if isinstance(address.ip,str))
    class Listener(ServiceListener):
        def add_service(self, zc, service_type, name):
            if 'vrchat' not in name.lower(): return
            info = zc.get_service_info(service_type, name, timeout=700)
            if info and allowed.intersection(info.parsed_addresses()): ports.add(info.port)
        def update_service(self, zc, service_type, name): self.add_service(zc, service_type, name)
        def remove_service(self, *_args): pass
    zc = Zeroconf(ip_version=IPVersion.V4Only)
    browser = None
    try:
        browser = ServiceBrowser(zc, '_oscjson._tcp.local.', Listener())
        time.sleep(wait)
        return sorted(ports)
    finally:
        if browser: browser.cancel()
        zc.close()


def discover(config, known_port=None, browse=True):
    host = core.validate_osc_host(config['oscHost'])
    ports = [known_port] if known_port else []
    if browse:
        try: ports.extend(mdns_ports(host))
        except (OSError, RuntimeError): pass
    ports.append(config.get('oscQueryPort', 9001))
    for port in dict.fromkeys(p for p in ports if p):
        try:
            tree = query_json(host, port)
            result = parse_tree(tree)
            if result['parameters'] or result['avatar'] or result['eyeHeight'] is not None:
                result['queryPort'] = port
                return result
        except (OSError, ValueError):
            continue
    return None


def fetch_measurements(config):
    data = core._request(config, '/api/vrchat/measurements')
    if data is None:
        return []
    if not isinstance(data, dict) or not isinstance(data.get('measurements'), list):
        raise RuntimeError('Mid’s Den returned invalid measurements.')
    result = []
    for item in data['measurements']:
        try:
            value, initial = float(item['value']), float(item['originalValue'])
            if math.isfinite(value) and math.isfinite(initial):
                result.append({**item, 'id': str(item['id']), 'value': value, 'originalValue': initial})
        except (KeyError, TypeError, ValueError): pass
    return result


def can_send(item, sources, discovery):
    if item.get('source') not in sources:
        return False
    if item.get('platform')=='resonite':return True
    if item.get('target') == '/avatar/eyeheight':
        return True
    if discovery is not None:
        return discovery.get('parameters',{}).get(item.get('target')) == item.get('kind')
    return True


def profile_key(discovery):
    return (discovery or {}).get('avatar') or 'manual'


def eye_height_preset(enabled=True):
    return {'source':'height','target':'/avatar/eyeheight','kind':'float','mode':'value','enabled':enabled}


def migrate_profiles(config):
    if config.get('mappingVersion',0) >= 2: return
    profiles=config.setdefault('profiles',{})
    profiles.setdefault('manual',[])
    for key,items in profiles.items():
        if key=='resonite':continue
        if not any(item.get('target')=='/avatar/eyeheight' for item in items):
            items.insert(0,eye_height_preset(config.get('syncHeight',True)))
    config['mappingVersion']=2
    config.pop('syncHeight',None)


class ChangedSender:
    """Deduplicate the encoded OSC value, only remembering successful UDP writes."""
    def __init__(self):
        self.context=None
        self.packets={}

    def begin(self,context):
        if context != self.context:
            self.context=context
            self.packets.clear()

    def prune(self,targets):
        self.packets={k:v for k,v in self.packets.items() if k in targets}

    def send(self,config,item,source):
        value=mapped_value(item,source)
        packet=encode_parameter(item['target'],item['kind'],value,item.get('platform','vrchat'))
        if self.packets.get(item['target'])==packet:return False
        send_mapping(config,item,source)
        self.packets[item['target']]=packet
        return True
