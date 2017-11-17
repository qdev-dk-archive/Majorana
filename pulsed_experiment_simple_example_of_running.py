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

hightime = 30e-6  # time the pulse is high/ON
trig_delay = 0  # delay between the end of the pulse and the measurement trigger
meastime = 400e-6  # desired time the measurement, i.e. scope shot, should last (see note below)
cycletime = hightime + meastime + 500e-6  # Time of one pulse-measure cycle. Repeated no_of_avgs times
no_of_avgs = 1000  # number of averages
pulsehigh = 100e-3  # Voltage level of the pulse
SR = 1e9  # sample rate of the AWG/Pulse
npts = 4096  # number of points in the scope trace (min.: 4096)
demod_freq = 250e6  # demodulation frequency (Hz)
compensation_ratio = 0  # the compensation pusle time ratio

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
                         cycletime, pulsehigh,
                         no_of_avgs, SR, compensation_ratio=compensation_ratio)

# visualise sequence
seq.plotSequence()

#%%
# upload sequence
sendSequenceToAWG(awg1, seq)

#%%
# switch on channel 1
awg1.ch1_state(1)

#%%

# prepare the scope on the ZI UHF-LI and the QCoDeS parameters
# holding the scope data
prepareZIUHFLI(zi, demod_freq, npts, SRstring, no_of_avgs, meastime)
zi.Scope.prepare_scope()
zi.scope_avg_ch1.make_setpoints(0, meastime, npts)

zi.Scope.add_post_trigger_action(awg1.run)  # make the awg run after arming the scope trigger

#%%
###############################################################################
#                                                                             #
#                               RUN A LOOP                                    #
#                                                                             #
###############################################################################

try:
    loop = qc.Loop(qdac.ch31.v.sweep(0, 1, num=200), delay=1).each(zi.scope_avg_ch1)
    data = loop.get_data_set(name='testsweep')
    plot = qc.QtPlot()  # create a plot
    plot.add(data.ziuhfli_scope_avg_ch1)  # add a graph to the plot
    _ = loop.with_bg_task(plot.update, plot.save).run()  # run the loop
finally:
    # remove the post trigger again
    zi.Scope._scopeactions = []
    zi.signal_output1_on('OFF')
