from time import sleep
from functools import partial

import qcodes as qc

from qcodes.instrument_drivers.QDev.QDac import QDac
from qcodes.instrument_drivers.stanford_research.SR830 import SR830
from qcodes.instrument_drivers.Keysight.Keysight_33500B import Keysight_33500B
from qcodes.instrument_drivers.ZI.ZIUHFLI import ZIUHFLI
from qcodes.instrument_drivers.devices import VoltageDivider

from .configreader import Config
from qcodes.instrument.parameter import ManualParameter
from qcodes.instrument.parameter import StandardParameter
from qcodes.utils.validators import Enum
from qcodes.utils.wrappers import init, _plot_setup, _save_individual_plots


import logging
import re
import time

init_log = logging.getLogger(__name__)

# import T10_setup as t10
config = Config('./MajoQubit/sample.config')

# Subclass the SR830


class SR830_T10(SR830):
    """
    An SR830 with a Voltage divider absorbed into it
    """

    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, **kwargs)

        # using the vocabulary of the config file
        self.ivgain = 1
        self.acfactor = 1
        self.dcfactor = 1

        self.amplitude_true = VoltageDivider(self.amplitude,
                                             self.acfactor)

        self.add_parameter('g',
                           label='{} conductance'.format(self.name),
                           # use lambda for late binding
                           get_cmd=lambda : self.get_conductance(self.amplitude_true(),
                                                                 self.ivgain),
                           unit='e^2/h',
                           get_parser=float)

    def _get_conductance(self, ac_excitation, iv_conv):
        """
        get_cmd for conductance parameter
        """
        resistance_quantum = 25.818e3  # [Ohm]
        i = self.X() / iv_conv
        # ac excitation voltage at the sample
        v_sample = ac_excitation()

        return (i/v_sample)*resistance_quantum

    @property
    def acfactor(self):
        return self.__acf

    @voltagegain.setter
    def voltagegain(self, acfactor):
        self.__acf = acfactor
        self.amplitude_true.division_value = acfactor


# Initialisation of intruments
qdac = QDac('qdac', 'ASRL6::INSTR', update_currents=False)
lockin_topo = SR830_T10('lockin_topo', 'GPIB10::7::INSTR')
lockin_right = SR830_T10('lockin_r', 'GPIB10::10::INSTR')
lockin_left = SR830_T10('lockin_l', 'GPIB10::14::INSTR')
keysight = Keysight_33500B('keysight', 'TCPIP0::A-33522B-12403::inst0::INSTR')
zi =  ZIUHFLI('ziuhfli', 'dev2189')

STATION = qc.Station(qdac, lockin_topo, lockin_right, lockin_left, keysight, zi)

# Initialisation of the experiment

qc.init("./MajoQubit", "DRALD_001D4", STATION)
