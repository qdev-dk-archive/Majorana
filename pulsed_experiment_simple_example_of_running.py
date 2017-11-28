# an example of how to run the simple pulsed experiment
import time
import matplotlib.pyplot as plt
plt.ion()

from pulsed_experiment_simple import (makeSimpleSequence, sendSequenceToAWG,
                                      prepareZIUHFLI, correctMeasTime)

###############################################################################
#                                                                             #
#                         SET EXPERIMENT VARIABLES                            #
#                                                                             #
###############################################################################

hightime = 100e-6  # time the pulse is high/ON
trig_delay = 0E-6  # delay between the end of the pulse and the measurement trigger
meastime = 200e-6  # desired time the measurement, i.e. scope shot, should last (see note below)
cycletime = hightime + meastime + 1500e-6  # Time of one pulse-measure cycle. Repeated no_of_avgs times
no_of_avgs = 300  # number of averages
pulsehigh = -7E-3  # Voltage level of the pulse
pulselow = 0E-3
SR = 1e9  # sample rate of the AWG/Pulse
npts = 4096  # number of points in the scope trace (min.: 4096)
demod_freq = 247e6  # demodulation frequency (Hz)
compensation_ratio = 0  # the compensation pusle time ratio
outputpwr = -56  # the UHF-LI output power (dBm)


qdac_channel = qdac.ch48.v
qdac_start = -2.164
qdac_stop = -2.158
qdac_pnts = 80

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
def run_awg():
    while awg1.state() == 'Running':
        time.sleep(10e-3)
    awg1.run()

zi.Scope.add_post_trigger_action(run_awg) # make the awg run after arming the scope trigger
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

        
    do1d(qdac_channel, qdac_start, qdac_stop, qdac_pnts, 1, zi.scope_avg_ch1, resetTask)

finally:
    # remove the post trigger again
    zi.Scope._scopeactions = []
    zi.signal_output1_on('OFF')
