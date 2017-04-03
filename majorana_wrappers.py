from time import sleep
from functools import partial

from qcodes.instrument_drivers.devices import VoltageDivider

from qcodes.instrument.parameter import ManualParameter
from qcodes.instrument.parameter import StandardParameter
from qcodes.utils.validators import Enum

import re

from qcodes.utils.wrappers import _plot_setup, _save_individual_plots
from qcodes.utils.wrappers import _select_plottables
import qcodes as qc

import logging

log = logging.getLogger(__name__)

##################################################
# Helper functions and wrappers


def print_voltages():
    """
    Print qDac voltages
    """

    max_col_width = 38
    for channel in used_channels():
        col_width = max_col_width - len(QDAC[channel].label)
        mssg = ('Ch {: >2} - {} '.format(channel, QDAC[channel].label) +
                ': {:>{col_width}}'.format(QDAC[channel].get(),
                                           col_width=col_width))
        print(mssg)


def set_all_voltages(voltage):
    """
    Set all AT SAMPLE voltages from QDac channels to the given voltage
    """
    for channel in range(1, 46):
        QDAC[channel].set(voltage)


def _unassign_qdac_slope(sweep_parameter):
    """
    Helper function for do1D and do2D to unassign QDac slopes

    The sweep_parameter is either a qdac.chXX_v parameter OR
    a VoltageDivider instance.
    """

    paramclass = str(sweep_parameter._instrument.__class__) 

    if not paramclass == "<class 'qcodes.instrument_drivers.QDev.QDac.QDac'>":
        raise ValueError("Can't unassign slope from a non-qdac instrument!")

    # check wether we are dealing with a voltage divider, and if so,
    # dif out the qdac parameter
    if isinstance(sweep_parameter, VoltageDivider):
        sweep_parameter = sweep_parameter.v1

    channel_id = int(re.findall('\d+', sweep_parameter.name)[0])
    slope_parameter = qdac.parameters['ch{0:02d}_slope'.format(channel_id)]
    slope_parameter('Inf')


def reset_qdac(sweep_parameters):
    """
    Reset the qdac channels (unassigns slopes)
    Input amy be a list of sweep_parameter or a single one
    """
    if not isinstance(sweep_parameters, list):
        sweep_parameters = [sweep_parameters]

    for swp in sweep_parameters:
        try:
            _unassign_qdac_slope(swp)
        except ValueError:
            pass


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
        additional_delay: Additional delay we need to add in the Loop
                          in order to take into account the ramping
                          time of the QDac
    """

    channel_id = int(re.findall('\d+', qdac_channel.name)[0])
    if ramp_slope is None:
        ramp_slope = QDAC_SLOPES[channel_id]

    slope_parameter = qdac.parameters['ch{0:02d}_slope'.format(channel_id)]
    slope_parameter(ramp_slope)

    try:
        init_ramp_time = abs(start-qdac_channel.get())/ramp_slope
    except TypeError:
        init_ramp_time = 0

    qdac_channel.set(start)
    time.sleep(init_ramp_time)

    try:
        additional_delay_perPoint = (abs(stop-start)/n_points)/ramp_slope
    except TypeError:
        additional_delay_perPoint = 0

    return additional_delay_perPoint, ramp_slope


def do1d(inst_set, start, stop, n_points, delay, *inst_meas):
    """
    Args:
        inst_set:  Instrument to sweep over
        start:  Start of sweep
        stop:  End of sweep
        division:  Spacing between values
        delay:  Delay at every step
        *inst_meas:  any number of instrument to measure
    Returns:
        plot, data : returns the plot and the dataset
    """

    loop = qc.Loop(inst_set.sweep(start, stop, num=n_points),
                   delay).each(*inst_meas)

    data = loop.get_data_set()
    plottables = _select_plottables(inst_meas)
    plot = _plot_setup(data, plottables)

    try:
        _ = loop.with_bg_task(plot.update, plot.save).run()
    except KeyboardInterrupt:
        print("Measurement Interrupted")

    _save_individual_plots(data, plottables)

    cur_exp = qc.utils.wrappers.CURRENT_EXPERIMENT
    if cur_exp.get('device_image'):
        log.debug('Saving annotated device image')
        qc.utils.wrappers.save_device_image()

    return plot, data


def do1d_M(inst_set, start, stop, n_points, delay, *inst_meas, ramp_slope=None):
    """
    !!!!!EXPERIMENTAL!!!!
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
    if str(inst_set._instrument.__class__) == "<class 'qcodes.instrument_drivers.QDev.QDac.QDac'>":
        additional_delay_perPoint, _ = prepare_qdac(inst_set, start,
                                                    stop, n_points, delay,
                                                    ramp_slope)
        delay += additional_delay_perPoint

    loop = qc.Loop(inst_set.sweep(start, stop, num=n_points),
                   delay).each(*inst_meas)
    data = loop.get_data_set()
    plottables = _select_plottables(inst_meas)
    plot = _plot_setup(data, plottables)

    try:
        _ = loop.with_bg_task(plot.update, plot.save).run()
    except KeyboardInterrupt:
        print("Measurement Interrupted")

    reset_qdac(inst_set)  # sets channel slopes to 'Inf' (binds to DC)
    _save_individual_plots(data, plottables)

    cur_exp = qc.utils.wrappers.CURRENT_EXPERIMENT
    if cur_exp.get('device_image'):
        log.debug('Saving annotated device image')
        qc.utils.wrappers.save_device_image()

    return plot, data

