from time import sleep
from functools import partial

import qcodes as qc

from qcodes.instrument_drivers.QDev.QDac import QDac
from qcodes.instrument_drivers.stanford_research.SR830 import SR830
from qcodes.instrument_drivers.Keysight.Keysight_33500B import Keysight_33500B
from qcodes.instrument_drivers.Keysight.Keysight_34465A import Keysight_34465A
from qcodes.instrument_drivers.ZI.ZIUHFLI  import ZIUHFLI
from qcodes.instrument_drivers.devices import VoltageDivider
from qcodes.instrument.parameter import ManualParameter
from qcodes.instrument.parameter import StandardParameter
from qcodes.utils.validators import Enum
from qcodes.utils.wrappers import init, _plot_setup, _save_individual_plots
from qcodes.instrument_drivers.tektronix.AWGFileParser import parse_awg_file 

import qcodes.instrument_drivers.tektronix.Keithley_2600 as keith
import qcodes.instrument_drivers.rohde_schwarz.SGS100A as sg  
import qcodes.instrument_drivers.tektronix.AWG5014 as awg  
import qcodes.instrument_drivers.HP .HP8133A as hpsg

import logging
import re
import time
from functools import partial

import numpy as np

from qcodes import IPInstrument, MultiParameter
from qcodes.utils.validators import Enum
from qcodes.instrument_drivers.oxford.mercuryiPS import MercuryiPS

init_log = logging.getLogger(__name__)

# import T10_setup as t10
from configparser import ConfigParser

# Initialisation of intruments

qdac = QDac('qdac', 'ASRL6::INSTR', update_currents=False)
lockin_topo = SR830('lockin_topo', 'GPIB10::7::INSTR')
lockin_right = SR830('lockin_r', 'GPIB10::10::INSTR')
lockin_left = SR830('lockin_l', 'GPIB10::14::INSTR')

sg1 = sg.RohdeSchwarz_SGS100A("sg1","TCPIP0::192.168.15.107::inst0::INSTR")
keysightgen_left = Keysight_33500B('keysight_gen_left', 'TCPIP0::192.168.15.101::inst0::INSTR')
keysightgen_mid = Keysight_33500B('keysighDRt_gen_mid', 'TCPIP0::192.168.15.114::inst0::INSTR')
keysightgen_right = Keysight_33500B('keysight_gen_right', 'TCPIP0::192.168.15.109::inst0::INSTR')

keysightdmm_top = Keysight_34465A('keysight_dmm_top', 'TCPIP0::192.168.15.111::inst0::INSTR')
keysightdmm_mid = Keysight_34465A('keysight_dmm_mid', 'TCPIP0::192.168.15.112::inst0::INSTR')
keysightdmm_bot = Keysight_34465A('keysight_dmm_bot', 'TCPIP0::192.168.15.113::inst0::INSTR')

#keithleytop=keith.Keithley_2600('keithley_top', 'TCPIP0::192.168.15.116::inst0::INSTR',"a,b")
keithleybot=keith.Keithley_2600('keithley_bot', 'TCPIP0::192.168.15.115::inst0::INSTR',"a,b")

mercury = MercuryiPS(name='mercury', address='192.168.15.102', port=7020, axes=['X', 'Y', 'Z'])

hpsg1 = hpsg.HP8133A("hpsg1", 'GPIB10::4::INSTR')
zi = ZIUHFLI('ziuhfli', 'dev2189')
awg1 = awg.Tektronix_AWG5014('AWG1', 'TCPIP0::192.168.15.105::inst0::INSTR', timeout=40)
awg2 = awg.Tektronix_AWG5014('AWG2', 'TCPIP0::192.168.15.106::inst0::INSTR', timeout=180)
CODING_MODE = False

# NOTE (giulio) this line is super important for metadata
# if one does not put the intruments in here there is no metadata!!
if CODING_MODE:
    init_log.critical('You are currently in coding mode - instruments are not ' +
                      'bound to Station and hence not logged properly.')
else:
    print('Querying all instrument parameters for metadata. This may take a while...')
    STATION = qc.Station(qdac, lockin_topo, lockin_right, lockin_left, keysightgen_left,keysightgen_mid,keysightgen_right,
                         keysightdmm_top,keysightdmm_mid,keysightdmm_bot,awg1,awg2,sg1, zi,keithleybot,mercury,hpsg1)

# Initialisation of the experiment

qc.init("./MajoQubit", "DVZ_004d1", STATION)
