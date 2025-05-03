from typing import TypedDict, Tuple, List, Dict, Any
import struct

class Point3(TypedDict):
    x               : float
    y               : float
    z               : float

class PacketHeader(TypedDict):
    function_code   : str
    mac_address     : str
    time            : int
    battery         : int
    temperature     : int

class PacketLocation(TypedDict):
    latitude        : float
    longitude       : float
    altitude        : float
    speed           : float

# 3.4028234663852886e+38
class PacketADS(TypedDict):
    rectification   : float
    vibration       : float
    voltage_3v      : float
    voltage_100v    : float

class PacketIMU(TypedDict):
    acceleration    : Point3
    accelerometer   : Point3
    angular_velocity: Point3
    gravity         : Point3
    magnetometer    : Point3
    orientation     : Point3

class PacketCapacity(TypedDict):
    GS: float
    GP: float
    GC: float
    GW: float
    TS: float
    TP: float
    TC: float
    TW: float

def unpackStruct(struct_format: str, struct_bytes: bytes):
    struct_size: int = struct.calcsize(struct_format)
    values = struct.unpack(struct_format, struct_bytes[:struct_size])
    return values, struct_bytes[struct_size:]

# Separate functions to read specific packet types
def read_location(location_bytes: bytes) -> tuple[PacketLocation, bytes]:
    values, unprocessed_bytes = unpackStruct('<4f', location_bytes)
    return PacketLocation(latitude=values[0], longitude=values[1], altitude=values[2], speed=values[3]), unprocessed_bytes

def read_ads(ads_bytes: bytes) -> tuple[PacketADS, bytes]:
    values, unprocessed_bytes = unpackStruct('<4f', ads_bytes)
    return PacketADS(rectification=values[0], vibration=values[1], voltage_3v=values[2], voltage_100v=values[3]), unprocessed_bytes

def read_capacity(capacity_bytes: bytes) -> tuple[PacketCapacity, bytes]:
    values, unprocessed_bytes = unpackStruct('<8f', capacity_bytes)
    return PacketCapacity(
        GS=values[0], GP=values[1], GC=values[2], GW=values[3],
        TS=values[4], TP=values[5], TC=values[6], TW=values[7],
    ), unprocessed_bytes

def read_imu(data: bytes) -> tuple[PacketIMU, bytes]:
    fields: List[Point3] = []

    for _ in range(6):
        field_data = struct.unpack('<3f', data[:12])
        fields.append(Point3(x=field_data[0], y=field_data[1], z=field_data[2]))
        data = data[12:]

    imu_data = PacketIMU(
        acceleration=fields[0],
        accelerometer=fields[1],
        angular_velocity=fields[2],
        gravity=fields[3],
        magnetometer=fields[4],
        orientation=fields[5],
    )
    return imu_data, data

SECTION_CALLBACKS: Dict[str, Any] = {
      'B' : read_location
    , 'C' : read_imu
    , 'D' : read_capacity
    , 'E' : read_ads
    }

def read_packet_section(sections_bytes: bytes) ->  tuple[PacketIMU | PacketLocation | PacketADS | PacketCapacity | None, bytes]:
    section_code: str = sections_bytes[:1].decode('ascii');
    sections_bytes = sections_bytes[1:];
    if section_code in SECTION_CALLBACKS:
        section_callback = SECTION_CALLBACKS[section_code]
        return section_callback(sections_bytes);

    return None, sections_bytes;

# first 2 chars are the function and next 12 bytes are the mac address as hex.
def read_function(hexencoded: str) -> Tuple[str, str, bytes]:
    return hexencoded[:2], hexencoded[2:14], bytes.fromhex(hexencoded[14:])

# returns battery, temperature, timestamp, node type and the remaining unprocessed bytes
def read_status(status_bytes: bytes) -> Tuple[int, int, int, bytes]:
    header_format: str = '<IBb' 
    header_size: int = struct.calcsize(header_format)
    values = struct.unpack(header_format, status_bytes[:header_size])
    return values[0], values[1], values[2], status_bytes[header_size:]  # Get the remaining bytes

def read_packet_hex(hexencoded: str) -> tuple[PacketHeader, List[PacketIMU | PacketLocation | PacketADS | PacketCapacity | None], bytes]:
    # Unpack the fields using struct
    function_code, mac, packet_bytes = read_function(hexencoded)
    time, battery, temperature, packet_bytes = read_status(packet_bytes)

    # Create the PacketHeader instance
    packet_header = PacketHeader(
        function_code   = function_code ,
        mac_address     = mac           ,
        battery         = battery       ,
        temperature     = temperature   ,
        time            = time          ,
    )
    print(packet_header)
    packet_sections: List[PacketIMU | PacketLocation | PacketADS | PacketCapacity] = []
    if packet_header["function_code"] == "F1":
        while len(packet_bytes):
            packet_section, packet_bytes = read_packet_section(packet_bytes)
            if packet_section:
                packet_sections.append(packet_section)
                print(packet_section)

    return packet_header, packet_sections, packet_bytes


