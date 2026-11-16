import ipaddress

from functools import lru_cache
from pathlib import Path

from fastapi import Request

# -----------------------------------------------------------------------------
# Client address and Singapore GPS helpers (geo.py)
# -----------------------------------------------------------------------------

# Rough bounding box around the main island and its islets
SG_MIN_LAT, SG_MAX_LAT = 1.15, 1.48
SG_MIN_LON, SG_MAX_LON = 103.60, 104.10

SG_ZONE_FILE = Path(__file__).parent / "data" / "sg.zone.txt"

def parse_ip(value: str | None):
    if not value:
        return None
    try:
        address = ipaddress.ip_address(value.strip().strip("[]"))
    except ValueError:
        return None
    # An IPv4 address carried inside IPv6 (::ffff:a.b.c.d) is treated as the IPv4 address
    if address.version == 6 and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address

def client_ip(request: Request) -> str | None:
    # First address of X-Forwarded-For when present, otherwise the socket address
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        # A header that does not hold an IP address must not hide the real socket address
        if parse_ip(first) is not None:
            return first
    return request.client.host if request.client else None

def coordinates_in_singapore(latitude: float, longitude: float) -> bool:
    return SG_MIN_LAT <= latitude <= SG_MAX_LAT and SG_MIN_LON <= longitude <= SG_MAX_LON

@lru_cache(maxsize=1)
def _sg_networks() -> tuple:
    # Parsed once per process; the zone file does not change at runtime
    with SG_ZONE_FILE.open() as f:
        return tuple(ipaddress.ip_network(line.strip()) for line in f if line.strip())

def is_singapore_ip(address) -> bool:
    # Private/local addresses (e.g. 192.168.x.x, 10.x.x.x, 127.x.x.x) are treated as on-campus and allowed
    if address is None or address.is_private:
        return True
    return any(address in network for network in _sg_networks())
