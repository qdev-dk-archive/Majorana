# an example of how to run the simple pulsed experiment

import matplotlib.pyplot as plt
plt.ion()

from pulsed_experiment_simple import (makeSimpleSequence, sendSequenceToAWG,
                                      prepareZIUHFLI, correctMeasTime, Scope_avg)

###############################################################################
#                                                                             #
#                         INSTRUMENT INITIALISATION                           #
#                                                                             #
###############################################################################

from qcodes.instrument_drivers.tektronix.AWG5014 import Tektronix_AWG5014
awg = Tektronix_AWG5014('awg', 'TCPIP0::192.168.15.107::inst0::INSTR')
from qcodes.instrument_drivers.ZI.ZIUHFLI import ZIUHFLI
zi = ZIUHFLI('uhf-li', 'dev2235')
from qcodes.instrument_drivers.QDev.QDac_channels import QDac
dac = QDac('dac', 'ASRL4::INSTR')

# Add averaged scope traces

try:
    zi.add_parameter('scope_avg_ch2',
                     channel=2,
                     label='',
                     parameter_class=Scope_avg)
except KeyError:
    pass
try:
    zi.add_parameter('scope_avg_ch1',
                     channel=1,
                     label='',
                     parameter_class=Scope_avg)
except KeyError:
    pass

###############################################################################
#                                                                             #
#                         SET EXPERIMENT VARIABLES                            #
#                                                                             #
###############################################################################

hightime = 10e-6  # time the pulse is high/ON
trig_delay = -25e-6  # delay between the end of the pulse and the measurement trigger
meastime = 50e-6  # desired time the measurement, i.e. scope shot, should last (see note below)
cycletime = 300e-6  # Time of one pulse-measure cycle. Repeated no_of_avgs times
no_of_avgs = 1  # number of averages
pulsehigh = 100e-3  # Voltage level of the pulse
SR = 1e9  # sample rate of the AWG/Pulse
npts = 4096  # number of points in the scope trace (min.: 4096)
demod_freq = 2e6  # demodulation frequency (Hz)
compesation_ratio = 0  # the compensation pusle time ratio

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


awg.clock_freq(SR)

# make sequence
seq = makeSimpleSequence(hightime, trig_delay, meastime,
                         cycletime, pulsehigh,
                         no_of_avgs, SR, compensation_ratio=2)

# visualise sequence
seq.plotSequence()

# upload sequence
sendSequenceToAWG(awg, seq)

# switch on channel 1
awg.ch1_state(1)

# prepare the scope on the ZI UHF-LI and the QCoDeS parameters
# holding the scope data
prepareZIUHFLI(zi, demod_freq, npts, SRstring, no_of_avgs, meastime)
zi.scope_avg_ch2.make_setpoints()
zi.Scope.prepare_scope()
zi.Scope.add_post_trigger_action(awg.run)  # make the awg run after arming the scope trigger

###############################################################################
#                                                                             #
#                               RUN A LOOP                                    #
#                                                                             #
###############################################################################


loop = qc.Loop(dac.ch01.v.sweep(0, 1, num=10), delay=1).each(zi.scope_avg_ch2)
data = loop.get_data_set(name='testsweep')
loop.run()
# remove the post trigger again
zi.Scope._scopeactions = []
