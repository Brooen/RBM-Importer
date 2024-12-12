import struct


def read_u8(file):
    return int.from_bytes(file.read(1), 'little')


def read_s8(file):
    return int.from_bytes(file.read(1), 'little', signed=True)


def read_u16(file):
    return int.from_bytes(file.read(2), 'little')


def read_s16(file):
    return int.from_bytes(file.read(2), 'little', signed=True)


def read_u32(file):
    return int.from_bytes(file.read(4), 'little')


def read_s32(file):
    return int.from_bytes(file.read(4), 'little', signed=True)


def read_float(file):
    return struct.unpack('f', file.read(4))[0]


def read_string(file, length: int):
    return file.read(length).decode('utf-8')


def hex_to_float(hex_value):
    packed = struct.pack('>I', hex_value)
    return struct.unpack('>f', packed)[0]
