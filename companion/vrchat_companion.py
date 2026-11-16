#!/usr/bin/env python3
"""Mid's Den -> VRChat avatar eye-height companion using local or private-LAN OSC."""

from __future__ import annotations

import argparse
import ipaddress
import json
import math
import os
from pathlib import Path
import socket
import struct
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


from measurement_format import format_measurement
from growth_options import normalize as growth_options

DEFAULT_URL = "https://mid.shardware.net"
DEFAULT_POLL_SECONDS = 5
MIN_METERS = 0.01
MAX_METERS = 10000.0  # OSC accepts this range; official support remains 0.1–100 m.
OSC_ADDRESS = "/avatar/eyeheight"
DEFAULT_OSC_HOST = "127.0.0.1"


def config_path() -> Path:
    # Keep settings beside the launcher and runtime so the extracted folder is portable.
    return Path(__file__).resolve().parent / "config.json"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Keep companion reads on the configured Mid's Den host.
        raise HTTPError(req.full_url, code, "Redirect refused", headers, fp)


def validate_server_url(value: str) -> str:
    url = value.strip().rstrip("/")
    parsed = urlsplit(url)
    local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not local_http:
        raise ValueError("Use an https:// URL. Plain HTTP is allowed only for localhost testing.")
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Enter a base URL without a username, password, query, or fragment.")
    return url


def validate_osc_host(value: str) -> str:
    host = value.strip()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError("Enter a private IPv4 address, or 127.0.0.1 for VRChat on this computer.") from None
    if address.version != 4 or not (address.is_private or address.is_loopback) or address.is_multicast or address.is_unspecified:
        raise ValueError("OSC can only be sent to a private IPv4 address or 127.0.0.1.")
    return str(address)


def save_config(config: dict, path: Path | None = None) -> Path:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass  # Windows ACLs inherit from the signed-in user's profile directory.
    temporary.replace(target)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return target


def load_config(path: Path | None = None) -> dict:
    target = path or config_path()
    data = json.loads(target.read_text(encoding="utf-8"))
    base_url = validate_server_url(str(data.get("serverUrl", "")))
    port = int(data.get("oscPort", 9000))
    query_port = int(data.get("oscQueryPort", 9001))
    osc_host = validate_osc_host(str(data.get("oscHost", DEFAULT_OSC_HOST)))
    if not 1 <= port <= 65535:
        raise ValueError("OSC port must be between 1 and 65535.")
    if not 1 <= query_port <= 65535:
        raise ValueError("OSCQuery port must be between 1 and 65535.")
    config = {"serverUrl": base_url, "oscHost": osc_host, "oscPort": port,
              "oscQueryPort": query_port}
    config['targetApp'] = data.get('targetApp','vrchat') if data.get('targetApp') in ('vrchat','resonite','chilloutvr') else 'vrchat'
    config['oscDestinations'] = data.get('oscDestinations',{}) if isinstance(data.get('oscDestinations'),dict) else {}
    config['profiles'] = data.get('profiles', {}) if isinstance(data.get('profiles'), dict) else {}
    config['growthOptions'] = growth_options(data.get('growthOptions'))
    config['smoothGrowth'] = data.get('smoothGrowth',False) is True
    config['syncHeight'] = data.get('syncHeight', True) is True
    config['mappingVersion'] = data.get('mappingVersion', 0)
    if "token" in data or "metersPerUnit" in data:
        save_config(config, target)
    return config


def configure(path: Path | None = None, ask_server_url: bool = True) -> Path:
    try:
        current = json.loads((path or config_path()).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        current = {}
    if ask_server_url:
        entered_url = input(f"Mid's Den URL [{current.get('serverUrl', DEFAULT_URL)}]: ").strip()
        server_url = validate_server_url(entered_url or current.get("serverUrl", DEFAULT_URL))
    else:
        server_url = validate_server_url(str(current.get("serverUrl", DEFAULT_URL)))
        print(f"Using Mid's Den: {server_url}")
    osc_host = input(
        f"VRChat device IP [{current.get('oscHost', DEFAULT_OSC_HOST)}] "
        "(127.0.0.1 for this computer, or its private network IP): "
    ).strip()
    osc_host = validate_osc_host(osc_host or current.get("oscHost", DEFAULT_OSC_HOST))
    entered_port = input(f"VRChat OSC receive port [{current.get('oscPort', 9000)}]: ").strip()
    osc_port = int(entered_port or current.get("oscPort", 9000))
    if not 1 <= osc_port <= 65535:
        raise ValueError("OSC port must be between 1 and 65535.")
    config = {
        "serverUrl": server_url,
        "oscHost": osc_host,
        "oscPort": osc_port,
        "oscQueryPort": int(current.get("oscQueryPort", 9001)),
    }
    config['targetApp'] = current.get('targetApp','vrchat') if current.get('targetApp') in ('vrchat','resonite','chilloutvr') else 'vrchat'
    config['oscDestinations'] = current.get('oscDestinations',{}) if isinstance(current.get('oscDestinations'),dict) else {}
    config['profiles'] = current.get('profiles', {}) if isinstance(current.get('profiles'), dict) else {}
    config['growthOptions'] = growth_options(current.get('growthOptions'))
    config['smoothGrowth'] = current.get('smoothGrowth',False) is True
    config['syncHeight'] = current.get('syncHeight', True) is True
    config['mappingVersion'] = current.get('mappingVersion', 0)
    target = save_config(config, path)
    print(f"Saved companion settings to {target}")
    return target


def _osc_string(value: str) -> bytes:
    raw = value.encode("utf-8") + b"\0"
    return raw + b"\0" * ((-len(raw)) % 4)


def encode_eyeheight_packet(meters: float) -> bytes:
    value = float(meters)
    if not math.isfinite(value) or not MIN_METERS <= value <= MAX_METERS:
        raise ValueError(f"Eye height must be between {MIN_METERS} and {MAX_METERS} meters.")
    return _osc_string(OSC_ADDRESS) + _osc_string(",f") + struct.pack(">f", value)


def send_eyeheight(meters: float, port: int = 9000, host: str = DEFAULT_OSC_HOST) -> None:
    packet = encode_eyeheight_packet(meters)
    host = validate_osc_host(host)
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError("OSC port must be between 1 and 65535.")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as osc:
        # OSC stays on this computer or the user's local network.
        osc.sendto(packet, (host, int(port)))


def _request(config: dict, path: str):
    base_url = validate_server_url(config["serverUrl"])
    headers = {
        "Accept": "application/json",
        "User-Agent": "MidsDen-VRChat-Companion/1.0",
    }
    request = Request(f"{base_url}{path}", headers=headers, method="GET")
    opener = build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=12) as response:
            if response.status == 204:
                return None
            raw = response.read(1_048_577)
            if len(raw) > 1_048_576:
                raise RuntimeError("Server response was too large.")
            return json.loads(raw.decode("utf-8")) if raw else None
    except HTTPError as err:
        if err.code == 204:
            return None
        raise RuntimeError(f"Mid's Den returned HTTP {err.code}.") from None
    except (URLError, TimeoutError, OSError) as err:
        raise RuntimeError(f"Could not reach Mid's Den: {getattr(err, 'reason', err)}") from None


