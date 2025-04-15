from .bitn import Bitn, NBin
from .crc import crc32
import pprint


class Dscptr:

    def __init__(self, bitn=None):
        self.type = 0
        self.length = 0
        self.value = b""
        self.total_size = 0
        if bitn:
            self.type = bitn.as_int(8)
            self.length = bitn.as_int(8)
            self.value = bitn.as_bytes(self.length << 3)
            self.total_size = 1 + 1 + self.length

    def __repr__(self):
        return str(vars(self))

    def add(self, nbin):
        nbin.add_int(self.type, 8)
        nbin.add_int(self.length, 8)
        nbin.add_bites(self.value)


class PmtStream:
    def __init__(self, bitn, conv_pids):
        self.descriptors = []
        self.stream_type = bitn.as_int(8)
        bitn.forward(3)
        self.elementary_PID = bitn.as_int(13)
        bitn.forward(4)
        self.ES_info_length = bitn.as_int(12)
        eil = self.ES_info_length << 3
        while eil > 0:
            dscptr = Dscptr(bitn)
            eil -= dscptr.total_size << 3
            self.descriptors.append(dscptr)
        if self.elementary_PID in conv_pids:
            self.stream_type = 134
            cuei = Dscptr()
            cuei.type = 5
            cuei.length = 4
            cuei.value = b"CUEI"
            cuei.total_size = 6
            self.descriptors = [cuei] + self.descriptors
            self.ES_info_length += cuei.total_size
        self.total_size = 5 + self.ES_info_length

    def __repr__(self):
        return str(vars(self))

    def add(self, nbin):
        nbin.add_int(self.stream_type, 8)
        nbin.reserve(3)
        nbin.add_int(self.elementary_PID, 13)
        nbin.reserve(4)
        nbin.add_int(self.ES_info_length, 12)
        for dscptr in self.descriptors:
            dscptr.add(nbin)


class PMT:

    def __init__(self, payload, conv_pids):
        self.conv_pids = conv_pids
        bitn = Bitn(payload)
        self.table_id = bitn.as_int(8)
        self.section_syntax_indicator = bitn.as_int(1)
        self.zero = bitn.as_int(1)
        bitn.forward(2)
        self.section_length = bitn.as_int(12)
        self.program_number = bitn.as_int(16)
        bitn.forward(2)
        self.version_number = bitn.as_int(5)
        self.current_next_indicator = bitn.as_int(1)
        self.section_number = bitn.as_int(8)
        self.last_section_number = bitn.as_int(8)
        bitn.forward(3)
        self.PCR_PID = bitn.as_int(13)
        bitn.forward(4)
        self.program_info_length = bitn.as_int(12)
        self.bitn = bitn
        self.descriptors = self.parse_descriptors()
        self.streams = self.parse_streams()
        self.crc32 = bitn.as_hex(32)

    def __repr__(self):
        return str(vars(self))

    def parse_descriptors(self):
        descriptors = []
        bitlen = self.program_info_length << 3
        data = self.bitn.as_bytes(bitlen)
        if not data:
            return descriptors
        bd = Bitn(data)
        while bitlen > 0:
            dscptr = Dscptr(bd)
            bitlen -= dscptr.total_size << 3
            descriptors.append(dscptr)
        return descriptors

    def parse_streams(self):
        streams = []
        while self.bitn.idx > 32:
            pms = PmtStream(self.bitn, self.conv_pids)
            streams.append(pms)
        pprint.pprint(streams)
        return streams

    def mk(self):
        cuei = Dscptr()
        cuei.type = 5
        cuei.length = 4
        cuei.value = b"CUEI"
        cuei.total_size = 6
        self.descriptors.append(cuei)
        self.program_info_length = sum(
            [dscptr.total_size for dscptr in self.descriptors]
        )
        stream_len = sum([stream.total_size for stream in self.streams])
        nbin = NBin()
        nbin.add_int(self.table_id, 8)  # 0x02
        nbin.add_int(self.section_syntax_indicator, 1)  # 9
        nbin.add_int(self.zero, 1)  # 10
        nbin.reserve(2)  # 12
        self.section_length = 15 + self.program_info_length + stream_len
        nbin.add_int(self.section_length, 12)  # 24
        nbin.add_int(self.program_number, 16)  # 40
        nbin.reserve(2)  # 42
        nbin.add_int(self.version_number, 5)  # 47
        nbin.add_int(self.current_next_indicator, 1)  # 48
        nbin.add_int(self.section_number, 8)  # 56
        nbin.add_int(self.last_section_number, 8)  # 64
        nbin.reserve(3)  # 67
        nbin.add_int(self.PCR_PID, 13)  # 80
        nbin.reserve(4)  # 84
        nbin.add_int(self.program_info_length, 12)  # 96
        for dscptr in self.descriptors:
            dscptr.add(nbin)
        for stream in self.streams:
            stream.add(nbin)
        self.crc32 = crc32(nbin.bites)
        nbin.add_int(self.crc32, 32)
        nbin.add_int(0, 8)
        return nbin.bites

        self.program_info_length = None
        self.descriptors = []
        self.streams = []
        self.crc32 = None
