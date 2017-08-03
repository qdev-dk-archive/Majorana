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

from qcodes.utils.configreader import Config
from qcodes.utils.wrappers import show_num
from modules.Majorana.majorana_wrappers import *
from modules.Majorana.reload_settings import *

from qcodes.instrument_drivers.QDev.QDac_channels import QDac
from qcodes.instrument_drivers.stanford_research.SR830 import SR830
from qcodes.instrument_drivers.stanford_research.SR830 import ChannelBuffer
from qcodes.instrument_drivers.Keysight.Keysight_33500B import Keysight_33500B
from qcodes.instrument_drivers.Keysight.Keysight_34465A import Keysight_34465A
from qcodes.instrument_drivers.ZI.ZIUHFLI import ZIUHFLI
from qcodes.instrument_drivers.devices import VoltageDivider
import qcodes.instrument_drivers.tektronix.Keithley_2600 as keith
import qcodes.instrument_drivers.rohde_schwarz.SGS100A as sg
import qcodes.instrument_drivers.tektronix.AWG5014 as awg
from modules.pulsebuilding import broadbean as bb
from qcodes.instrument_drivers.oxford.mercuryiPS import MercuryiPS
import qcodes.instrument_drivers.HP .HP8133A as hpsg
#import qcodes.instrument_drivers.rohde_schwarz.ZNB20 as vna


# A conductance buffer, needed for the faster 2D conductance measurements
# (Wecker style)
class ConductanceBuffer(ChannelBuffer):
    """
    A full-buffered version of the conductance based on an
    array of X measurements

    We basically just slightly tweak the get method
    """

    def __init__(self, name: str, instrument: 'SR830_T10', **kwargs):
        super().__init__(name, instrument, channel=1)
        self.unit = ('e^2/h')

    def get(self):
        # If X is not being measured, complain
        if self._instrument.ch1_display() != 'X':
            raise ValueError('Can not return conductance since X is not '
                             'being measured on channel 1.')

        resistance_quantum = 25.818e3  # (Ohm)
        xarray = super().get()
        iv_conv = self._instrument.ivgain
        ac_excitation = self._instrument.amplitude_true()

        gs = xarray/iv_conv/ac_excitation*resistance_quantum

        return gs

# Subclass the SR830

class SR830_T10(SR830):
    """
    An SR830 with the following super powers:
        - a Voltage divider
        - An I/V converter
        - A conductance buffer
    """

    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, **kwargs)

        # using the vocabulary of the config file
        self.ivgain = 1
        self.__acf = 1

        self.add_parameter('amplitude_true',
                           parameter_class=VoltageDivider,
                           v1=self.amplitude,
                           division_value=self.acfactor)

        self.add_parameter('g',
                           label='{} conductance'.format(self.name),
                           # use lambda for late binding
                           get_cmd=self._get_conductance,
                           unit='e^2/h',
                           get_parser=float)

        self.add_parameter('conductance',
                           label='{} conductance'.format(self.name),
                           parameter_class=ConductanceBuffer)

    def _get_conductance(self):
        """
        get_cmd for conductance parameter
        """
        resistance_quantum = 25.818e3  # (Ohm)
        i = self.X() / self.ivgain
        # ac excitation voltage at the sample
        v_sample = self.amplitude_true()

        return (i/v_sample)*resistance_quantum

    @property
    def acfactor(self):
        return self.__acf

    @acfactor.setter
    def acfactor(self, acfactor):
        self.__acf = acfactor
        self.amplitude_true.division_value = acfactor


# Subclass the QDAC


class QDAC_T10(QDac):
    """
    A QDac with three voltage dividers
    """
    def __init__(self, name, address, config, **kwargs):
        super().__init__(name, address, **kwargs)

        # Define the named channels

        topo_channel = int(config.get('Channel Parameters',
                                      'topo bias channel'))
        topo_channel = self.channels[topo_channel-1].v

        self.add_parameter('current_bias',
                           label='{} conductance'.format(self.name),
                           # use lambda for late binding
                           get_cmd=lambda: self.channels.chan40.v.get()/10E6*1E9,
                           set_cmd=lambda value: self.channels.chan40.v.set(value*1E-9*10E6),
                           unit='nA',
                           get_parser=float)

        # sens_r_channel = int(config.get('Channel Parameters',
        #                                'right sensor bias channel'))
        # sens_r_channel = self.channels[sens_r_channel-1].v

        # sens_l_channel = int(config.get('Channel Parameters',
        #                                 'left sensor bias channel'))
        # sens_l_channel = self.channels[sens_l_channel-1].v

        self.topo_bias = VoltageDivider(topo_channel,
                                        float(config.get('Gain settings',
                                                         'dc factor topo')))
        # self.sens_r_bias = VoltageDivider(sens_r_channel,
        #                                  float(config.get('Gain settings',
        #                                                   'dc factor right')))
        # self.sens_l_bias = VoltageDivider(sens_l_channel,
        #                                  float(config.get('Gain settings',
        #                                                    'dc factor left')))


# Subclass the DMM


class Keysight_34465A_T10(Keysight_34465A):
    """
    A Keysight DMM with an added I-V converter
    """
    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, **kwargs)

        self.iv_conv = 1

        self.add_parameter('ivconv',
                           label='Current',
                           unit='pA',
                           get_cmd=self._get_current,
                           set_cmd=None)

    def _get_current(self):
        """
        get_cmd for dmm readout of IV_TAMP parameter
        """
        return self.volt()/self.iv_conv*1E12


