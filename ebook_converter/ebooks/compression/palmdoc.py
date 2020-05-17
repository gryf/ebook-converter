import io
import sys
from struct import pack


def decompress_doc(data):
    uncompressed = b''
    skip_next = 0

    for idx, item in enumerate(data):
        if skip_next:
            skip_next -= 1
            continue

        if item in range(1, 9):
            # copy amount of bytes as in item
            skip_next = item
            for amount in range(1, item + 1):
                uncompressed += data[idx + amount].to_bytes(1, sys.byteorder)

        elif item < 128:
            # direct ascii copy
            uncompressed += item.to_bytes(1, sys.byteorder)

        elif item >= 192:
            # merged space and ascii character
            uncompressed += b' ' + (item ^ 128).to_bytes(1, sys.byteorder)

        else:
            # compressed data, item contains how many characters should be
            # repeated for the next one.
            skip_next = 1
            item = (item << 8) + data[idx + 1]
            character_index = (item & 0x3FFF) >> 3
            for _ in range((item & 7) + 3):
                uncompressed += (uncompressed[len(uncompressed) -
                                              character_index]
                                 .to_bytes(1, sys.byteorder))

    return uncompressed


def compress_doc(data):
    out = io.BytesIO()
    i = 0
    ldata = len(data)
    while i < ldata:
        if i > 10 and (ldata - i) > 10:
            chunk = b''
            match = -1
            for j in range(10, 2, -1):
                chunk = data[i:i+j]
                try:
                    match = data.rindex(chunk, 0, i)
                except ValueError:
                    continue
                if (i - match) <= 2047:
                    break
                match = -1
            if match >= 0:
                n = len(chunk)
                m = i - match
                code = 0x8000 + ((m << 3) & 0x3ff8) + (n - 3)
                out.write(pack('>H', code))
                i += n
                continue
        ch = data[i:i+1]
        och = ord(ch)
        i += 1
        if ch == b' ' and (i + 1) < ldata:
            onch = ord(data[i:i+1])
            if onch >= 0x40 and onch < 0x80:
                out.write(pack('>B', onch ^ 0x80))
                i += 1
                continue
        if och == 0 or (och > 8 and och < 0x80):
            out.write(ch)
        else:
            j = i
            binseq = [ch]
            while j < ldata and len(binseq) < 8:
                ch = data[j:j+1]
                och = ord(ch)
                if och == 0 or (och > 8 and och < 0x80):
                    break
                binseq.append(ch)
                j += 1
            out.write(pack('>B', len(binseq)))
            out.write(b''.join(binseq))
            i += len(binseq) - 1
    return out.getvalue()
