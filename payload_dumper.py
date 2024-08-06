#!/usr/bin/env python3
import struct
import hashlib
import bz2
import sys
import argparse
import bsdiff4
import io
import os
import brotli
import zipfile
try:
    import lzma
except ImportError:
    from backports import lzma

import update_metadata_pb2 as um

BSDF2_MAGIC = b'BSDF2'

flatten = lambda l: [item for sublist in l for item in sublist]

def u32(x):
    return struct.unpack('>I', x)[0]

def u64(x):
    return struct.unpack('>Q', x)[0]

def bsdf2_decompress(alg, data):
    if alg == 0:
        return data
    elif alg == 1:
        return bz2.decompress(data)
    elif alg == 2:
        return brotli.decompress(data)

# Adapted from bsdiff4.read_patch
def bsdf2_read_patch(fi):
    """read a bsdiff/BSDF2-format patch from stream 'fi'
    """
    magic = fi.read(8)
    if magic == bsdiff4.format.MAGIC:
        # bsdiff4 uses bzip2 (algorithm 1)
        alg_control = alg_diff = alg_extra = 1
    elif magic[:5] == BSDF2_MAGIC:
        alg_control = magic[5]
        alg_diff = magic[6]
        alg_extra = magic[7]
    else:
        raise ValueError("incorrect magic bsdiff/BSDF2 header")

    # length headers
    len_control = bsdiff4.core.decode_int64(fi.read(8))
    len_diff = bsdiff4.core.decode_int64(fi.read(8))
    len_dst = bsdiff4.core.decode_int64(fi.read(8))

    # read the control header
    bcontrol = bsdf2_decompress(alg_control, fi.read(len_control))
    tcontrol = [(bsdiff4.core.decode_int64(bcontrol[i:i + 8]),
                 bsdiff4.core.decode_int64(bcontrol[i + 8:i + 16]),
                 bsdiff4.core.decode_int64(bcontrol[i + 16:i + 24]))
                for i in range(0, len(bcontrol), 24)]

    # read the diff and extra blocks
    bdiff = bsdf2_decompress(alg_diff, fi.read(len_diff))
    bextra = bsdf2_decompress(alg_extra, fi.read())
    return len_dst, tcontrol, bdiff, bextra

def verify_contiguous(exts):
    blocks = 0

    for ext in exts:
        if ext.start_block != blocks:
            return False

        blocks += ext.num_blocks

    return True

def data_for_op(op,out_file,old_file):
    args.payloadfile.seek(data_offset + op.data_offset)
    data = args.payloadfile.read(op.data_length)

    # assert hashlib.sha256(data).digest() == op.data_sha256_hash, 'operation data hash mismatch'

    if op.type == op.REPLACE_XZ:
        dec = lzma.LZMADecompressor()
        data = dec.decompress(data)
        out_file.seek(op.dst_extents[0].start_block*block_size)
        out_file.write(data)
    elif op.type == op.REPLACE_BZ:
        dec = bz2.BZ2Decompressor()
        data = dec.decompress(data)
        out_file.seek(op.dst_extents[0].start_block*block_size)
        out_file.write(data)
    elif op.type == op.REPLACE:
        out_file.seek(op.dst_extents[0].start_block*block_size)
        out_file.write(data)
    elif op.type == op.SOURCE_COPY:
        if not args.diff:
            print ("SOURCE_COPY supported only for differential OTA")
            sys.exit(-2)
        out_file.seek(op.dst_extents[0].start_block*block_size)
        for ext in op.src_extents:
            old_file.seek(ext.start_block*block_size)
            data = old_file.read(ext.num_blocks*block_size)
            out_file.write(data)
    elif op.type in (op.SOURCE_BSDIFF, op.BROTLI_BSDIFF):
        if not args.diff:
            print ("BSDIFF supported only for differential OTA")
            sys.exit(-3)
        out_file.seek(op.dst_extents[0].start_block*block_size)
        tmp_buff = io.BytesIO()
        for ext in op.src_extents:
            old_file.seek(ext.start_block*block_size)
            old_data = old_file.read(ext.num_blocks*block_size)
            tmp_buff.write(old_data)
        tmp_buff.seek(0)
        old_data = tmp_buff.read()
        tmp_buff.seek(0)
        tmp_buff.write(bsdiff4.core.patch(old_data, *bsdf2_read_patch(io.BytesIO(data))))
        n = 0;
        tmp_buff.seek(0)
        for ext in op.dst_extents:
            tmp_buff.seek(n*block_size)
            n += ext.num_blocks
            data = tmp_buff.read(ext.num_blocks*block_size)
            out_file.seek(ext.start_block*block_size)
            out_file.write(data)
    elif op.type == op.ZERO:
        for ext in op.dst_extents:
            out_file.seek(ext.start_block*block_size)
            out_file.write(b'\x00' * ext.num_blocks*block_size)
    else:
        print ("Unsupported type = %d" % op.type)
        sys.exit(-1)

    return data

def dump_part(part):
    sys.stdout.write("Processing %s partition" % part.partition_name)
    sys.stdout.flush()

    out_file = open('%s/%s.img' % (args.out, part.partition_name), 'wb')
    h = hashlib.sha256()

    if args.diff:
        old_file = open('%s/%s.img' % (args.old, part.partition_name), 'rb')
    else:
        old_file = None

    for op in part.operations:
        data = data_for_op(op,out_file,old_file)
        sys.stdout.write(".")
        sys.stdout.flush()

    print("Done")


parser = argparse.ArgumentParser(description='OTA payload dumper')
parser.add_argument('payloadfile', type=argparse.FileType('rb'),
                    help='payload file name')
parser.add_argument('--out', default='output',
                    help='output directory (defaul: output)')
parser.add_argument('--diff',action='store_true',
                    help='extract differential OTA, you need put original images to old dir')
parser.add_argument('--old', default='old',
                    help='directory with original images for differential OTA (defaul: old)')
parser.add_argument('--images', default="",
                    help='images to extract (default: empty)')
args = parser.parse_args()

#Check for --out directory exists
if not os.path.exists(args.out):
    os.makedirs(args.out)

if zipfile.is_zipfile(args.payloadfile):
    args.payloadfile = zipfile.ZipFile(args.payloadfile).open("payload.bin")
args.payloadfile.seek(0)

magic = args.payloadfile.read(4)
assert magic == b'CrAU'

file_format_version = u64(args.payloadfile.read(8))
assert file_format_version == 2

manifest_size = u64(args.payloadfile.read(8))

metadata_signature_size = 0

if file_format_version > 1:
    metadata_signature_size = u32(args.payloadfile.read(4))

manifest = args.payloadfile.read(manifest_size)
metadata_signature = args.payloadfile.read(metadata_signature_size)

data_offset = args.payloadfile.tell()

dam = um.DeltaArchiveManifest()
dam.ParseFromString(manifest)
block_size = dam.block_size

if args.images == "":
    for part in dam.partitions:
        dump_part(part)
else:
    images = args.images.split(",")
    for image in images:
        partition = [part for part in dam.partitions if part.partition_name == image]
        if partition:
            dump_part(partition[0])
        else:
            sys.stderr.write("Partition %s not found in payload!\n" % image)

