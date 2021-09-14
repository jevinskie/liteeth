from abc import ABC
import enum
from typing import Final

import attr

from .bitfield import *

SPACE_B: Final[int] = 0x40


class ST25R_ICID(enum.IntEnum):
    ST25R3911: Final[int] = 0b00001
    ST25R3916: Final[int] = 0b00101


class ST25R3911_REVID(enum.IntEnum):
    R31: Final[int] = 0b010
    R33: Final[int] = 0b011
    R40: Final[int] = 0b100
    R41: Final[int] = 0b101


class ST25R3916_REVID(enum.IntEnum):
    R31: Final[int] = 0b010


class SPIOpMode(enum.IntEnum):
    WRITE: Final[int] = (0b00 << 6)
    READ: Final[int] = (0b01 << 6)
    FIFO: Final[int] = (0b10 << 6)
    WRITE_PT_A: Final[int]   = 0b10100000 # bytes 0-14
    WRITE_PT_F: Final[int]   = 0b10101000 # bytes 15-35
    WRITE_PT_TSN: Final[int] = 0b10101100 # bytes 36-47
    READ_PT: Final[int]      = 0b10111111
    FIFO_READ: Final[int]    = 0b10011111 # 0x9F
    FIFO_WRITE: Final[int]   = 0b10000000 # 0x80
    CMD: Final[int] = (0b11 << 6)


class OpMode(enum.IntEnum):
    en: Final[int] = 1 << 7
    rx_en: Final[int] = 1 << 6
    rx_chn: Final[int] = 1 << 5
    rx_man: Final[int] = 1 << 4
    tx_en: Final[int] = 1 << 3
    wu: Final[int] = 1 << 2
    en_fd_c1: Final[int] = 1 << 1
    en_fd_c0: Final[int] = 1 << 0


class PTMem:
    sz: Final[int] = 48

    @attr.s
    class AConf:
        uid: bytes = attr.ib(default=b'_APL')
        sens_res: bytes = attr.ib(default=b'\x02\x00')
        selr_l1: int = attr.ib(default=0x20)
        selr_l2: int = attr.ib(default=0x20)
        selr_l3: int = attr.ib(default=0x20)
        off: Final[int] = 0
        sz: Final[int] = 15

        def __bytes__(self):
            buf = b''
            if len(self.uid) == 4:
                buf += self.uid + bytes(6)
            elif len(self.uid) == 7:
                buf += self.uid + bytes(3)
            else:
                raise NotImplementedError(f'uid size: {len(self.uid)}')
            buf += self.sens_res
            buf += bytes([self.selr_l1, self.selr_l2, self.selr_l3])
            assert len(buf) == self.sz
            return buf

        @selr_l1.validator
        def _check_selr_l1_range(self, attribute, value):
            assert 0 <= value <= 255

        @selr_l2.validator
        def _check_selr_l2_range(self, attribute, value):
            assert 0 <= value <= 255

        @selr_l3.validator
        def _check_selr_l3_range(self, attribute, value):
            # assert value == 0x20
            pass

        @uid.validator
        def _check_uid_size(self, attribute, value):
            # assert len(value) in (4, 7)
            pass

        @sens_res.validator
        def _check_sens_res_size(self, attribute, value):
            assert len(value) == 2

        @classmethod
        def from_bytes(cls, buf: bytes) -> 'PTMem.AConf':
            assert len(buf) == cls.sz
            uid = buf[0:7]
            if uid[4:7] == bytes(3):
                uid = uid[0:4]
            # assert buf[7:10] == bytes(3) # RFU bytes
            sens_res = buf[10:12]
            selr_l1 = buf[12]
            selr_l2 = buf[13]
            # assert buf[14] == 0x20 # selr_l3 RFU but set to 0x20 in demo code
            return cls(uid=uid, sens_res=sens_res, selr_l1=selr_l1, selr_l2=selr_l2)

    class FConf:
        off: Final[int] = 15
        sz: Final[int] = 21

    class TSNData:
        off: Final[int] = 36
        sz: Final[int] = 11


@attr.s
class DirectCommandOpModes:
    required: Final[set[OpMode]] = attr.ib()
    prohibited: Final[set[OpMode]] = attr.ib()


OpModesAll = set([OpMode.__members__.values()])
OpModesEn = set([OpMode.en])
OpModesRx = set([OpMode.en, OpMode.rx_en])
OpModesTx = set([OpMode.en, OpMode.tx_en])
OpModesWu = set([OpMode.wu])
OpModesNone = set()


DirectCommandOpModesAll = DirectCommandOpModes(required=OpModesNone, prohibited=OpModesNone)
DirectCommandOpModesEn = DirectCommandOpModes(required=OpModesEn, prohibited=OpModesNone)
DirectCommandOpModesRx = DirectCommandOpModes(required=OpModesRx, prohibited=OpModesNone)
DirectCommandOpModesTx = DirectCommandOpModes(required=OpModesTx, prohibited=OpModesNone)
DirectCommandOpModesNotWu = DirectCommandOpModes(required=OpModesNone, prohibited=OpModesWu)


class DirectCommandListMeta(type):
    @classmethod
    def __prepare__(metacls, name: str, bases: tuple):
        r = collections.OrderedDict()
        return r

    def __init__(self, name: str, bases: tuple, dct: dict):
        type.__init__(self, name, bases, dct)
        for k, v in dct.items():
            if isinstance(v, DirectCommand):
                dct = {
                    '_name': property(lambda self: self.__class__.__name__),
                }
                dct.update(**v.__class__.__dict__)
                nty = type(k, (v.__class__,) + v.__class__.__bases__, dct)
                nv = nty(opcode=v.opcode, chaining=v.chaining, irq=v.irq, modes=v.modes)
                setattr(self, k, nv)


