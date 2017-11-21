# an example of how to run the simple pulsed experiment

import matplotlib.pyplot as plt
plt.ion()

from pulsed_experiment_simple import (makeSimpleSequence, sendSequenceToAWG,
                                      prepareZIUHFLI, correctMeasTime)

###############################################################################
#                                                                             #
#                         SET EXPERIMENT VARIABLES                            #
#                                                                             #
###############################################################################

hightime = 250e-6  # time the pulse is high/ON
trig_delay = 0E-6  # delay between the end of the pulse and the measurement trigger
meastime = 1400e-6  # desired time the measurement, i.e. scope shot, should last (see note below)
cycletime = hightime + meastime + 1500e-6  # Time of one pulse-measure cycle. Repeated no_of_avgs times
no_of_avgs = 100  # number of averages
pulsehigh = 8E-3  # Voltage level of the pulse
pulselow = 0E-3
SR = 1e9  # sample rate of the AWG/Pulse
npts = 4096  # number of points in the scope trace (min.: 4096)
demod_freq = 247e6  # demodulation frequency (Hz)
compensation_ratio = 0  # the compensation pusle time ratio
outputpwr = -53  # the UHF-LI output power (dBm)

# NOTE: we can't have any measurement time we want, since
# there is only a fixed number of available sample rates
# and scope lengths on the ZI UHF-LI
# Therefore, we correct the meastime
oldmeastime = meastime
meastime, SRstring = correctMeasTime(oldmeastime, npts)
print('Corrected meastime from {:.6f} s to {:.6f} s.'.format(oldmeastime, meastime))
 
###############################################################################
#                                                                             #
#                            PREPARE INSTRUMENTS                              #
#                                                                             #
###############################################################################
# get instruments from the station
station = qc.Station.default
qdac = station['qdac']
awg1 = station['AWG1']
zi = station['ziuhfli']
awg1.clock_freq(SR)
# make sequence
seq = makeSimpleSequence(hightime, trig_delay, meastime,
                         cycletime, pulsehigh, pulselow,
                         no_of_avgs, SR, compensation_ratio=compensation_ratio)
#seq.plotSequence()
#%%
# upload sequence
sendSequenceToAWG(awg1, seq)
#%%
# switch on channel 1
awg1.ch1_state(1)
#%%
# prepare the scope on the ZI UHF-LI and the QCoDeS parameters
# holding the scope data
prepareZIUHFLI(zi, demod_freq, npts, SRstring, no_of_avgs, meastime, outputpwr)
zi.Scope.prepare_scope()
zi.scope_avg_ch1.make_setpoints(0, meastime, npts)
zi.Scope.add_post_trigger_action(awg1.run) # make the awg run after arming the scope trigger
#%%
###############################################################################
#                                                                             #
#                               RUN A MEASUREMENT                             #
#                                                                             #
###############################################################################
try:
    def make_things_right():
        prepareZIUHFLI(zi, demod_freq, npts, SRstring, no_of_avgs,
                       meastime, outputpwr)
        zi.Scope.prepare_scope()
        
    resetTask = qc.Task(make_things_right)
        
    do1d(qdac.ch48.v, -2.497, -2.503, 120, 1, zi.scope_avg_ch1, resetTask)
finally:
    # remove the post trigger again
    zi.Scope._scopeactions = []
    zi.signal_output1_on('OFF')