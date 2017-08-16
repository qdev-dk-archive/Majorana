import qcodes as qc
import os
import time
import logging
import re
import numpy as np
from functools import partial

import matplotlib as mpl
import matplotlib.pyplot as plt
mpl.rcParams['figure.figsize'] = (8, 3)
mpl.rcParams['figure.subplot.bottom'] = 0.15 
mpl.rcParams['font.size'] = 8

from qcodes.utils.configreader import Config
from qcodes.utils.wrappers import show_num

from majorana_wrappers import *
from reload_settings import *
from customised_instruments import *


from qcodes.instrument_drivers.Harvard.Decadac import Decadac
from qcodes.instrument_drivers.stanford_research.SR830 import SR830
from qcodes.instrument_drivers.stanford_research.SR830 import ChannelBuffer
# from qcodes.instrument_drivers.Keysight.Keysight_33500B import Keysight_33500B
# from qcodes.instrument_drivers.Keysight.Keysight_34465A import Keysight_34465A
# from qcodes.instrument_drivers.ZI.ZIUHFLI import ZIUHFLI
from qcodes.instrument_drivers.devices import VoltageDivider

# import qcodes.instrument_drivers.tektronix.Keithley_2600 as keith
# import qcodes.instrument_drivers.rohde_schwarz.SGS100A as sg
# import qcodes.instrument_drivers.tektronix.AWG5014 as awg
# from modules.pulsebuilding import broadbean as bb
from qcodes.instrument_drivers.oxford.mercuryiPS import MercuryiPS
# import qcodes.instrument_drivers.HP .HP8133A as hpsg
import qcodes.instrument_drivers.rohde_schwarz.ZNB as vna

from qcodes.utils.configreader import Config
from qcodes.utils.validators import Numbers
import logging
import re
import time
from functools import partial
import atexit

from conductance_measurements import do2Dconductance
from fast_diagrams import fast_charge_diagram

if __name__ == '__main__':

    #logging.basicConfig(filename=os.path.join(os.getcwd(), 'pythonlog.txt'), level=logging.DEBUG)

    init_log = logging.getLogger(__name__)

    # import T10_setup as t10
    config = Config('D:\MajoranacQED\Majorana\sample_T3.cfg')

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
    deca = Decadac('decadac', 'ASRL4::INSTR', config, update_currents=False)
    # deca = Decadac('Decadac', port=4, slot=0)
    lockin_1 = SR830_T10('lockin_1', 'GPIB10::2::INSTR')
    lockin_2 = SR830_T10('lockin_2', 'GPIB10::6::INSTR')

    # zi = ZIUHFLI_T10('ziuhfli', 'dev2189')
    # keysightgen_left = Keysight_33500B('keysight_gen_left', 'TCPIP0::192.168.15.101::inst0::INSTR')
    # keysightgen_left.add_function('sync_phase',call_cmd='SOURce1:PHASe:SYNChronize')
    # keysightgen_mid = Keysight_33500B('keysight_gen_mid', 'TCPIP0::192.168.15.114::inst0::INSTR')
    #keysightdmm_top = Keysight_34465A_T10('keysight_dmm_top', 'TCPIP0::192.168.15.111::inst0::INSTR')
    #keithleybot_a = keith.Keithley_2600('keithley_bot','TCPIP0::192.168.15.115::inst0::INSTR',"a")
    # awg1 = awg.Tektronix_AWG5014('AWG1','TCPIP0::192.168.15.105::inst0::INSTR',timeout=40)
    # sg1 = sg.RohdeSchwarz_SGS100A("sg1","TCPIP0::192.168.15.107::inst0::INSTR")
    # sg1.frequency.set_validator(Numbers(1e5,43.5e9))  # SMF100A can go to 43.5 GHz.
    # hpsg1 = hpsg.HP8133A("hpsg1", 'GPIB10::4::INSTR')  
  #  keysightgen_pulse = Keysight_33500B('keysight_gen_pulse', 'TCPIP0::192.168.15.109::inst0::INSTR')
    mercury = MercuryiPS(name='mercury',
                         address='172.20.10.148',
                         port=7020,
                         axes=['X', 'Y', 'Z'])

    v1 = vna.ZNB20('VNA', 'TCPIP0::192.168.15.103::inst0::INSTR')
   # keithleytop=keith.Keithley_2600('keithley_top',
   # 'TCPIP0::192.168.15.116::inst0::INSTR',"a,b")
   
    print('Querying all instrument parameters for metadata.'
          'This may take a while...')

    start = time.time()
    STATION = qc.Station( lockin_1, lockin_2, mercury, v1, deca)
                         # keysightgen_left, keysightgen_mid, keithleybot_a,
                         # keysightdmm_mid, keysightdmm_bot,
                         # keysightdmm_top, keysightdmm_mid, keysightdmm_bot,
                         # awg1, zi, sg1, hpsg1)# keysightgen_pulse)

    end = time.time()
    print("Querying took {} s".format(end-start))
    # Initialisation of the experiment

    end = time.time()
    print("done Querying all instruments took {}".format(end-start))
    qc.init("./data", "AcQED05_7", STATION,
            display_pdf=False, display_individual_pdf=False)

    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)

    config = Config('D:\MajoranacQED\Majorana\sample_T3.cfg')
    Config.default = config

    # qdac_chans_i = [39,18,12,10,9,7,47,22,48,43,42,37,36,35]
    # qdac_chans = []
    # for i in qdac_chans_i:
        # qdac_chans.append(qdac.channels[i-1].v)
    
    qc.Monitor(mercury.x_fld, mercury.y_fld, mercury.z_fld
                #*qdac_chans, #keithleybot_a.volt,
                )

     # Get the two global objects containing the instruments and settings


    # configs.reload()

    # one could put in some validation here if wanted


    lockin_1.acfactor = float(configs.get('Gain settings',
                                             'ac factor'))
    lockin_2.acfactor = float(configs.get('Gain settings',
                                              'ac factor'))


    lockin_1.ivgain = float(configs.get('Gain settings',
                                           'iv gain'))
    lockin_2.ivgain = float(configs.get('Gain settings',
                                            'iv gain'))



    # Try to close all instruments when exiting
    atexit.register(close_station, STATION)
