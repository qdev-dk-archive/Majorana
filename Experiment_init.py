from time import sleep
from functools import partial

import qcodes as qc

from qcodes.instrument_drivers.QDev.QDac import QDac
from qcodes.instrument_drivers.stanford_research.SR830 import SR830
from qcodes.instrument_drivers.devices import VoltageDivider


from qcodes.instrument.parameter import ManualParameter
from qcodes.instrument.parameter import StandardParameter
from qcodes.utils.validators import Enum
from qcodes.utils.wrappers import init, _plot_setup


import logging as lg
import re
import time

import T10_setup as t10

# Initialisation of intruments
qdac = QDac('qdac', 'ASRL6::INSTR', readcurrents=False)
lockin_topo = SR830('lockin_topo', 'GPIB10::7::INSTR')
lockin_left = SR830('lockin_l', 'GPIB10::14::INSTR')
lockin_right = SR830('lockin_r', 'GPIB10::10::INSTR')


CODING_MODE = False


# NOTE (giulio) this line is super important for metadata
# if one does not put the intruments in here there is no metadata!!
if CODING_MODE:
    lg.critical('You are currently in coding mode - instruments are not ' +
                'bound to Station and hence not logged properly.')
else:
    STATION = qc.Station(qdac, lockin_topo, lockin_right, lockin_left)


qc.init("./Basic_quantum_dot_msrmts", "DRALD00ID3")

# Useful dicts:
BIAS_CH = [t10.SD_TOPO, t10.SD_SENS_L, t10.SD_SENS_R]
USED_QDAC_CHANNELS = sorted(t10.QDAC_LABELS.keys())
VOLTAGES = [qdac.parameters['ch{:02}_v'.format(ii)] for ii in USED_QDAC_CHANNELS]
QDAC = dict(zip(USED_QDAC_CHANNELS, VOLTAGES))

for ii in USED_QDAC_CHANNELS:
    QDAC[ii].label = t10.QDAC_LABELS[ii]
# A dictionary with max ramp speed for qDac channels.
# Bias channels, backgate and cutters/plungers have their own values respectively
QDAC_SLOPES = dict(zip(USED_QDAC_CHANNELS, len(USED_QDAC_CHANNELS)*[t10.MAX_RAMPSPEED_QCH]))
QDAC_SLOPES[t10.BG] = t10.MAX_RAMPSPEED_BG
for ii in BIAS_CH:
    QDAC_SLOPES[ii] = t10.MAX_RAMPSPEED_BIAS


# I/V converter for all three Lockins
IV_CONV_GAIN_TOPO = ManualParameter('IVgain topo bias',
                                    unit='V/A',
                                    vals=Enum(1e5, 1e6, 1e7, 1e8, 1e9))
IV_CONV_GAIN_TOPO(t10.IV_GAIN_TOPO)

IV_CONV_GAIN_R = ManualParameter('IVgain sens right',
                                 unit='V/A',
                                 vals=Enum(1e5, 1e6, 1e7, 1e8, 1e9))
IV_CONV_GAIN_R(t10.IV_GAIN_R)

IV_CONV_GAIN_L = ManualParameter('IVgain sens left',
                                 unit='V/A',
                                 vals=Enum(1e5, 1e6, 1e7, 1e8, 1e9))
IV_CONV_GAIN_L(t10.IV_GAIN_L)


# Taking into account all voltage deviders (AC and DC for all lockins)

AC_EXCITATION_TOPO = VoltageDivider(lockin_topo.amplitude, t10.AC_FACTOR_TOPO)
AC_EXCITATION_R = VoltageDivider(lockin_right.amplitude, t10.AC_FACTOR_R)
AC_EXCITATION_L = VoltageDivider(lockin_left.amplitude, t10.AC_FACTOR_L)

