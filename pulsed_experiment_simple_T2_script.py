import numpy as np
import qcodes as qc
from pulsed_experiment_simple import (makeT2Sequence, sendSequenceToAWG,
                                      prepareZIUHFLI, correctMeasTime)



###############################################################################
#                                                                             #
#                         SET EXPERIMENT VARIABLES                            #
#                                                                             #
###############################################################################

hightimes = np.linspace(15e-6, 35e-6, 5)  # time the pulse is high/ON
trig_delay = 0e-6  # delay between the end of the pulse and the measurement trigger
meastime = 400e-6  # desired time the measurement, i.e. scope shot, should last (see note below)
cycletime = meastime + 550e-6  # Time of one pulse-measure cycle. Repeated no_of_avgs times
no_of_avgs = 1000  # number of averages
pulsehigh = 100e-3  # Voltage level of the pulse
pulselow = 0
SR = 1.2e9  # sample rate of the AWG/Pulse
npts = 4096  # number of points in the scope trace (min.: 4096)
demod_freq = 2e6  # demodulation frequency (Hz)
outputpwr = -50
single_channel = True  # whether to only use a single scope channel

###############################################################################
#                                                                             #
#                            PREPARE INSTRUMENTS                              #
#                                                                             #
###############################################################################
# get instruments from the station
station = qc.Station.default
qdac = station['qdac']
awg = station['AWG1']
zi = station['ziuhfli']
awg.clock_freq(SR)


# NOTE: we can't have any measurement time we want, since
# there is only a fixed number of available sample rates
# and scope lengths on the ZI UHF-LI
# Therefore, we correct the meastime
oldmeastime = meastime
meastime, SRstring = correctMeasTime(oldmeastime, npts)
print('Corrected meastime from {:.6f} s to {:.6f} s.'.format(oldmeastime, meastime))


#%%

seq = makeT2Sequence(hightimes, trig_delay, meastime,
                     cycletime, pulsehigh, pulselow,
                     no_of_avgs, SR)

seq.plotSequence()

#%%

sendSequenceToAWG(awg, seq)

#%%

prepareZIUHFLI(zi, demod_freq, npts, SRstring, no_of_avgs,
               meastime, outputpwr, single_channel=single_channel)
zi.Scope.prepare_scope()

awg.ch1_m1_high(1.5)
zi.Scope.add_post_trigger_action(awg.force_trigger)

#%%

# prepare the pusle width parameter


def step_awg_to_next_pulse(awg, no_of_pulses):

    counter = 0

    while True:
        target = (counter % (no_of_pulses)) + 2
        awg.set_sqel_goto_target_index(1, target)
        counter += 1
        yield


stepper = step_awg_to_next_pulse(awg, len(hightimes))


def step_setter(value):
    next(stepper)


step_param = qc.Parameter('Pulse width', label='Pulse width',
                          unit='s', set_cmd=step_setter)

#%%


# At least this code must be run on every measurement

# re-initialise the counter
stepper = step_awg_to_next_pulse(awg, len(hightimes))

step_param.set = step_setter


def make_things_right():
    prepareZIUHFLI(zi, demod_freq, npts, SRstring, no_of_avgs, meastime,
                   outputpwr, single_channel=single_channel)
    zi.Scope.prepare_scope()


resetTask = qc.Task(make_things_right)
make_things_right()
awg.ch1_state(1)
awg.run()

p1 = hightimes[0]
p2 = hightimes[-1]
num = len(hightimes)

try:
    innerloop = qc.Loop(step_param.sweep(p1, p2, num=num), delay=0.01).each(zi.scope_full_avg_ch1,
                                                                            resetTask)
    outerloop = qc.Loop(qdac.ch01.v.sweep(0, 1, num=25), delay=1).each(innerloop)
    data = outerloop.get_data_set(name='testsweep')
    plot = qc.QtPlot()
    plot.add(data.arrays['uhf-li_scope_full_avg_ch1'])  # add a graph to the plot
    _ = outerloop.with_bg_task(plot.update, plot.save).run()  # run the loop

    # I think the above will become
    #do2d(qdac.ch01.v, 0, 1, 25, 1, step_param, p1, p2, num, zi.scope_full_avg_ch1, resetTask)

finally:
    awg.set_sqel_goto_target_index(1, 2)
    awg.stop()
    zi.Scope._scopeactions = []
