from Pulsed_Experiments_scripts import doPulsedExperiment

from qcodes.instrument_drivers.ZI.ZIUHFLI import ZIUHFLI
import qcodes.instrument_drivers.tektronix.AWG5014 as awg
from qcodes.instrument_drivers.keysight.Keysight_33500B import Keysight_33500B

zi = ZIUHFLI('ZIUHFLI', 'dev2235') # 192.168.15.106
awg1 = awg.Tektronix_AWG5014('AWG1', 'TCPIP0::192.168.15.107::inst0::INSTR', timeout=40)
ks = Keysight_33500B('ks', 'TCPIP0::192.168.15.108::inst0::INSTR')


doPulsedExperiment(fast_axis='ramp',
                   slow_axis='dt',
                   slow_start=1e-6,
                   slow_stop=2e-6,
                   slow_npts=5,
                   fast_start=0,
                   fast_stop=0.1,
                   fast_nptp=3,
                   n_avgs=1,
                   pts_per_shot=4096,
                   hightime=1e-6,
                   meastime=1e-6,
                   trig_delay=1e-6,
                   demod_freq=10e6
                   )

