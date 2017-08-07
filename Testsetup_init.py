import qcodes as qc

from qcodes.instrument_drivers.QDev.QDac_channels import QDac
from qcodes.instrument_drivers.stanford_research.SR830 import SR830
from qcodes.instrument_drivers.stanford_research.SR830 import ChannelBuffer
from qcodes.instrument_drivers.Keysight.Keysight_33500B import Keysight_33500B
from qcodes.instrument_drivers.Keysight.Keysight_34465A import Keysight_34465A
from qcodes.instrument_drivers.ZI.ZIUHFLI import ZIUHFLI
from qcodes.instrument_drivers.devices import VoltageDivider
from qcodes.instrument_drivers.oxford.mercuryiPS import MercuryiPS

from qcodes.utils.configreader import Config

import qcodes.instrument_drivers.tektronix.Keithley_2600 as keith
import qcodes.instrument_drivers.rohde_schwarz.SGS100A as sg
import qcodes.instrument_drivers.tektronix.AWG5014 as awg
import qcodes.instrument_drivers.HP.HP8133A as hpsg
import qcodes.instrument_drivers.rohde_schwarz.ZNB as vna

import logging
import re
import time
from functools import partial

from majorana_wrappers import *
from reload_settings import *
from customised_instruments import *

import atexit

if __name__ == '__main__':

    init_log = logging.getLogger(__name__)

    # import T10_setup as t10
    config = Config('sample.config')

    def close_station(station):
        for comp in station.components:
            print("Closing connection to {}".format(comp))
            qc.Instrument.find_instrument(comp).close()

    if qc.Station.default:
        close_station(qc.Station.default)

    # Initialisation of intruments
    qdac = QDAC_T10('qdac', 'ASRL6::INSTR', config, update_currents=False)
    lockin = SR830_T10('lockin_topo', 'GPIB0::8::INSTR')
    zi = ZIUHFLI('ziuhfli', 'dev2235')
    keysightgen_1 = Keysight_33500B('keysight_gen_1',
                                    'TCPIP0::192.168.15.108::inst0::INSTR')
    keysightgen_2 = Keysight_33500B('keysight_gen_2',
                                    'TCPIP0::192.168.15.112::inst0::INSTR')
    keysightdmm_1 = Keysight_34465A_T10('keysight_dmm_1',
                                        'TCPIP0::192.168.15.110::inst0::INSTR')
    keysightdmm_2 = Keysight_34465A_T10('keysight_dmm_2',
                                        'TCPIP0::192.168.15.115::inst0::INSTR')
    keysightdmm_3 = Keysight_34465A_T10('keysight_dmm_3',
                                        'TCPIP0::192.168.15.117::inst0::INSTR')
    keithley_1 = keith.Keithley_2600('keithley_1',
                                     'TCPIP0::192.168.15.114::inst0::INSTR',
                                     "a")
    keithley_2 = keith.Keithley_2600('keithley_2',
                                     'TCPIP0::192.168.15.116::inst0::INSTR',
                                     "a")

    print('Querying all instrument parameters for metadata.'
          'This may take a while...')

    start = time.time()
    STATION = qc.Station(qdac, lockin, zi, 
                         keysightgen_1, keysightgen_2, 
                         keysightdmm_1, keysightdmm_2, keysightdmm_3,
                         keithley_1, keithley_2)

    end = time.time()
    print("Querying took {} s".format(end-start))

    # Try to close all instruments when exiting
    atexit.register(close_station, STATION)

    # Initialisation of the experiment
    qc.init("./MajoQubit", "DVZ_MCQ002A1", STATION, annotate_image=False)