@attr.s(slots=False)
class DirectCommand:
    _name: Final[str] = attr.ib(init=False)
    _opcode: Final[int] = attr.ib()
    _chaining: Final[bool] = attr.ib()
    _irq: Final[bool] = attr.ib()
    _modes: Final[DirectCommandOpModes] = attr.ib()

    name: Final[str] = property(lambda self: self._name)
    opcode: Final[int] = property(lambda self: self._opcode)
    opc: Final[int] = property(lambda self: self._opcode) # opcode alias
    chaining: Final[bool] = property(lambda self: self._chaining)
    irq: Final[bool] = property(lambda self: self._irq)
    modes: Final[DirectCommandOpModes] = property(lambda self: self._modes)

    def is_allowed(self, dev: 'ST25R') -> bool:
        if not len(self.modes.prohibited) and not len(self.modes.required):
            return True
        op_reg = dev.rd(Regs.OP_CONTROL)
        for bad_bit in self.modes.prohibited:
            if (op_reg.packed & bad_bit):
                return False
        for req_bit in self.modes.required:
            if not (op_reg.packed & req_bit):
                return False
        return True


class DCmd(metaclass=DirectCommandListMeta):
    SET_DEFAULT                 = DirectCommand(opcode=0xC1, chaining=False, irq=False, modes=DirectCommandOpModesAll)
    STOP                        = DirectCommand(opcode=0xC2, chaining=True,  irq=False, modes=DirectCommandOpModesEn)
    TRANSMIT_WITH_CRC           = DirectCommand(opcode=0xC4, chaining=True,  irq=False, modes=DirectCommandOpModesEn)
    TRANSMIT_WITHOUT_CRC        = DirectCommand(opcode=0xC5, chaining=True,  irq=False, modes=DirectCommandOpModesEn)
    TRANSMIT_REQA               = DirectCommand(opcode=0xC6, chaining=True,  irq=False, modes=DirectCommandOpModesTx)
    TRANSMIT_WUPA               = DirectCommand(opcode=0xC7, chaining=True,  irq=False, modes=DirectCommandOpModesTx)
    INITIAL_RF_COLLISION        = DirectCommand(opcode=0xC8, chaining=True,  irq=True,  modes=DirectCommandOpModesEn)
    RESPONSE_RF_COLLISION_N     = DirectCommand(opcode=0xC9, chaining=True,  irq=True,  modes=DirectCommandOpModesEn)
    GOTO_SENSE                  = DirectCommand(opcode=0xCD, chaining=True,  irq=False, modes=DirectCommandOpModesRx)
    GOTO_SLEEP                  = DirectCommand(opcode=0xCE, chaining=True,  irq=False, modes=DirectCommandOpModesRx)
    MASK_RECEIVE_DATA           = DirectCommand(opcode=0xD0, chaining=True,  irq=False, modes=DirectCommandOpModesAll)
    UNMASK_RECEIVE_DATA         = DirectCommand(opcode=0xD1, chaining=True,  irq=False, modes=DirectCommandOpModesAll)
    AM_MOD_STATE_CHANGE         = DirectCommand(opcode=0xD2, chaining=True,  irq=False, modes=DirectCommandOpModesTx)
    MEASURE_AMPLITUDE           = DirectCommand(opcode=0xD3, chaining=False, irq=True,  modes=DirectCommandOpModesAll)
    RESET_RXGAIN                = DirectCommand(opcode=0xD5, chaining=False, irq=False, modes=DirectCommandOpModesEn)
    ADJUST_REGULATORS           = DirectCommand(opcode=0xD6, chaining=False, irq=True,  modes=DirectCommandOpModesEn)
    CALIBRATE_DRIVER_TIMING     = DirectCommand(opcode=0xD8, chaining=False, irq=False, modes=DirectCommandOpModesEn)
    MEASURE_PHASE               = DirectCommand(opcode=0xD9, chaining=False, irq=True,  modes=DirectCommandOpModesAll)
    CLEAR_RSSI                  = DirectCommand(opcode=0xDA, chaining=True,  irq=False, modes=DirectCommandOpModesEn)
    CLEAR_FIFO                  = DirectCommand(opcode=0xDB, chaining=True,  irq=False, modes=DirectCommandOpModesEn)
    TRANSPARENT_MODE            = DirectCommand(opcode=0xDC, chaining=False, irq=False, modes=DirectCommandOpModesEn)
    CALIBRATE_C_SENSOR          = DirectCommand(opcode=0xDD, chaining=False, irq=True,  modes=DirectCommandOpModesAll)
    MEASURE_CAPACITANCE         = DirectCommand(opcode=0xDE, chaining=False, irq=True,  modes=DirectCommandOpModesAll)
    MEASURE_VDD                 = DirectCommand(opcode=0xDF, chaining=False, irq=True,  modes=DirectCommandOpModesEn)
    START_GP_TIMER              = DirectCommand(opcode=0xE0, chaining=True,  irq=False, modes=DirectCommandOpModesEn)
    START_WUP_TIMER             = DirectCommand(opcode=0xE1, chaining=True,  irq=False, modes=DirectCommandOpModesNotWu)
    START_MASK_RECEIVE_TIMER    = DirectCommand(opcode=0xE2, chaining=True,  irq=False, modes=DirectCommandOpModesEn)
    START_NO_RESPONSE_TIMER     = DirectCommand(opcode=0xE3, chaining=True,  irq=False, modes=DirectCommandOpModesEn)
    START_PPON2_TIMER           = DirectCommand(opcode=0xE4, chaining=True,  irq=False, modes=DirectCommandOpModesEn)
    STOP_NRT                    = DirectCommand(opcode=0xE8, chaining=True,  irq=False, modes=DirectCommandOpModesEn)
    SPACE_B_ACCESS              = DirectCommand(opcode=0xFB, chaining=True,  irq=False, modes=DirectCommandOpModesAll)
    TEST_ACCESS                 = DirectCommand(opcode=0xFC, chaining=True,  irq=False, modes=DirectCommandOpModesAll)


