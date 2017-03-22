from time import sleep
from functools import partial

import qcodes as qc

from qcodes.instrument_drivers.QDev.QDac import QDac
from qcodes.instrument_drivers.stanford_research.SR830 import SR830
from qcodes.instrument_drivers.devices import VoltageDivider


from qcodes.instrument.parameter import ManualParameter
from qcodes.instrument.parameter import StandardParameter
from qcodes.utils.validators import Enum
from qcodes.utils.wrappers import init, _plot_setup, _save_individual_plots


import logging as lg
import re
import time

# import T10_setup as t10
from configparser import ConfigParser

# Initialisation of intruments
qdac = QDac('qdac', 'ASRL6::INSTR', readcurrents=False)
lockin_topo = SR830('lockin_topo', 'GPIB10::7::INSTR')
lockin_left = SR830('lockin_l', 'GPIB10::14::INSTR')
lockin_right = SR830('lockin_r', 'GPIB10::10::INSTR')

CODING_MODE = False

# NOTE (giulio) this line is super important for metadata
# if one does not put the intruments in here there is no metadata!!
if CODING_MODE:
    lg.critical('You are currently in coding mode - instruments are not ' +
                'bound to Station and hence not logged properly.')
else:
    STATION = qc.Station(qdac, lockin_topo, lockin_right, lockin_left)

# Initialisation of the experiment

qc.init("./Basic_quantum_dot_measurements", "DRALD00ID3")
