# -*- coding: utf-8 -*-
"""
Created on Wed Nov 22 13:33:05 2017

@author: Jens
"""
import numpy as np
import qcodes as qc
import time
import matplotlib.pyplot as plt
plt.ion()

from pulsed_experiment_simple import (makeT2Sequence, sendSequenceToAWG,
                                      prepareZIUHFLIForAlazar, correctMeasTime,
                                      setupAlazarForT2, setupAlazarControllerForT2,
                                      AlazarValues)
from alazar_controllers.ATSChannelController import ATSChannelController
from alazar_controllers.alazar_channel import AlazarChannel
###############################################################################
#                                                                             #
#                         SET EXPERIMENT VARIABLES                            #
#                                                                             #
###############################################################################

hightimes = np.linspace(1e-9, 50e-6, 100)  # times the pulse is high/ON
trig_delay = 0E-6 #delay between the end of the pulse and the measurement trigger
RF_delay = 0E-6
meastime = 1e-6 # desired time the measurement, i.e. scope shot, should last (see note below)
extra_wait_time = 20e-6
no_of_avgs = 2000  # number of averages
pulsehigh =6E-3  # Voltage level of the pulse
pulselow = 0E-3
SR = 1e9  # sample rate of the AWG/Pulse
demod_freq = 247e6  # demodulation frequency (Hz)
compensation_ratio = 0  # the compensation pusle time ratio
outputpwr = -15  # the UHF-LI output power (dBm)
signalscaling = 20000

alazar_sampling_rate = 1_000_000_000

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
alazar.buffer_timeout._set(10000)
alazar.buffer_timeout._set_updated()
alazarcontroller = station['alazarcontroller']

# set alazar settigs
setupAlazarForT2(alazar, alazar_sampling_rate)
# set measuere time
alazarcontroller.int_time(meastime)
alazarcontroller.int_delay(0)

oldmeastime = meastime
# update the meastime with the real value based on allowed sampling rates
meastime = alazarcontroller.samples_per_record()/alazar.get_sample_rate()
cycletime = max(hightimes) + meastime + extra_wait_time  # Time of one pulse-measure cycle. Repeated no_of_avgs times
print("Updated meastime from {} to {}".format(oldmeastime, meastime))

# setup alazar channel with the right format
chan1 = AlazarChannel(alazarcontroller, 'T2', demod=False,
                      integrate_samples=False, average_buffers=False)
chan1.num_averages(no_of_avgs)
 
awg1.clock_freq(SR)
# make sequence
seq = makeT2Sequence(hightimes, trig_delay, RF_delay, meastime,
                     cycletime, pulsehigh, pulselow,
                     no_of_avgs, SR)
#seq.plotSequence()
#%%
# upload sequence
sendSequenceToAWG(awg1, seq)
#%%
# switch on channel 1
awg1.ch1_state(1)
# set the markers corectly
awg1.ch1_m1_high(2.6)
awg1.ch1_m2_high(2.6)
#%%
# prepare the scope on the ZI UHF-LI and the QCoDeS parameters
# holding the scope data
prepareZIUHFLIForAlazar(zi, demod_freq, outputpwr, signalscaling)
#%%
# define functions for running the awg with a hook from within the alazar
# define functions for running the awg with a hook from within the alazar
def run_awg():
    while awg1.state() == 'Running':
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
chan1.buffers_per_acquisition(len(hightimes))
chan1.prepare_channel()

start_width = hightimes[0]
stop_width = hightimes[-1]
no_of_widths = len(hightimes)

nsteps = 150

av = AlazarValues('alazar_values', alazarcontroller, chan1, save_raw_data=False)
av.prepare_alazar_values(hightimes)

try:
    #awg1.run()
    #execute_all_pulses()
#    sweep= keysightgen_left.ch1_frequency.sweep(1e3, 2e3, num=nsteps)
#    loop = qc.Loop(sweep, 0.01).each(av)
#    data = loop.run()
    nsteps = 200
    plot, data = do1d(qdac.ch48.v, -2.206, -2.2, nsteps, 0.001, av)
finally:
    # remove the post trigger again
    alazarcontroller.pre_acquire = dummy_func
    zi.signal_output1_on('OFF')
    av._rawdatacounter = 0
    awg1.all_channels_off()