class Bitrate(enum.IntEnum):
    DO_NOT_SET: Final[int] = 0xFF
    BR_106:     Final[int] = 0x00
    BR_212:     Final[int] = 0x01
    BR_424:     Final[int] = 0x02
    BR_848:     Final[int] = 0x03
    BR_1695:    Final[int] = 0x04
    BR_3390:    Final[int] = 0x05
    BR_6780:    Final[int] = 0x07


class RegsListMeta(type):
    @classmethod
    def __prepare__(metacls, name: str, bases: tuple):
        r = collections.OrderedDict()
        return r

    def __init__(self, name: str, bases: tuple, dct: dict):
        type.__init__(self, name, bases, dct)
        for k, v in dct.items():
            if isinstance(v, BitFieldUnionMeta):
                self.addr2reg[v.addr] = v
                if not v.addr & SPACE_B:
                    self.regs_a.append(v)
                else:
                    self.regs_b.append(v)
        self.regs_a = sorted(self.regs_a, key=lambda r: r.addr)
        self.regs_b = sorted(self.regs_b, key=lambda r: r.addr)

class Regs(metaclass=RegsListMeta):
    addr2reg: Final[dict[int, BitFieldUnionMeta]] = {}
    regs_a: list[BitFieldUnionMeta] = []
    regs_b: list[BitFieldUnionMeta] = []

    class IO_CONF1(BitFieldUnion):
        addr: Final[int] = 0x00
        single = BitField(7, 1)
        rfo2 = BitField(6, 1)
        i2c_thd1 = BitField(5, 1)
        i2c_thd0 = BitField(4, 1)
        i2c_thd = BitField(4, 2)
        rfu = BitField(3, 1)
        out_cl1 = BitField(2, 1)
        out_cl0 = BitField(1, 1)
        out_cl_13_56MHZ = BitField(2, 1)
        out_cl_4_78MHZ = BitField(1, 1)
        out_cl = BitField(1, 2)
        lf_clk_off = BitField(0, 1)
        lf_clk_off_on = BitField(0, 1)

    class IO_CONF2(BitFieldUnion):
        addr: Final[int] = 0x01
        sup3V = BitField(7, 1)
        sup3V_3V = BitField(7, 1)
        vspd_off = BitField(6, 1)
        aat_en = BitField(5, 1)
        miso_pd2 = BitField(4, 1)
        miso_pd1 = BitField(3, 1)
        io_drv_lvl = BitField(2, 1)
        am_ref_rf = BitField(1, 1)
        slow_up = BitField(0, 1)

    class OP_CONTROL(BitFieldUnion):
        addr: Final[int] = 0x02
        en = BitField(7, 1)
        rx_en = BitField(6, 1)
        rx_chn = BitField(5, 1)
        rx_man = BitField(4, 1)
        tx_en = BitField(3, 1)
        wu = BitField(2, 1)
        en_fd_c1 = BitField(1, 1)
        en_fd_manual_efd_ca = BitField(0, 1)
        en_fd_c0 = BitField(0, 1)
        en_fd_manual_efd_pdt = BitField(1, 1)
        en_fd = BitField(0, 2)

    class MODE(BitFieldUnion):
        addr: Final[int] = 0x03
        targ = BitField(7, 1)
        targ_targ = BitField(7, 1)
        om3 = BitField(6, 1)
        om2 = BitField(5, 1)
        om1 = BitField(4, 1)
        om0 = BitField(3, 1)
        om_topaz = BitField(5, 1)
        om_iso14443b = BitField(4, 1)
        om_iso14443a = BitField(3, 1)
        om_targ_nfca = BitField(3, 1)
        om_targ_nfcb = BitField(4, 1)
        om_targ_nfcf = BitField(5, 1)
        om = BitField(3, 4)
        tr_am = BitField(2, 1)
        tr_am_am = BitField(2, 1)
        nfc_ar1 = BitField(1, 1)
        nfc_ar0 = BitField(0, 1)
        nfc_ar_auto_rx = BitField(0, 1)
        nfc_ar_eof = BitField(1, 1)
        nfc_ar = BitField(0, 2)

    class BIT_RATE(BitFieldUnion):
        addr: Final[int] = 0x04
        txrate_212 = BitField(4, 1)
        txrate_424 = BitField(5, 1)
        txrate = BitField(4, 2)
        rxrate_212 = BitField(0, 1)
        rxrate_424 = BitField(1, 1)
        rxrate = BitField(0, 2)

    class ISO14443A_NFC(BitFieldUnion):
        addr: Final[int] = 0x05
        no_tx_par = BitField(7, 1)
        no_rx_par = BitField(6, 1)
        nfc_f0 = BitField(5, 1)
        p_len3 = BitField(4, 1)
        p_len2 = BitField(3, 1)
        p_len1 = BitField(2, 1)
        p_len0 = BitField(1, 1)
        p_len = BitField(1, 4)
        antcl = BitField(0, 1)

    class ISO14443B_1(BitFieldUnion):
        addr: Final[int] = 0x06
        egt2 = BitField(7, 1)
        egt1 = BitField(6, 1)
        egt0 = BitField(5, 1)
        egt = BitField(5, 3)
        sof_1 = BitField(3, 1)
        sof_1_3etu = BitField(3, 1)
        sof_0 = BitField(4, 1)
        sof_0_11etu = BitField(4, 1)
        sof = BitField(4, 2)
        eof = BitField(2, 1)
        eof_11etu = BitField(2, 1)
        half = BitField(1, 1)
        rx_st_om = BitField(0, 1)

    class ISO14443B_2(BitFieldUnion):
        addr: Final[int] = 0x07
        tr1_1 = BitField(7, 1)
        tr1_0 = BitField(6, 1)
        tr1_64fs32fs = BitField(6, 1)
        tr1 = BitField(6, 2)
        no_sof = BitField(5, 1)
        no_eof = BitField(4, 1)
        f_p1 = BitField(1, 1)
        f_p0 = BitField(0, 1)
        f_p_80 = BitField(1, 1)
        f_p_64 = BitField(0, 1)
        f_p = BitField(0, 2)

    class PASSIVE_TARGET(BitFieldUnion):
        addr: Final[int] = 0x08
        fdel_3 = BitField(7, 1)
        fdel_2 = BitField(6, 1)
        fdel_1 = BitField(5, 1)
        fdel_0 = BitField(4, 1)
        fdel = BitField(4, 4)
        d_ac_ap2p = BitField(3, 1)
        d_212_424_1r = BitField(2, 1)
        rfu = BitField(1, 1)
        d_106_ac_a = BitField(0, 1)

    class STREAM_MODE(BitFieldUnion):
        addr: Final[int] = 0x09
        rfu = BitField(7, 1)
        scf1 = BitField(6, 1)
        scf0 = BitField(5, 1)
        scf_sc424 = BitField(5, 1)
        scf_sc848 = BitField(6, 1)
        scf_bpsk1695 = BitField(5, 1)
        scf_bpsk3390 = BitField(6, 1)
        scf = BitField(5, 2)
        scp1 = BitField(4, 1)
        scp0 = BitField(3, 1)
        scp_2pulses = BitField(3, 1)
        scp_4pulses = BitField(4, 1)
        scp = BitField(3, 2)
        stx2 = BitField(2, 1)
        stx1 = BitField(1, 1)
        stx0 = BitField(0, 1)
        stx_212 = BitField(0, 1)
        stx_424 = BitField(1, 1)
        stx = BitField(0, 3)

    class AUX(BitFieldUnion):
        addr: Final[int] = 0x0A
        no_crc_rx = BitField(7, 1)
        rfu = BitField(6, 1)
        nfc_id1 = BitField(5, 1)
        nfc_id0 = BitField(4, 1)
        nfc_id_7bytes = BitField(4, 1)
        nfc_id = BitField(4, 2)
        mfaz_cl90 = BitField(3, 1)
        dis_corr = BitField(2, 1)
        dis_corr_coherent = BitField(2, 1)
        nfc_n1 = BitField(1, 1)
        nfc_n0 = BitField(0, 1)
        nfc_n = BitField(0, 2)

    class RX_CONF1(BitFieldUnion):
        addr: Final[int] = 0x0B
        ch_sel = BitField(7, 1)
        ch_sel_PM = BitField(7, 1)
        lp2 = BitField(6, 1)
        lp1 = BitField(5, 1)
        lp0 = BitField(4, 1)
        lp_600khz = BitField(4, 1)
        lp_300khz = BitField(5, 1)
        lp_2000khz = BitField(6, 1)
        lp = BitField(4, 3)
        z600k = BitField(3, 1)
        h200 = BitField(2, 1)
        h80 = BitField(1, 1)
        z12k = BitField(0, 1)
        hz_60_200khz = BitField(2, 1)
        hz_40_80khz = BitField(1, 1)
        hz_12_200khz = BitField(0, 1)
        hz_600_400khz = BitField(3, 1)
        hz = BitField(0, 4)

    class RX_CONF2(BitFieldUnion):
        addr: Final[int] = 0x0C
        demod_mode = BitField(7, 1)
        amd_sel = BitField(6, 1)
        amd_sel_mixer = BitField(6, 1)
        sqm_dyn = BitField(5, 1)
        pulz_61 = BitField(4, 1)
        agc_en = BitField(3, 1)
        agc_m = BitField(2, 1)
        agc_alg = BitField(1, 1)
        agc6_3 = BitField(0, 1)

    class RX_CONF3(BitFieldUnion):
        addr: Final[int] = 0x0D
        rg1_am2 = BitField(7, 1)
        rg1_am1 = BitField(6, 1)
        rg1_am0 = BitField(5, 1)
        rg1_am = BitField(5, 3)
        rg1_pm2 = BitField(4, 1)
        rg1_pm1 = BitField(3, 1)
        rg1_pm0 = BitField(2, 1)
        rg1_pm = BitField(2, 3)
        lf_en = BitField(1, 1)
        lf_op = BitField(0, 1)

    class RX_CONF4(BitFieldUnion):
        addr: Final[int] = 0x0E
        rg2_am3 = BitField(7, 1)
        rg2_am2 = BitField(6, 1)
        rg2_am1 = BitField(5, 1)
        rg2_am0 = BitField(4, 1)
        rg2_am = BitField(4, 4)
        rg2_pm3 = BitField(3, 1)
        rg2_pm2 = BitField(2, 1)
        rg2_pm1 = BitField(1, 1)
        rg2_pm0 = BitField(0, 1)
        rg2_pm = BitField(0, 4)

    class MASK_RX_TIMER(BitFieldUnion):
        addr: Final[int] = 0x0F

    class NO_RESPONSE_TIMER1(BitFieldUnion):
        addr: Final[int] = 0x10

    class NO_RESPONSE_TIMER2(BitFieldUnion):
        addr: Final[int] = 0x11

    class TIMER_EMV_CONTROL(BitFieldUnion):
        addr: Final[int] = 0x12
        gptc2 = BitField(7, 1)
        gptc1 = BitField(6, 1)
        gptc0 = BitField(5, 1)
        gptc_erx = BitField(5, 1)
        gptc_srx = BitField(6, 1)
        gptc = BitField(5, 3)
        rfu = BitField(4, 1)
        mrt_step = BitField(3, 1)
        mrt_step_512 = BitField(3, 1)
        nrt_nfc = BitField(2, 1)
        nrt_nfc_on = BitField(2, 1)
        nrt_emv = BitField(1, 1)
        nrt_emv_on = BitField(1, 1)
        nrt_step = BitField(0, 1)
        nrt_step_4096_fc = BitField(0, 1)

    class GPT1(BitFieldUnion):
        addr: Final[int] = 0x13

    class GPT2(BitFieldUnion):
        addr: Final[int] = 0x14

    class PPON2(BitFieldUnion):
        addr: Final[int] = 0x15

    class IRQ_MASK_MAIN(BitFieldUnion):
        addr: Final[int] = 0x16
        osc = BitField(7, 1)
        wl = BitField(6, 1)
        rxs = BitField(5, 1)
        rxe = BitField(4, 1)
        txe = BitField(3, 1)
        col = BitField(2, 1)
        rx_rest = BitField(1, 1)

    class IRQ_MASK_TIMER_NFC(BitFieldUnion):
        addr: Final[int] = 0x17
        dct = BitField(7, 1)
        nre = BitField(6, 1)
        gpe = BitField(5, 1)
        eon = BitField(4, 1)
        eof = BitField(3, 1)
        cac = BitField(2, 1)
        cat = BitField(1, 1)
        nfct = BitField(0, 1)

    class IRQ_MASK_ERROR_WUP(BitFieldUnion):
        addr: Final[int] = 0x18
        crc = BitField(7, 1)
        par = BitField(6, 1)
        err2 = BitField(5, 1)
        err1 = BitField(4, 1)
        wt = BitField(3, 1)
        wam = BitField(2, 1)
        wph = BitField(1, 1)
        wcap = BitField(0, 1)

    class IRQ_MASK_TARGET(BitFieldUnion):
        addr: Final[int] = 0x19
        ppon2 = BitField(7, 1)
        sl_wl = BitField(6, 1)
        apon = BitField(5, 1)
        rxe_pta = BitField(4, 1)
        wu_f = BitField(3, 1)
        rfu1 = BitField(2, 1)
        wu_aprime = BitField(1, 1)
        wu_a = BitField(0, 1)

    class IRQ_MAIN(BitFieldUnion):
        addr: Final[int] = 0x1A
        osc = BitField(7, 1)
        wl = BitField(6, 1)
        rxs = BitField(5, 1)
        rxe = BitField(4, 1)
        txe = BitField(3, 1)
        col = BitField(2, 1)
        rx_rest = BitField(1, 1)

    class IRQ_TIMER_NFC(BitFieldUnion):
        addr: Final[int] = 0x1B
        dct = BitField(7, 1)
        nre = BitField(6, 1)
        gpe = BitField(5, 1)
        eon = BitField(4, 1)
        eof = BitField(3, 1)
        cac = BitField(2, 1)
        cat = BitField(1, 1)
        nfct = BitField(0, 1)

    class IRQ_ERROR_WUP(BitFieldUnion):
        addr: Final[int] = 0x1C
        crc = BitField(7, 1)
        par = BitField(6, 1)
        err2 = BitField(5, 1)
        err1 = BitField(4, 1)
        wt = BitField(3, 1)
        wam = BitField(2, 1)
        wph = BitField(1, 1)
        wcap = BitField(0, 1)

    class IRQ_TARGET(BitFieldUnion):
        addr: Final[int] = 0x1D
        ppon2 = BitField(7, 1)
        sl_wl = BitField(6, 1)
        apon = BitField(5, 1)
        rxe_pta = BitField(4, 1)
        wu_f = BitField(3, 1)
        rfu1 = BitField(2, 1)
        wu_aprime = BitField(1, 1)
        wu_a = BitField(0, 1)

    class FIFO_STATUS1(BitFieldUnion):
        addr: Final[int] = 0x1E

    class FIFO_STATUS2(BitFieldUnion):
        addr: Final[int] = 0x1F
        fifo_b9 = BitField(7, 1)
        fifo_b8 = BitField(6, 1)
        fifo_b = BitField(6, 2)
        fifo_unf = BitField(5, 1)
        fifo_ovr = BitField(4, 1)
        fifo_lb2 = BitField(3, 1)
        fifo_lb1 = BitField(2, 1)
        fifo_lb0 = BitField(1, 1)
        fifo_lb = BitField(1, 3)
        np_lb = BitField(0, 1)

    class COLLISION_STATUS(BitFieldUnion):
        addr: Final[int] = 0x20
        c_byte3 = BitField(7, 1)
        c_byte2 = BitField(6, 1)
        c_byte1 = BitField(5, 1)
        c_byte0 = BitField(4, 1)
        c_byte = BitField(4, 4)
        c_bit2 = BitField(3, 1)
        c_bit1 = BitField(2, 1)
        c_bit0 = BitField(1, 1)
        c_pb = BitField(0, 1)
        c_bit = BitField(1, 2)

    class PASSIVE_TARGET_STATUS(BitFieldUnion):
        addr: Final[int] = 0x21
        rfu = BitField(7, 1)
        rfu1 = BitField(6, 1)
        rfu2 = BitField(5, 1)
        rfu3 = BitField(4, 1)
        pta_state3 = BitField(3, 1)
        pta_state2 = BitField(2, 1)
        pta_state1 = BitField(1, 1)
        pta_state0 = BitField(0, 1)
        pta_st_idle = BitField(0, 1)
        pta_st_ready_l1 = BitField(1, 1)
        pta_st_rfu4 = BitField(2, 1)
        pta_st_rfu8 = BitField(3, 1)
        pta_state = BitField(0, 4)

    class NUM_TX_BYTES1(BitFieldUnion):
        addr: Final[int] = 0x22
        ntx_hi8 = BitField(0, 8)

    class NUM_TX_BYTES2(BitFieldUnion):
        addr: Final[int] = 0x23
        ntx4 = BitField(7, 1)
        ntx3 = BitField(6, 1)
        ntx2 = BitField(5, 1)
        ntx1 = BitField(4, 1)
        ntx0 = BitField(3, 1)
        ntx = BitField(3, 5)
        ntx_lo5 = BitField(3, 5)
        nbtx2 = BitField(2, 1)
        nbtx1 = BitField(1, 1)
        nbtx0 = BitField(0, 1)
        nbtx = BitField(0, 3)

    class NFCIP1_BIT_RATE(BitFieldUnion):
        addr: Final[int] = 0x24
        nfc_rfu1 = BitField(7, 1)
        nfc_rfu0 = BitField(6, 1)
        nfc_rate1 = BitField(5, 1)
        nfc_rate0 = BitField(4, 1)
        nfc_rate = BitField(4, 2)
        ppt2_on = BitField(3, 1)
        gpt_on = BitField(2, 1)
        nrt_on = BitField(1, 1)
        mrt_on = BitField(0, 1)

    class AD_RESULT(BitFieldUnion):
        addr: Final[int] = 0x25

    class ANT_TUNE_A(BitFieldUnion):
        addr: Final[int] = 0x26

    class ANT_TUNE_B(BitFieldUnion):
        addr: Final[int] = 0x27

    class TX_DRIVER(BitFieldUnion):
        addr: Final[int] = 0x28
        am_mod3 = BitField(7, 1)
        am_mod2 = BitField(6, 1)
        am_mod1 = BitField(5, 1)
        am_mod0 = BitField(4, 1)
        am_mod_6percent = BitField(4, 1)
        am_mod_7percent = BitField(5, 1)
        am_mod_9percent = BitField(6, 1)
        am_mod_13percent = BitField(7, 1)
        am_mod = BitField(4, 4)
        d_res3 = BitField(3, 1)
        d_res2 = BitField(2, 1)
        d_res1 = BitField(1, 1)
        d_res0 = BitField(0, 1)
        d_res = BitField(0, 4)

    class PT_MOD(BitFieldUnion):
        addr: Final[int] = 0x29
        ptm_res3 = BitField(7, 1)
        ptm_res2 = BitField(6, 1)
        ptm_res1 = BitField(5, 1)
        ptm_res0 = BitField(4, 1)
        ptm_res = BitField(4, 4)
        pt_res3 = BitField(3, 1)
        pt_res2 = BitField(2, 1)
        pt_res1 = BitField(1, 1)
        pt_res0 = BitField(0, 1)
        pt_res = BitField(0, 4)

    class FIELD_THRESHOLD_ACTV(BitFieldUnion):
        addr: Final[int] = 0x2A
        trg_l2a = BitField(6, 1)
        trg_l1a = BitField(5, 1)
        trg_l0a = BitField(4, 1)
        trg_105mV = BitField(4, 1)
        trg_150mV = BitField(5, 1)
        trg_290mV = BitField(6, 1)
        trg = BitField(4, 3)
        rfe_t3a = BitField(3, 1)
        rfe_t2a = BitField(2, 1)
        rfe_t1a = BitField(1, 1)
        rfe_t0a = BitField(0, 1)
        rfe_105mV = BitField(0, 1)
        rfe_150mV = BitField(1, 1)
        rfe_290mV = BitField(2, 1)
        rfe_25mV = BitField(3, 1)
        rfe = BitField(0, 4)

    class FIELD_THRESHOLD_DEACTV(BitFieldUnion):
        addr: Final[int] = 0x2B
        trg_l2d = BitField(6, 1)
        trg_l1d = BitField(5, 1)
        trg_l0d = BitField(4, 1)
        trg_105mV = BitField(4, 1)
        trg_150mV = BitField(5, 1)
        trg_290mV = BitField(6, 1)
        trg = BitField(4, 3)
        rfe_t3d = BitField(3, 1)
        rfe_t2d = BitField(2, 1)
        rfe_t1d = BitField(1, 1)
        rfe_t0d = BitField(0, 1)
        rfe_105mV = BitField(0, 1)
        rfe_150mV = BitField(1, 1)
        rfe_290mV = BitField(2, 1)
        rfe_25mV = BitField(3, 1)
        rfe = BitField(0, 4)

    class REGULATOR_CONTROL(BitFieldUnion):
        addr: Final[int] = 0x2C
        reg_s = BitField(7, 1)
        rege_3 = BitField(6, 1)
        rege_2 = BitField(5, 1)
        rege_1 = BitField(4, 1)
        rege_0 = BitField(3, 1)
        rege = BitField(3, 4)
        mpsv2 = BitField(3, 1)
        mpsv1 = BitField(1, 1)
        mpsv0 = BitField(0, 1)
        mpsv_vdd_a = BitField(0, 1)
        mpsv_vdd_d = BitField(1, 1)
        mpsv_vdd_am = BitField(2, 1)
        mpsv = BitField(0, 3)

    class RSSI_RESULT(BitFieldUnion):
        addr: Final[int] = 0x2D
        rssi_am_3 = BitField(7, 1)
        rssi_am_2 = BitField(6, 1)
        rssi_am_1 = BitField(5, 1)
        rssi_am_0 = BitField(4, 1)
        rssi_am = BitField(4, 4)
        rssi_pm3 = BitField(3, 1)
        rssi_pm2 = BitField(2, 1)
        rssi_pm1 = BitField(1, 1)
        rssi_pm0 = BitField(0, 1)
        rssi_pm = BitField(0, 4)

    class GAIN_RED_STATE(BitFieldUnion):
        addr: Final[int] = 0x2E
        gs_am_3 = BitField(7, 1)
        gs_am_2 = BitField(6, 1)
        gs_am_1 = BitField(5, 1)
        gs_am_0 = BitField(4, 1)
        gs_am = BitField(4, 4)
        gs_pm_3 = BitField(3, 1)
        gs_pm_2 = BitField(2, 1)
        gs_pm_1 = BitField(1, 1)
        gs_pm_0 = BitField(0, 1)
        gs_pm = BitField(0, 4)

    class CAP_SENSOR_CONTROL(BitFieldUnion):
        addr: Final[int] = 0x2F
        cs_mcal4 = BitField(7, 1)
        cs_mcal3 = BitField(6, 1)
        cs_mcal2 = BitField(5, 1)
        cs_mcal1 = BitField(4, 1)
        cs_mcal0 = BitField(3, 1)
        cs_mcal = BitField(3, 5)
        cs_g2 = BitField(2, 1)
        cs_g1 = BitField(1, 1)
        cs_g0 = BitField(0, 1)
        cs_g = BitField(0, 3)

    class CAP_SENSOR_RESULT(BitFieldUnion):
        addr: Final[int] = 0x30
        cs_cal4 = BitField(7, 1)
        cs_cal3 = BitField(6, 1)
        cs_cal2 = BitField(5, 1)
        cs_cal1 = BitField(4, 1)
        cs_cal0 = BitField(3, 1)
        cs_cal = BitField(3, 5)
        cs_cal_end = BitField(2, 1)
        cs_cal_err = BitField(1, 1)

    class AUX_DISPLAY(BitFieldUnion):
        addr: Final[int] = 0x31
        a_cha = BitField(7, 1)
        efd_o = BitField(6, 1)
        tx_on = BitField(5, 1)
        osc_ok = BitField(4, 1)
        rx_on = BitField(3, 1)
        rx_act = BitField(2, 1)
        en_peer = BitField(1, 1)
        en_ac = BitField(0, 1)

    class WUP_TIMER_CONTROL(BitFieldUnion):
        addr: Final[int] = 0x32
        wur = BitField(7, 1)
        wut2 = BitField(6, 1)
        wut1 = BitField(5, 1)
        wut0 = BitField(4, 1)
        wut = BitField(4, 3)
        wto = BitField(3, 1)
        wam = BitField(2, 1)
        wph = BitField(1, 1)
        wcap = BitField(0, 1)

    class AMPLITUDE_MEASURE_CONF(BitFieldUnion):
        addr: Final[int] = 0x33
        am_d3 = BitField(7, 1)
        am_d2 = BitField(6, 1)
        am_d1 = BitField(5, 1)
        am_d0 = BitField(4, 1)
        am_d = BitField(4, 4)
        am_aam = BitField(3, 1)
        am_aew1 = BitField(2, 1)
        am_aew0 = BitField(1, 1)
        am_aew = BitField(1, 2)
        am_ae = BitField(0, 1)

    class AMPLITUDE_MEASURE_REF(BitFieldUnion):
        addr: Final[int] = 0x34

    class AMPLITUDE_MEASURE_AA_RESULT(BitFieldUnion):
        addr: Final[int] = 0x35

    class AMPLITUDE_MEASURE_RESULT(BitFieldUnion):
        addr: Final[int] = 0x36

    class PHASE_MEASURE_CONF(BitFieldUnion):
        addr: Final[int] = 0x37
        pm_d3 = BitField(7, 1)
        pm_d2 = BitField(6, 1)
        pm_d1 = BitField(5, 1)
        pm_d0 = BitField(4, 1)
        pm_d = BitField(4, 4)
        pm_aam = BitField(3, 1)
        pm_aew1 = BitField(2, 1)
        pm_aew0 = BitField(1, 1)
        pm_aew = BitField(1, 2)
        pm_ae = BitField(0, 1)

    class PHASE_MEASURE_REF(BitFieldUnion):
        addr: Final[int] = 0x38

    class PHASE_MEASURE_AA_RESULT(BitFieldUnion):
        addr: Final[int] = 0x39

    class PHASE_MEASURE_RESULT(BitFieldUnion):
        addr: Final[int] = 0x3A

    class CAPACITANCE_MEASURE_CONF(BitFieldUnion):
        addr: Final[int] = 0x3B
        cm_d3 = BitField(7, 1)
        cm_d2 = BitField(6, 1)
        cm_d1 = BitField(5, 1)
        cm_d0 = BitField(4, 1)
        cm_d = BitField(4, 4)
        cm_aam = BitField(3, 1)
        cm_aew1 = BitField(2, 1)
        cm_aew0 = BitField(1, 1)
        cm_aew = BitField(1, 2)
        cm_ae = BitField(0, 1)

    class CAPACITANCE_MEASURE_REF(BitFieldUnion):
        addr: Final[int] = 0x3C

    class CAPACITANCE_MEASURE_AA_RESULT(BitFieldUnion):
        addr: Final[int] = 0x3D

    class CAPACITANCE_MEASURE_RESULT(BitFieldUnion):
        addr: Final[int] = 0x3E

    class IC_IDENTITY(BitFieldUnion):
        addr: Final[int] = 0x3F
        ic_type4 = BitField(7, 1)
        ic_type3 = BitField(6, 1)
        ic_type2 = BitField(5, 1)
        ic_type1 = BitField(4, 1)
        ic_type0 = BitField(3, 1)
        ic_type = BitField(3, 5)
        ic_rev2 = BitField(2, 1)
        ic_rev1 = BitField(1, 1)
        ic_rev0 = BitField(0, 1)
        ic_rev = BitField(0, 3)

    class EMD_SUP_CONF(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x05
        emd_emv = BitField(7, 1)
        emd_emv_on = BitField(7, 1)
        rx_start_emv = BitField(6, 1)
        rx_start_emv_on = BitField(6, 1)
        rfu1 = BitField(5, 1)
        rfu0 = BitField(4, 1)
        emd_thld3 = BitField(3, 1)
        emd_thld2 = BitField(2, 1)
        emd_thld1 = BitField(1, 1)
        emd_thld0 = BitField(0, 1)
        emd_thld = BitField(0, 4)

    class SUBC_START_TIME(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x06
        rfu2 = BitField(7, 1)
        rfu1 = BitField(6, 1)
        rfu0 = BitField(5, 1)
        sst4 = BitField(4, 1)
        sst3 = BitField(3, 1)
        sst2 = BitField(2, 1)
        sst1 = BitField(1, 1)
        sst0 = BitField(0, 1)
        sst = BitField(0, 5)

    class P2P_RX_CONF(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x0B
        ook_fd = BitField(7, 1)
        ook_rc1 = BitField(6, 1)
        ook_rc0 = BitField(5, 1)
        ook_thd1 = BitField(4, 1)
        ook_thd0 = BitField(3, 1)
        ask_rc1 = BitField(2, 1)
        ask_rc0 = BitField(1, 1)
        ask_thd = BitField(0, 1)

    class CORR_CONF1(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x0C
        corr_s7 = BitField(7, 1)
        corr_s6 = BitField(6, 1)
        corr_s5 = BitField(5, 1)
        corr_s4 = BitField(4, 1)
        corr_s3 = BitField(3, 1)
        corr_s2 = BitField(2, 1)
        corr_s1 = BitField(1, 1)
        corr_s0 = BitField(0, 1)

    class CORR_CONF2(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x0D
        rfu5 = BitField(7, 1)
        rfu4 = BitField(6, 1)
        rfu3 = BitField(5, 1)
        rfu2 = BitField(4, 1)
        rfu1 = BitField(3, 1)
        rfu0 = BitField(2, 1)
        corr_s9 = BitField(1, 1)
        corr_s8 = BitField(0, 1)

    class SQUELCH_TIMER(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x0F

    class FIELD_ON_GT(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x15

    class AUX_MOD(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x28
        dis_reg_am = BitField(7, 1)
        lm_ext_pol = BitField(6, 1)
        lm_ext = BitField(5, 1)
        lm_dri = BitField(4, 1)
        res_am = BitField(3, 1)
        rfu2 = BitField(2, 1)
        rfu1 = BitField(1, 1)
        rfu0 = BitField(0, 1)

    class TX_DRIVER_TIMING(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x29
        d_rat_t3 = BitField(7, 1)
        d_rat_t2 = BitField(6, 1)
        d_rat_t1 = BitField(5, 1)
        d_rat_t0 = BitField(4, 1)
        d_rat = BitField(4, 4)
        rfu = BitField(3, 1)
        d_tim_m2 = BitField(2, 1)
        d_tim_m1 = BitField(1, 1)
        d_tim_m0 = BitField(0, 1)
        d_tim_m = BitField(0, 3)

    class RES_AM_MOD(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x2A
        fa3_f = BitField(7, 1)
        md_res6 = BitField(6, 1)
        md_res5 = BitField(5, 1)
        md_res4 = BitField(4, 1)
        md_res3 = BitField(3, 1)
        md_res2 = BitField(2, 1)
        md_res1 = BitField(1, 1)
        md_res0 = BitField(0, 1)
        md_res = BitField(0, 7)

    class TX_DRIVER_STATUS(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x2B
        d_rat_r3 = BitField(7, 1)
        d_rat_r2 = BitField(6, 1)
        d_rat_r1 = BitField(5, 1)
        d_rat_r0 = BitField(4, 1)
        d_rat = BitField(4, 4)
        rfu = BitField(3, 1)
        d_tim_r2 = BitField(2, 1)
        d_tim_r1 = BitField(1, 1)
        d_tim_r0 = BitField(0, 1)
        d_tim = BitField(0, 3)

    class REGULATOR_RESULT(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x2C
        reg_3 = BitField(7, 1)
        reg_2 = BitField(6, 1)
        reg_1 = BitField(5, 1)
        reg_0 = BitField(4, 1)
        reg = BitField(4, 4)
        i_lim = BitField(0, 1)

    class OVERSHOOT_CONF1(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x30
        ov_tx_mode1 = BitField(7, 1)
        ov_tx_mode0 = BitField(6, 1)
        ov_pattern13 = BitField(5, 1)
        ov_pattern12 = BitField(4, 1)
        ov_pattern11 = BitField(3, 1)
        ov_pattern10 = BitField(2, 1)
        ov_pattern9 = BitField(1, 1)
        ov_pattern8 = BitField(0, 1)

    class OVERSHOOT_CONF2(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x31
        ov_pattern7 = BitField(7, 1)
        ov_pattern6 = BitField(6, 1)
        ov_pattern5 = BitField(5, 1)
        ov_pattern4 = BitField(4, 1)
        ov_pattern3 = BitField(3, 1)
        ov_pattern2 = BitField(2, 1)
        ov_pattern1 = BitField(1, 1)
        ov_pattern0 = BitField(0, 1)

    class UNDERSHOOT_CONF1(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x32
        un_tx_mode1 = BitField(7, 1)
        un_tx_mode0 = BitField(6, 1)
        un_pattern13 = BitField(5, 1)
        un_pattern12 = BitField(4, 1)
        un_pattern11 = BitField(3, 1)
        un_pattern10 = BitField(2, 1)
        un_pattern9 = BitField(1, 1)
        un_pattern8 = BitField(0, 1)

    class UNDERSHOOT_CONF2(BitFieldUnion):
        addr: Final[int] = SPACE_B | 0x33
        un_pattern7 = BitField(7, 1)
        un_pattern6 = BitField(6, 1)
        un_pattern5 = BitField(5, 1)
        un_pattern4 = BitField(4, 1)
        un_pattern3 = BitField(3, 1)
        un_pattern2 = BitField(2, 1)
        un_pattern1 = BitField(1, 1)
        un_pattern0 = BitField(0, 1)