if __name__ == '__main__':

    init_log = logging.getLogger(__name__)

    # import T10_setup as t10
    config = Config('A:\qcodes_experiments\modules\Majorana\sample.config')


    # Initialisation of intruments
    qdac = QDAC_T10('qdac', 'ASRL8::INSTR', config, update_currents=False)
    lockin_topo = SR830_T10('lockin_topo', 'GPIB10::7::INSTR')
    lockin_left = SR830_T10('lockin_l', 'GPIB10::10::INSTR')
    lockin_right = SR830_T10('lockin_r', 'GPIB10::14::INSTR')
    zi = ZIUHFLI('ziuhfli', 'dev2189')
    keysightgen_left = Keysight_33500B('keysight_gen_left', 'TCPIP0::192.168.15.101::inst0::INSTR')
    keysightgen_left.add_function('sync_phase',call_cmd='SOURce1:PHASe:SYNChronize')
    keysightgen_mid = Keysight_33500B('keysight_gen_mid', 'TCPIP0::192.168.15.114::inst0::INSTR')
    #keysightdmm_top = Keysight_34465A_T10('keysight_dmm_top', 'TCPIP0::192.168.15.111::inst0::INSTR')
    keysightdmm_mid = Keysight_34465A_T10('keysight_dmm_mid', 'TCPIP0::192.168.15.112::inst0::INSTR')
    keysightdmm_bot = Keysight_34465A_T10('keysight_dmm_bot','TCPIP0::192.168.15.113::inst0::INSTR')
    keithleybot_a = keith.Keithley_2600('keithley_bot','TCPIP0::192.168.15.115::inst0::INSTR',"a")
    awg1 = awg.Tektronix_AWG5014('AWG1','TCPIP0::192.168.15.105::inst0::INSTR',timeout=40)
    awg2 = awg.Tektronix_AWG5014('AWG2','TCPIP0::192.168.15.106::inst0::INSTR',timeout=180)
    sg1 = sg.RohdeSchwarz_SGS100A("sg1","TCPIP0::192.168.15.107::inst0::INSTR")
    sg1.frequency.set_validator(Numbers(1e5,43.5e9))  # SMF100A can go to 43.5 GHz.
    hpsg1 = hpsg.HP8133A("hpsg1", 'GPIB10::4::INSTR')  
  #  keysightgen_pulse = Keysight_33500B('keysight_gen_pulse', 'TCPIP0::192.168.15.109::inst0::INSTR')
    mercury = MercuryiPS(name='mercury',
                         address='192.168.15.102',
                         port=7020,
                         axes=['X', 'Y', 'Z'])

   # v1 = vna.ZNB20('VNA', 'TCPIP0::192.168.15.108::inst0::INSTR')
   # keithleytop=keith.Keithley_2600('keithley_top',
   # 'TCPIP0::192.168.15.116::inst0::INSTR',"a,b")
   
    print('Querying all instrument parameters for metadata.'
          'This may take a while...')
    start = time.time()
    STATION = qc.Station(qdac, lockin_topo, lockin_right, lockin_left,
                         keysightgen_left, keysightgen_mid, keithleybot_a,
                         keysightdmm_mid, keysightdmm_bot,
                         #keysightdmm_top, keysightdmm_mid, keysightdmm_bot,
                         awg1, awg2, zi, mercury, sg1, hpsg1)# keysightgen_pulse)

    # Initialisation of the experiment
    end = time.time()
    print("done Querying all instruments took {}".format(end-start))
    qc.init("./MajoQubit", "DVZ_MCQ002B1", STATION)

    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)

    config = Config('A:\qcodes_experiments\modules\Majorana\sample.config')
    Config.default = config

    qdac_chans_i = [39,18,12,10,9,7,47,22,48,43,42,37,36,35]
    qdac_chans = []
    for i in range(len(qdac_chans_i)):
        chan = 'ch{:02d}_v'.format(qdac_chans_i[i])
        qdac_chans.append(getattr(qdac, chan))
    
    qc.Monitor(*qdac_chans, keithleybot_a.volt, zi.oscillator1_freq, zi.oscillator2_freq, 
               zi.scope_channel1_input, zi.scope_channel2_input, mercury.x_fld, mercury.y_fld, mercury.z_fld,
               sg1.status, sg1.power, sg1.frequency, hpsg1.output, hpsg1.amplitude, hpsg1.width,hpsg1.frequency)

    reload_SR830_settings()
    reload_QDAC_settings()

# setup fast diagrams
    zi.oscillator1_freq(278e6)
    zi.oscillator2_freq(275e6)

    zi.demod1_timeconstant(5e-7)
    zi.demod5_timeconstant(5e-7)

    zi.demod1_order(5)
    zi.demod5_order(5)

    zi.demod1_signalin('Sig In 1')
    zi.demod5_signalin('Sig In 1')

    zi.signal_output1_ampdef('dBm')
    zi.signal_output1_amplitude(-60)
    zi.signal_output1_offset(0)

    zi.signal_output2_ampdef('dBm')
    zi.signal_output2_amplitude(-50)
    zi.signal_output2_offset(0)
 