#q5 =  VoltageDivider(QDAC[5], t10.DC_FACTOR_CH)
#q48 = VoltageDivider(QDAC[48], t10.DC_FACTOR_CH)
#q45 = VoltageDivider(QDAC[45], t10.DC_FACTOR_CH)
#q12 = VoltageDivider(QDAC[12], t10.DC_FACTOR_CH)
#q17 = VoltageDivider(QDAC[17], t10.DC_FACTOR_CH)
#q24 = VoltageDivider(QDAC[24], t10.DC_FACTOR_CH2)



topo_bias = VoltageDivider(QDAC[t10.SD_TOPO], t10.DC_FACTOR_TOPO)
sens_r_bias = VoltageDivider(QDAC[t10.SD_SENS_R], t10.DC_FACTOR_R)
sens_l_bias = VoltageDivider(QDAC[t10.SD_SENS_L], t10.DC_FACTOR_L)


# Adding a parameter for conductance measurement

def get_conductance(lockin, ac_excitation, iv_conv):
    """
    get_cmd for conductance parameter
    """
    resistance_quantum = 25.818e3  # [Ohm]
    i = lockin.X() / iv_conv()
    # ac excitation voltage at the sample
    v_sample = ac_excitation()
    return (i/v_sample)*resistance_quantum


lockin_topo.add_parameter(name='g',
                          label='Topo g (e^2/h)',
                          unit='',
                          get_cmd=partial(get_conductance, lockin_topo, AC_EXCITATION_TOPO,
                                          IV_CONV_GAIN_TOPO),
                          set_cmd=None)

lockin_right.add_parameter(name='g',
                           label='Sensor right g (e^2/h)',
                           unit='',
                           get_cmd=partial(get_conductance, lockin_right, AC_EXCITATION_R,
                                           IV_CONV_GAIN_R),
                           set_cmd=None)

lockin_left.add_parameter(name='g',
                          label='Sensor left g (e^2/h)',
                          unit='',
                          get_cmd=partial(get_conductance, lockin_left, AC_EXCITATION_R,
                                          IV_CONV_GAIN_L),
                          set_cmd=None)

# Helper functions

def print_voltages():
    """
    Print qDac voltages
    """

    max_col_width = 38 # max([len(list(QDAC_LABELS[ii])) for ii in USED_QDAC_CHANNELS])
    for channel in USED_QDAC_CHANNELS:
        col_width = max_col_width - len(QDAC[channel].label)
        if channel in BIAS_CH:
            divided_voltage = {t10.SD_TOPO: topo_bias, t10.SD_SENS_L: sens_l_bias, t10.SD_SENS_R: sens_r_bias}
            print('Ch {: >2}_at sample - '.format(channel) + QDAC[channel].label +
                  ': {:>{col_width}}'.format(divided_voltage[channel](), col_width=col_width))
        else:
            print('Ch {: >2} - '.format(channel) + QDAC[channel].label +
                  ': {:>{col_width}}'.format(QDAC[channel].get(), col_width=col_width))

def set_all_voltages(voltage):
    """
    Set all voltages on qDac to a given voltage
    """
    for channel in range(1, 46):
        QDAC[channel].set(voltage)


def unassign_qdac_slope(qdac_channel):
    """
    Args:
        qdac_channel:
    """

    if not qdac_channel._instrument == qdac:
        Raise ValueError("Can't unassign slope from a non-qdac instrument!")

    channel_id = int(re.findall('\d+', qdac_channel.name)[0])
    slope_parameter = qdac.parameters['ch{0:02d}_slope'.format(channel_id)]
    slope_parameter('Inf')


def prepare_qdac(qdac_channel, start, stop, n_points, delay, ramp_slope):
    """
    Args:
        inst_set:  Instrument to sweep over
        start:  Start of sweep
        stop:  End of sweep
        division:  Spacing between values
        delay:  Delay at every step
        ramp_slope:

    Return:
        additional_delay: Additional delay we need to add in the Loop in order to take
                          into account the ramping time of the QDac
    """

    channel_id = int(re.findall('\d+', qdac_channel.name)[0])
    if ramp_slope is None:
        ramp_slope = QDAC_SLOPES[channel_id]

    slope_parameter = qdac.parameters['ch{0:02d}_slope'.format(channel_id)]
    slope_parameter(ramp_slope)

    init_ramp_time = abs(start-qdac_channel.get())/ramp_slope
    qdac_channel.set(start)
    time.sleep(init_ramp_time)

    additional_delay_perPoint = (abs(stop-start)/n_points)/ramp_slope
    return additional_delay_perPoint, ramp_slope


