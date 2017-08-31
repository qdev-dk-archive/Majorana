import qcodes as qc
import time
import sys
import logging
import re
import atexit
import numpy as np
from functools import partial

import matplotlib as mpl
import matplotlib.pyplot as plt
mpl.rcParams['figure.figsize'] = (8, 3)
mpl.rcParams['figure.subplot.bottom'] = 0.15
mpl.rcParams['font.size'] = 8

from qcodes.utils.configreader import Config
from qcodes.utils.natalie_wrappers.file_setup import my_init

from majorana_wrappers import *
from reload_settings import *
from customised_instruments import SR830_T3, Decadac_T3
helper_fns_folder = r'D:\Transmon\Qcodes-contrib'
if helper_fns_folder not in sys.path:
    sys.path.insert(0, helper_fns_folder)
from qdev_transmon_helpers import *

from qcodes.instrument_drivers.oxford.mercuryiPS import MercuryiPS
import qcodes.instrument_drivers.rohde_schwarz.ZNB as VNA


from conductance_measurements import do2Dconductance

if __name__ == '__main__':

    init_log = logging.getLogger(__name__)

    config = Config('D:\MajoranacQED\Majorana\sample.config')
    Config.default = config

    def close_station(station):
        for comp in station.components:
            print("Closing connection to {}".format(comp))
            try:
                qc.Instrument.find_instrument(comp).close()
            except KeyError:
                pass

    if qc.Station.default:
        close_station(qc.Station.default)

    # Initialisation of intruments
    deca = Decadac_T3('Decadac', 'ASRL1::INSTR', config)

    lockin_2 = SR830_T3('lockin_2', 'GPIB0::2::INSTR', config)

    mercury = MercuryiPS(name='mercury',
                         address='172.20.10.148',
                         port=7020,
                         axes=['X', 'Y', 'Z'])

    vna = VNA.ZNB('VNA', 'TCPIP0::192.168.15.103::inst0::INSTR',
                  init_s_params=False)
    vna.add_channel('S21')

    print('Querying all instrument parameters for metadata.'
          'This may take a while...')

    start = time.time()

    STATION = qc.Station(lockin_2, mercury, deca, vna)
    lockin_2.acbias()
    deca.dcbias.get()
    deca.lcut.get()
    deca.rcut.get()
    deca.jj.get()
    deca.rplg.get()
    deca.lplg.get()
    mercury.x_fld()
    mercury.y_fld()
    mercury.z_fld()
    vna.rf_power()
    vna.channels.S21.npts()
    vna.channels.S21.power()
    vna.channels.S21.start()
    vna.channels.S21.stop()
    vna.channels.S21.avg()
    vna.channels.S21.bandwidth()

    end = time.time()
    print("done Querying all instruments took {}".format(end - start))
    my_init("natalie_playing", STATION,
            display_pdf=False, display_individual_pdf=False)

    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)

    qc.Monitor(mercury.x_fld, mercury.y_fld, mercury.z_fld,
               deca.dcbias, deca.lcut, deca.rcut, deca.jj, deca.rplg,
               deca.lplg,
               lockin_2.acbias,
               vna.rf_power,
               vna.channels.S21.npts,
               vna.channels.S21.power,
               vna.channels.S21.start,
               vna.channels.S21.stop,
               vna.channels.S21.avg,
               vna.channels.S21.bandwidth)

    # Try to close all instruments when exiting
    atexit.register(close_station, STATION)
