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

hightime = 250e-6  # time the pulse is high/ON
trig_delay = -100E-6  # delay between the end of the pulse and the measurement trigger
meastime = 1400e-6  # desired time the measurement, i.e. scope shot, should last (see note below)
extra_wait_time = 150e-6
no_of_avgs = 100  # number of averages
pulsehigh = 8E-3  # Voltage level of the pulse
pulselow = 0E-3
SR = 1e9  # sample rate of the AWG/Pulse
demod_freq = 1e6#247e6  # demodulation frequency (Hz)
compensation_ratio = 0  # the compensation pusle time ratio
outputpwr = -53  # the UHF-LI output power (dBm)

alazar_sampling_rate = 1_000_000

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
seq = makeT1Sequence(hightime, trig_delay, meastime,
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
awg1.ch1_m2_high(2.5)
#%%
# prepare the scope on the ZI UHF-LI and the QCoDeS parameters
# holding the scope data
prepareZIUHFLIForAlazar(zi, demod_freq, outputpwr)
#%%
# define functions for running the awg with a hook from within the alazar
def run_awg():
    while awg1.state() == 'Running':
        time.sleep(10e-3)
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
    nsteps = 10
    plot, data = do1d(keysightgen_left.ch1_frequency, 1e3, 2e3, nsteps, 0.01, chan1.data)
finally:
    # remove the post trigger again
    alazarcontroller.pre_acquire = dummy_func
    zi.signal_output1_on('OFF')
    