def do1d_M(inst_set, start, stop, n_points, delay, *inst_meas, ramp_slope=None):
    """
    Args:
        inst_set:  Instrument to sweep over
        start:  Start of sweep
        stop:  End of sweep
        division:  Spacing between values
        delay:  Delay at every step
        *inst_meas:  any number of instrument to measure
        ramp_slope:

    Returns:
        plot, data : returns the plot and the dataset

    """
    if inst_set._instrument == qdac:
        additional_delay_perPoint, _ = prepare_qdac(inst_set, start, stop, n_points, delay, ramp_slope)
        delay += additional_delay_perPoint

    loop = qc.Loop(inst_set.sweep(start, stop, num=n_points), delay).each(*inst_meas)
    data = loop.get_data_set()
    plot = _plot_setup(data, inst_meas)

    try:
        _ = loop.with_bg_task(plot.update, plot.save).run()
    except KeyboardInterrupt:
        # Clean up QDac, if it was used
        try:
            unassign_qdac_slope(inst_set)
        except ValueError:
            pass

        print("Measurement Interrupted")

    if inst_set._instrument == qdac:
        unassign_qdac_slope(inst_set)

    return plot, data


def do2d_M(inst_set, start, stop, n_points, delay, inst_set2, start2, stop2,
           n_points2, delay2, *inst_meas, ramp_slope1=None, ramp_slope2=None, inter_loop_sleep_time=0):
    """
    Args:
        inst_set:  Instrument to sweep over
        start:  Start of sweep
        stop:  End of sweep
        division:  Spacing between values
        delay:  Delay at every step
        inst_set_2:  Second instrument to sweep over
        start_2:  Start of sweep for second intrument
        stop_2:  End of sweep for second intrument
        division_2:  Spacing between values for second intrument
        delay_2:  Delay at every step for second intrument
        *inst_meas:
        ramp_slope:

    Returns:
        plot, data : returns the plot and the dataset
    """

    if inst_set2._instrument == qdac:
        additional_delay_perPoint2, ramp_slope2 = prepare_qdac(inst_set2, start2, stop2,
                                                      n_points2, delay2, ramp_slope2)
        delay2 += additional_delay_perPoint2
        # print('delay2: {}'.format(delay2))
        inter_loop_sleep_time += abs(stop2-start2)/ramp_slope2 + 0.05

    if inst_set._instrument == qdac:
        additional_delay_perPoint, ramp_slope1 = prepare_qdac(inst_set, start, stop,
                                                     n_points, delay, ramp_slope1)
        delay = max(delay, inter_loop_sleep_time)
        # print('delay1: {}'.format(delay))


    for inst in inst_meas:
        if getattr(inst, "setpoints", False):
            raise ValueError("3d plotting is not supported")

    loop = qc.Loop(inst_set.sweep(start, stop, num=n_points), delay).each(
        qc.Loop(inst_set2.sweep(start2, stop2, num=n_points2), delay2).each(
        *inst_meas
        # qc.Task(inst_set2.set, start))
        #qc.Wait(inter_loop_sleep_time)
        ))

    data = loop.get_data_set()
    plot = _plot_setup(data, inst_meas)
    try:
        _ = loop.with_bg_task(plot.update, plot.save).run()
    except KeyboardInterrupt:
        print("Measurement Interrupted")

    if inst_set._instrument == qdac:
        unassign_qdac_slope(inst_set)

    if inst_set2._instrument == qdac:
        unassign_qdac_slope(inst_set2)

    return plot, data
