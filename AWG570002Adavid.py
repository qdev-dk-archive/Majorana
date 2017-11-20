import struct
import warnings

import numpy as np
import array as arr

from time import sleep, localtime
from io import BytesIO

from qcodes import VisaInstrument, validators as vals
from pyvisa.errors import VisaIOError



class Tektronix_AWG700002A(VisaInstrument):



    def __init__(self, name, address, **kwargs):
        timeout = 1
        super().__init__(name, address, timeout=timeout, **kwargs)

        for i in range(1, 3):

            outputstate_cmd = 'OUTPut{}:STATe'.format(i)

            amplitude_cmd = 'FGEN:CHANnel{}:AMPLitude'.format(i)

            frequency_cmd = 'FGEN:CHANnel{}:FREQuency'.format(i)

            dclevel_cmd = 'FGEN:CHANnel{}:DCLevel'.format(i)

            highvoltage_cmd = 'FGEN:CHANnel{}:HIGH'.format(i)

            lowvoltage_cmd = 'FGEN:CHANnel{}:LOW'.format(i)

            offset_cmd = 'FGEN:CHANnel{}:OFFSet'.format(i)

            period_cmd = 'FGEN:PERiod?'.format(i)

            phase_cmd = 'FGEN:CHANnel{}:PHASe'.format(i)

            symmetry_cmd = 'FGEN:CHANnel{}:SYMMetry'.format(i)

            type_cmd = 'FGEN:CHANnel{}:TYPE'.format(i)



            self.add_parameter('ch{}_state'.format(i),
                                label='Channel {} state'.format(i),
                                get_cmd=outputstate_cmd + '?',
                                set_cmd=outputstate_cmd + ' {}',
                                vals=vals.Ints(0,1),
                                get_parser=float)


            self.add_parameter('ch{}_amplitude'.format(i),
                                label='Channel {} amplitude'.format(i),
                                get_cmd=amplitude_cmd + '?',
                                set_cmd=amplitude_cmd + ' {}',
                                vals=vals.Numbers(0, 0.5),
                                get_parser=float)

            self.add_parameter('ch{}_frequency'.format(i),
                                label='Channel {} frequency'.format(i),
                                get_cmd=frequency_cmd + '?',
                                set_cmd=frequency_cmd + ' {:E}',
                                vals=vals.Numbers(1, 50000000),
                                get_parser=float)


            self.add_parameter('ch{}_dclevel'.format(i),
                                label='Channel {} DC level'.format(i),
                                get_cmd=dclevel_cmd + '?',
                                set_cmd=dclevel_cmd + ' {}',
                                vals=vals.Numbers(-0.25, 0.25),
                                get_parser=float)


            self.add_parameter('ch{}_highvoltage'.format(i),
                                label='Channel {} High Voltage'.format(i),
                                get_cmd=highvoltage_cmd + '?',
                                set_cmd=highvoltage_cmd + ' {}',
                                vals=vals.Numbers(-0.25, 0.25),
                                get_parser=float)


            self.add_parameter('ch{}_lowvoltage'.format(i),
                                label='Channel {} Low Voltage'.format(i),
                                get_cmd=lowvoltage_cmd + '?',
                                set_cmd=lowvoltage_cmd + ' {}',
                                vals=vals.Numbers(-0.25, 0.25),
                                get_parser=float)


            self.add_parameter('ch{}_offset'.format(i),
                                label='Channel {} amplitude'.format(i),
                                get_cmd=offset_cmd + '?',
                                set_cmd=offset_cmd + ' {}',
                                vals=vals.Numbers(-0.25, 0.25),
                                get_parser=float)


            self.add_parameter('ch{}_period'.format(i),
                                label='Channel {} Period'.format(i),
                                get_cmd=period_cmd + '?',
                                get_parser=float)


            self.add_parameter('ch{}_phase'.format(i),
                                label='Channel {} Phase'.format(i),
                                get_cmd=phase_cmd + '?',
                                set_cmd=phase_cmd + ' {}',
                                vals=vals.Numbers(-180.0,180.0),
                                get_parser=float)


            self.add_parameter('ch{}_symmetry'.format(i),
                                label='Channel {} Symmetry'.format(i),
                                get_cmd=symmetry_cmd + '?',
                                set_cmd=symmetry_cmd + ' {}',
                                vals=vals.Numbers(0, 100),
                                get_parser=float)


            self.add_parameter('ch{}_type'.format(i),
                                label='Channel {} Function Type'.format(i),
                                get_cmd=type_cmd + '?',
                                set_cmd=type_cmd + ' {}',
                                vals=vals.Enum(('SINE','SQU', 'TRI', 'NOIS', 'DC', 'GAUS', 'EXPR', 'EXPD', 'NONE')))




    def all_channels_on(self):

        for i in range(1, 3):
            self.set('ch{:d}_state'.format(i), 1)

    def all_channels_off(self):

        for i in range(1, 3):
            self.set('ch{}_state'.format(i), 0)
