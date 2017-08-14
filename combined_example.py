import numpy as np

import qcodes as qc
from qcodes.tests.instrument_mocks import DummyInstrument

dac = DummyInstrument(name="dac", gates=['ch1', 'ch2'])  # The DAC voltage source
dmm = DummyInstrument(name="dmm", gates=['voltage'])  # The DMM voltage reader
import random
dmm.voltage.get =  lambda: random.randint(0, 100)

cp = qc.combine(dac.ch1, dac.ch2, name='combined_dac')

def printsomething():
    print("something")

def printelse():
    print("else")

printtask = qc.Task(printsomething)
printelse = qc.Task(printelse)


chan1_set = np.linspace(0, 10, 11).reshape(11,1)
chan2_set = np.linspace(0, 5, 11).reshape(11,1)
combine_setpoints = np.hstack((chan1_set, chan2_set))
loop = qc.Loop(cp.sweep(combine_setpoints), 0.1).each(printtask, printelse)
#loop = qc.Loop(cp.sweep(combine_setpoints), 0.1).each(printtask)
#loop = qc.Loop(dac.ch1.sweep(0, 1, 0.1), 0.1).each(printtask, printelse)


data = loop.run()

#print(data.dac_ch1_set)
print(data.dac_ch1)
print(data.dac_ch2)
