# -*- coding: utf-8 -*-
"""
Created on Wed Nov 22 13:33:05 2017

@author: Jens
"""
import qcodes as qc
import time
import matplotlib.pyplot as plt
plt.ion()

from pulsed_experiment_simple import (makeT1Sequence, sendSequenceToAWG,
                                      prepareZIUHFLIForAlazar, correctMeasTime,
                                      setupAlazarForT1, setupAlazarControllerForT1)
from alazar_controllers.ATSChannelController import ATSChannelController
from alazar_controllers.alazar_channel import AlazarChannel
###############################################################################
#                                                                             #
#                         SET EXPERIMENT VARIABLES                            #
#                                                                             #
###############################################################################

hightime = 500e-6  # time the pulse is high/ON
trig_delay = 0E-6  # delay between the end of the pulse and the measurement trigger
RF_delay = 0e-6
meastime = 500e-6  # desired time the measurement, i.e. scope shot, should last (see note below)
extra_wait_time = 0e-6
no_of_avgs = 500  # number of averages
pulsehigh = 6E-3  # Voltage level of the pulse
pulselow = 0E-3
SR = 1e9  # sample rate of the AWG/Pulse
demod_freq = 247e6  # demodulation frequency (Hz)
compensation_ratio = 0  # the compensation pusle time ratio
outputpwr = -15  # the UHF-LI output power (dBm)
signalscaling = 2000

alazar_sampling_rate = 10_000_000

###############################################################################
#                                                                             #
#                            PREPARE INSTRUMENTS                              #
#                                                                             #
###############################################################################
# get instruments from the station
station = qc.Station.default
#qdac = station['qdac']
awg1 = station['AWG1']
zi = station['ziuhfli']
alazar = station['alazar']
alazarcontroller = station['alazarcontroller']

# set alazar settigs
setupAlazarForT1(alazar, alazar_sampling_rate)
# set measuere time
alazarcontroller.int_time(meastime)
alazarcontroller.int_delay(0)

oldmeastime = meastime
# update the meastime with the real value based on allowed sampling rates
meastime = alazarcontroller.samples_per_record()/alazar.get_sample_rate()
cycletime = hightime + meastime + extra_wait_time  # Time of one pulse-measure cycle. Repeated no_of_avgs times
print("Updated meastime from {} to {}".format(oldmeastime, meastime))

# setup alazar channel with the right format
chan1 = AlazarChannel(alazarcontroller, 'mychan', demod=False, integrate_samples=False)
chan1.num_averages(no_of_avgs)
 
awg1.clock_freq(SR)
# make sequence
seq = makeT1Sequence(hightime, trig_delay, RF_delay,
                     meastime,
                     cycletime, pulsehigh, pulselow,
                     no_of_avgs, SR, compensation_ratio=compensation_ratio)
#seq.plotSequence()
#%%
# upload sequence
sendSequenceToAWG(awg1, seq)
#%%
# switch on channel 1
awg1.ch1_state(1)
# set the marker corectly
awg1.ch1_m1_high(2.3)
awg1.ch1_m2_high(2.6)
#%%
# prepare the scope on the ZI UHF-LI and the QCoDeS parameters
# holding the scope data
prepareZIUHFLIForAlazar(zi, demod_freq, outputpwr, signalscaling)
#%%
# define functions for running the awg with a hook from within the alazar
def run_awg():
    while awg1.state() == 'Running':
       # print('AWG not ready')
        time.sleep(50e-3)
    awg1.run()

def dummy_func():
    pass

alazarcontroller.pre_acquire = run_awg

#%%
###############################################################################
#                                                                             #
#                               RUN A MEASUREMENT                             #
#                                                                             #
###############################################################################

chan1.prepare_channel()

try:
    #qc.Measure(chan1.data)
    nsteps = 150
    plot, data = do1d(qdac.ch48.v, -2.204, -2.198, nsteps, 0.001, chan1.data)
finally:
    # remove the post trigger again
    alazarcontroller.pre_acquire = dummy_func
    zi.signal_output1_on('OFF')
    awg1.all_channels_off()
    