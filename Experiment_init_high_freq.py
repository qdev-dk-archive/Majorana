import qcodes as qc
import time
import sys
import logging
import numpy as np
from os.path import sep
import matplotlib as mpl
import matplotlib.pyplot as plt
mpl.rcParams['figure.figsize'] = (8, 3)
mpl.rcParams['figure.subplot.bottom'] = 0.15
mpl.rcParams['font.size'] = 8

from wrappers.file_setup import CURRENT_EXPERIMENT
from wrappers.configreader import Config
from wrappers.file_setup import close_station, my_init
from qcodes import ManualParameter

from wrappers import *
from majorana_wrappers import *
from reload_settings import *
from customised_instruments import SR830_T3, Decadac_T3, AWG5014_T3, \
    ATS9360Controller_T3, AlazarTech_ATS9360_T3, VNA_T3
helper_fns_folder = r'D:\Transmon\Qcodes-contrib'
if helper_fns_folder not in sys.path:
    sys.path.insert(0, helper_fns_folder)
from qdev_transmon_helpers import *

from qcodes.instrument_drivers.oxford.mercuryiPS import MercuryiPS
from qcodes.instrument_drivers.rohde_schwarz.SGS100A import RohdeSchwarz_SGS100A


if __name__ == '__main__':

    init_log = logging.getLogger(__name__)

    # Close existing connections if present
    if qc.Station.default:
        close_station(qc.Station.default)

    STATION = qc.Station()

    # Set up folders, settings and logging for the experiment
    my_init("", STATION,
            pdf_folder=True, analysis_folder=True,
            temp_dict_folder=True, waveforms_folder=True,
            annotate_image=False, mainfolder=None, display_pdf=True,
            display_individual_pdf=False, qubit_count=4,
            plot_x_position=0.66)

    # Load config from experiment file, if none found then uses one in mainfolder
    cfg_file = "{}{}".format(CURRENT_EXPERIMENT['exp_folder'], 'instr.config')
    instr_config = Config(cfg_file, isdefault=True)
    if len(instr_config.sections()) == 0:
        cfg_file = sep.join([CURRENT_EXPERIMENT['mainfolder'], 'instr.config'])
        instr_config = Config(cfg_file, isdefault=True)

    # Initialise intruments
    deca = Decadac_T2('Decadac', 'ASRL1::INSTR', instr_config)
    alazar = AlazarTech_ATS9360_T3('alazar', seq_mode='off')
    ave_ctrl = ATS9360Controller_T3('ave_ctrl', alazar, ctrl_type='ave')
    rec_ctrl = ATS9360Controller_T3('rec_ctrl', alazar, ctrl_type='rec')
    samp_ctrl = ATS9360Controller_T3('samp_ctrl', alazar, ctrl_type='samp')
    localos = RohdeSchwarz_SGS100A('localos_rs',
                                   'TCPIP0::192.168.15.104::inst0::INSTR')
    cavity_source = RohdeSchwarz_SGS100A('cavity_rs',
                                         'TCPIP0::192.168.15.105::inst0::INSTR')
    qubit_source = RohdeSchwarz_SGS100A('qubit_source',
                                        'TCPIP0::192.168.15.105::inst0::INSTR')
    awg1 = AWG5014_T3(
        'awg1', 'TCPIP0::192.168.15.101::inst0::INSTR', timeout=40)
    awg2 = AWG5014_T3(
        'awg2', 'TCPIP0::192.168.15.101::inst0::INSTR', timeout=40)
    vna = VNA_T3('VNA', 'TCPIP0::192.168.15.103::inst0::INSTR', S21=True)
    dummy_time = ManualParameter('dummy_time')

    # Add instruments to station so that metadata for them is recorded at
    # each measurement and connections are closed at end of session
    STATION.add_component(deca)
    STATION.add_component(vna)
    STATION.add_component(alazar)
    STATION.add_component(ave_ctrl)
    STATION.add_component(rec_ctrl)
    STATION.add_component(samp_ctrl)
    STATION.add_component(localos)
    STATION.add_component(cavity_source)
    STATION.add_component(qubit_source)
    STATION.add_component(awg1)
    STATION.add_component(awg2)

    # Set log level
    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)

    # Get parameter values to populate monitor
    print('Querying all instrument parameters for metadata.'
          'This may take a while...')
    start = time.time()

#    lockin_2.acbias()
    deca.channels[0].get()
    deca.channels[1].get()
    deca.channels[2].get()
    deca.channels[3].get()
    vna.rf_power()
    vna.channels.S21.npts()
    vna.channels.S21.power()
    vna.channels.S21.start()
    vna.channels.S21.stop()
    vna.channels.S21.avg()
    vna.channels.S21.bandwidth()
    cavity_source.status()
    cavity_source.power()
    cavity_source.frequency()
    localos.status()
    localos.power()
    localos.frequency()
    qubit_source.status()
    qubit_source.power()
    qubit_source.frequency()
    awg1.state()
    awg1.ch1_amp()
    awg1.ch1_state()
    awg1.ch2_amp()
    awg1.ch2_state()
    awg1.ch3_amp()
    awg1.ch3_state()
    awg1.ch4_amp()
    awg1.ch4_state()
    awg2.state()
    awg2.ch1_amp()
    awg2.ch1_state()
    awg2.ch2_amp()
    awg2.ch2_state()
    awg2.ch3_amp()
    awg2.ch3_state()
    awg2.ch4_amp()
    awg2.ch4_state()

    end = time.time()

    print("done Querying all instruments took {}".format(end - start))

    # Put parameters into monitor
    Monitor(deca.channels[0], deca.channels[1],
            deca.channels[2], deca.channels[3],
            samp_ctrl.num_avg, samp_ctrl.int_time, samp_ctrl.int_delay,
            rec_ctrl.num_avg, rec_ctrl.int_time, rec_ctrl.int_delay,
            ave_ctrl.num_avg, ave_ctrl.int_time, ave_ctrl.int_delay,
            awg1.state, awg1.ch1_amp, awg1.ch1_state, awg1.ch2_amp,
            awg1.ch3_state, awg1.ch4_amp, awg1.ch4_state,
            awg2.state, awg2.ch1_amp, awg2.ch1_state, awg2.ch2_amp,
            awg2.ch3_state, awg2.ch4_amp, awg2.ch4_state,
            alazar.seq_mode,
            cavity_source.frequency, cavity_source.power, cavity_source.status,
            qubit_source.frequency, qubit_source.power, qubit_source.status,
            localos.frequency, localos.power, localos.status,
            vna.channels.S21.power, vna.channels.S21.start,
            vna.channels.S21.stop, vna.channels.S21.avg,
            vna.channels.S21.bandwidth, vna.channels.S21.npts)