def fetch_current_height(config: dict) -> float | None:
    response = _request(config, "/api/vrchat/height")
    if response is None:
        return None
    try:
        height = float(response["heightMeters"])
    except (KeyError, TypeError, ValueError):
        raise RuntimeError("Mid's Den returned an invalid height.") from None
    if not math.isfinite(height) or height <= 0:
        raise RuntimeError("Mid's Den returned an invalid height.")
    return min(MAX_METERS, max(MIN_METERS, height))


def vrchat_osc_ready(host: str = DEFAULT_OSC_HOST, query_port: int = 9001) -> bool:
    """Check the VRChat OSCQuery endpoint so updates wait while OSC is off."""
    try:
        host = validate_osc_host(host)
        request = Request(
            f"http://{host}:{int(query_port)}/avatar/eyeheight",
            headers={"Accept": "application/json"},
        )
        with urlopen(request, timeout=1.5) as response:
            if response.status != 200:
                return False
            return isinstance(json.loads(response.read(1_048_577).decode("utf-8")), dict)
    except (OSError, ValueError, URLError, TimeoutError):
        return False


def run(config: dict, once: bool = False) -> int:
    if config.get('targetApp') in ('resonite','chilloutvr'):
        print('Use the desktop companion for Resonite or ChilloutVR profiles.',file=sys.stderr)
        return 1
    import avatar_mapping as mappings
    sender = mappings.ChangedSender()
    previous_discovery = False
    reconnect = 0
    last_state = None
    last_height = None
    while True:
        try:
            meters = fetch_current_height(config)
            if meters is None:
                if last_state != "height-unconfigured":
                    print("Set a starting height in Mid's Den to begin.")
                last_state = "height-unconfigured"
            else:
                discovery = None if once else mappings.discover(config, browse=False)
                if discovery and not previous_discovery: reconnect += 1
                previous_discovery = bool(discovery)
                sender.begin((config['oscHost'], config['oscPort'], mappings.profile_key(discovery), reconnect))
                sender.send(config, mappings.eye_height_preset(), {'value': meters})
                if last_state != "sending" or last_height != meters:
                    print(f"Sending height: {format_measurement(meters, 'm')} to {config['oscHost']}:{config['oscPort']} (OSC UDP).")
                last_height = meters
                last_state = "sending"
        except (RuntimeError, ValueError, OSError) as err:
            print(f"Companion: {err}", file=sys.stderr)
            if once:
                return 1
        if once:
            return 0
        time.sleep(DEFAULT_POLL_SECONDS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Mid's Den's current height to VRChat over OSC.")
    parser.add_argument("--configure", action="store_true", help="set the Mid's Den URL and VRChat device IP")
    parser.add_argument("--once", action="store_true", help="check once and exit (useful for diagnostics)")
    parser.add_argument("--test-osc", nargs="?", const=2.0, type=float, metavar="METERS",
                        help="send a test scale to VRChat (default: 2m; does not contact Mid's Den)")
    parser.add_argument("--osc-host", default=DEFAULT_OSC_HOST, help="private IPv4 address of the VRChat device for --test-osc")
    parser.add_argument("--osc-port", type=int, default=9000, help="VRChat OSC port for --test-osc")
    args = parser.parse_args()
    try:
        if args.test_osc is not None:
            host = validate_osc_host(args.osc_host)
            send_eyeheight(args.test_osc, args.osc_port, host)
            print(f"Sent OSC eye-height test: {args.test_osc:g} m to {host}:{args.osc_port}.")
            return 0
        if args.configure:
            configure()
            return 0
        if not config_path().exists():
            configure(ask_server_url=False)
        settings = load_config()
        return run(settings, once=args.once)
    except (OSError, ValueError, json.JSONDecodeError) as err:
        print(f"Companion setup error: {err}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nCompanion stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