def do2d(inst_set, start, stop, n_points, delay, inst_set2, start2, stop2,
           n_points2, delay2, *inst_meas):
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

    for inst in inst_meas:
        if getattr(inst, "setpoints", False):
            raise ValueError("3d plotting is not supported")

    loop = qc.Loop(inst_set.sweep(start, stop, num=n_points), delay).loop(inst_set2.sweep(start2, stop2, num=n_points2), delay2).each(
             *inst_meas)


    data = loop.get_data_set()
    plottables = _select_plottables(inst_meas)
    plot = _plot_setup(data, plottables)
    try:
        _ = loop.with_bg_task(plot.update, plot.save).run()
    except KeyboardInterrupt:
        print("Measurement Interrupted")

    _save_individual_plots(data, plottables)

    cur_exp = qc.utils.wrappers.CURRENT_EXPERIMENT
    if cur_exp.get('device_image'):
        log.debug('Saving annotated device image')
        qc.utils.wrappers.save_device_image()

    return plot, data



def do2d_M(inst_set, start, stop, n_points, delay, inst_set2, start2, stop2,
           n_points2, delay2, *inst_meas, ramp_slope1=None, ramp_slope2=None,
           inter_loop_sleep_time=0):
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

    if str(inst_set2._instrument.__class__) == "<class 'qcodes.instrument_drivers.QDev.QDac.QDac'>":
        additional_delay_perPoint2, ramp_slope2 = prepare_qdac(inst_set2, start2,
                                                               stop2,
                                                               n_points2, delay2,
                                                               ramp_slope2)
        delay2 += additional_delay_perPoint2
        # print('delay2: {}'.format(delay2))
        try:
            inter_loop_sleep_time += abs(stop2-start2)/ramp_slope2 + 0.05
        except TypeError:
            inter_loop_sleep_time += 0.05

    # FUGLY hack... but how to do it properly?
    if str(inst_set._instrument.__class__) == "<class 'qcodes.instrument_drivers.QDev.QDac.QDac'>":
        additional_delay_perPoint, ramp_slope1 = prepare_qdac(inst_set, start, stop,
                                                     n_points, delay, ramp_slope1)
        delay = max(delay, inter_loop_sleep_time)
        # print('delay1: {}'.format(delay))

    for inst in inst_meas:
        if getattr(inst, "setpoints", False):
            raise ValueError("3d plotting is not supported")

    loop = qc.Loop(inst_set.sweep(start, stop, num=n_points), delay).loop(inst_set2.sweep(start2, stop2, num=n_points2), delay2).each(
             *inst_meas)
            # qc.Task(inst_set2.set, start))
            # qc.Wait(inter_loop_sleep_time)


    data = loop.get_data_set()
    plottables = _select_plottables(inst_meas)
    plot = _plot_setup(data, plottables)
    try:
        _ = loop.with_bg_task(plot.update, plot.save).run()
    except KeyboardInterrupt:
        print("Measurement Interrupted")

    reset_qdac([inst_set, inst_set2])
    _save_individual_plots(data, plottables)

    cur_exp = qc.utils.wrappers.CURRENT_EXPERIMENT
    if cur_exp.get('device_image'):
        log.debug('Saving annotated device image')
        qc.utils.wrappers.save_device_image()

    return plot, data
