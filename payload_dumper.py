#!/usr/bin/env python
import struct
import hashlib
import bz2
import sys

try:
    import lzma
except ImportError:
    from backports import lzma

import update_metadata_pb2 as um

flatten = lambda l: [item for sublist in l for item in sublist]

def u32(x):
    return struct.unpack('>I', x)[0]

def u64(x):
    return struct.unpack('>Q', x)[0]

def verify_contiguous(exts):
    blocks = 0

    for ext in exts:
        if ext.start_block != blocks:
            return False

        blocks += ext.num_blocks

    return True

def data_for_op(op):
    p.seek(data_offset + op.data_offset)
    data = p.read(op.data_length)

    # assert hashlib.sha256(data).digest() == op.data_sha256_hash, 'operation data hash mismatch'

    if op.type == op.REPLACE_XZ:
        dec = lzma.LZMADecompressor()
        data = dec.decompress(data) 
    elif op.type == op.REPLACE_BZ:
        dec = bz2.BZ2Decompressor()
        data = dec.decompress(data) 

    return data

def dump_part(part):
    print(part.partition_name)

    out_file = open('output/%s.img' % part.partition_name, 'wb')
    h = hashlib.sha256()

    for op in part.operations:
        data = data_for_op(op)
        h.update(data)
        out_file.write(data)

    # assert h.digest() == part.new_partition_info.hash, 'partition hash mismatch'

p = open(sys.argv[1], 'rb')

magic = p.read(4)
assert magic == b'CrAU'

file_format_version = u64(p.read(8))
assert file_format_version == 2

manifest_size = u64(p.read(8))

metadata_signature_size = 0

if file_format_version > 1:
    metadata_signature_size = u32(p.read(4))

manifest = p.read(manifest_size)
metadata_signature = p.read(metadata_signature_size)

data_offset = p.tell()

dam = um.DeltaArchiveManifest()
dam.ParseFromString(manifest)

for part in dam.partitions:
    # for op in part.operations:
    #     assert op.type in (op.REPLACE, op.REPLACE_BZ, op.REPLACE_XZ), \
    #             'unsupported op'

    # extents = flatten([op.dst_extents for op in part.operations])
    # assert verify_contiguous(extents), 'operations do not span full image'

    dump_part(part)