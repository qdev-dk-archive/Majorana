from functools import partial

import qcodes as qc

from qcodes.instrument_drivers.QDev.QDac import QDac
from qcodes.instrument_drivers.Keysight.Keysight_33500B import Keysight_33500B
from qcodes.instrument_drivers.ZI.ZIUHFLI import ZIUHFLI


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
qdac = QDac('qdac', 'ASRL6::INSTR', update_currents=False)
zi = ZIUHFLI('uhfli', 'dev2235')
keysight = Keysight_33500B('keysight','TCPIP0::K-33522B-00256::inst0::INSTR')

CODING_MODE = True

# NOTE (giulio) this line is super important for metadata
# if one does not put the intruments in here there is no metadata!!
if CODING_MODE:
    lg.critical('You are currently in coding mode - instruments are not ' +
                'bound to Station and hence not logged properly.')
else:
    STATION = qc.Station(zi, keysight, qdac)

# Initialisation of the experiment

qc.init("./Basic_quantum_dot_measurements", "DRALD00ID3")