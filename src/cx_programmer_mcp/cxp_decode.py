"""Pure-Python decoder for the PKWARE DCL stream used by CX-Programmer CXP files.

CXP is treated as an input format only. The edited project is intentionally written
as CXT, which CX-Programmer supports as its text project format.

encode_cxp() added to support save_cxp() for environments where CX-Programmer
cannot open .cxt directly.
"""
from __future__ import annotations

MAXBITS = 13

LITLEN = [
    11,124,8,7,28,7,188,13,76,4,10,8,12,10,12,10,8,23,8,
    9,7,6,7,8,7,6,55,8,23,24,12,11,7,9,11,12,6,7,22,5,
    7,24,6,11,9,6,7,22,7,11,38,7,9,8,25,11,8,11,9,12,
    8,12,5,38,5,38,5,11,7,5,6,21,6,10,53,8,7,24,10,27,
    44,253,253,253,252,252,252,13,12,45,12,45,12,61,12,45,
    44,173,
]
LENLEN = [2,35,36,53,38,23]
DISTLEN = [2,20,53,230,247,151,248]
BASE = [3,2,4,5,6,7,8,9,10,12,16,24,40,72,136,264]
EXTRA = [0,0,0,0,0,0,0,0,1,2,3,4,5,6,7,8]


def _construct(rep: list[int]) -> tuple[list[int], list[int]]:
    lengths: list[int] = []
    for b in rep:
        lengths.extend([b & 15] * ((b >> 4) + 1))
    count = [0] * (MAXBITS + 1)
    for length in lengths:
        count[length] += 1
    offs = [0] * (MAXBITS + 1)
    for length in range(1, MAXBITS):
        offs[length + 1] = offs[length] + count[length]
    symbol = [0] * sum(count[1:])
    pos = offs[:]
    for sym, length in enumerate(lengths):
        if length:
            symbol[pos[length]] = sym
            pos[length] += 1
    return count, symbol


class _BitReader:
    def __init__(self, data: bytes):
        self.data = data
        self.i = 0
        self.bitbuf = 0
        self.bitcnt = 0

    def bits(self, need: int) -> int:
        value = self.bitbuf
        while self.bitcnt < need:
            if self.i >= len(self.data):
                raise EOFError("Unexpected end of CXP compressed stream")
            value |= self.data[self.i] << self.bitcnt
            self.i += 1
            self.bitcnt += 8
        self.bitbuf = value >> need
        self.bitcnt -= need
        return value & ((1 << need) - 1) if need else 0

    def bit(self) -> int:
        return self.bits(1)


def _decode(br: _BitReader, table: tuple[list[int], list[int]]) -> int:
    count, symbol = table
    code = first = index = 0
    for length in range(1, MAXBITS + 1):
        code |= br.bit() ^ 1
        cnt = count[length]
        if code < first + cnt:
            return symbol[index + (code - first)]
        index += cnt
        first = (first + cnt) << 1
        code <<= 1
    raise ValueError("Invalid Huffman code in CXP stream")


def decode_cxp(data: bytes) -> bytes:
    """Decode a CX-Programmer .cxp compressed stream into CXT bytes."""
    br = _BitReader(data)
    literal_flag = br.bits(8)
    if literal_flag > 1:
        raise ValueError(f"Unsupported CXP literal flag: {literal_flag}")
    dict_bits = br.bits(8)
    if not 4 <= dict_bits <= 6:
        raise ValueError(f"Unsupported CXP dictionary bits: {dict_bits}")

    lit_h = _construct(LITLEN)
    len_h = _construct(LENLEN)
    dist_h = _construct(DISTLEN)
    out = bytearray()

    while True:
        if br.bit():
            symbol = _decode(br, len_h)
            length = BASE[symbol] + br.bits(EXTRA[symbol])
            if length == 519:
                break
            distance_bits = 2 if length == 2 else dict_bits
            distance = (_decode(br, dist_h) << distance_bits) + br.bits(distance_bits) + 1
            if distance > len(out):
                raise ValueError(f"Invalid CXP back-reference: {distance} > {len(out)}")
            for _ in range(length):
                out.append(out[-distance])
        else:
            symbol = _decode(br, lit_h) if literal_flag else br.bits(8)
            out.append(symbol)

    return bytes(out)



# ---------------------------------------------------------------------------
# Encoder: PKWARE DCL Implode, literal mode
# Encode table di-derive dengan brute-force simulasi decoder — paling akurat.
# ---------------------------------------------------------------------------

class _BitWriter:
    def __init__(self) -> None:
        self.buf = bytearray()
        self.bitbuf = 0
        self.bitcnt = 0

    def write_bits(self, value: int, n: int) -> None:
        """Write n bits, LSB first (sesuai format PKWARE DCL)."""
        for _ in range(n):
            self.bitbuf |= (value & 1) << self.bitcnt
            value >>= 1
            self.bitcnt += 1
            if self.bitcnt == 8:
                self.buf.append(self.bitbuf)
                self.bitbuf = 0
                self.bitcnt = 0

    def flush(self) -> bytes:
        if self.bitcnt:
            self.buf.append(self.bitbuf)
        return bytes(self.buf)


def _derive_encode_table(rep: list[int], num_symbols: int) -> dict[int, tuple[int, int]]:
    """
    Derive symbol -> (code_val, bit_len) dengan brute-force simulasi _decode().
    Decoder: code = (code<<1)|(bit^1) per bit, match saat code-count[len]<0.
    Kita cari bit pattern terpendek yang menghasilkan tiap simbol target.
    """
    count, symbol = _construct(rep)
    encode: dict[int, tuple[int, int]] = {}

    for target in range(num_symbols):
        for bit_len in range(1, MAXBITS + 1):
            found = False
            for code_val in range(1 << bit_len):
                # Simulasi _decode dengan bit_len bits dari code_val (LSB first)
                c = f = idx = 0
                matched = False
                for length in range(1, MAXBITS + 1):
                    bit_pos = length - 1
                    if bit_pos >= bit_len:
                        break
                    bit = (code_val >> bit_pos) & 1
                    c = (c << 1) | (bit ^ 1)
                    f += count[length]
                    idx += count[length]
                    c -= count[length]
                    if c < 0:
                        if length == bit_len and symbol[idx + c] == target:
                            encode[target] = (code_val, bit_len)
                            matched = True
                        break
                if matched:
                    found = True
                    break
            if found:
                break

    return encode


def encode_cxp(data: bytes) -> bytes:
    """
    Encode bytes ke format PKWARE DCL Implode kompatibel CX-Programmer.
    literal_flag=0x00: tiap literal di-emit sebagai 8 raw bits (tidak pakai Huffman).
    dict_bits=0x06.
    EOS: bit=1, length symbol 15 + 8 extra bits = 255 → total length = 519.
    """
    len_enc = _derive_encode_table(LENLEN, 16)

    bw = _BitWriter()

    for byte in data:
        bw.write_bits(0, 1)        # bit=0 → literal
        bw.write_bits(byte, 8)     # literal_flag=0: raw 8 bits, bukan Huffman

    # EOS: bit=1 (length), sym=15 → BASE[15]+extra=264+255=519
    bw.write_bits(1, 1)
    eos_code, eos_bits = len_enc[15]
    bw.write_bits(eos_code, eos_bits)
    bw.write_bits(255, 8)          # extra bits → length=264+255=519=EOS

    return bytes([0x00, 0x06]) + bw.flush()



