from time import sleep
from functools import partial

from qcodes.instrument_drivers.devices import VoltageDivider

from qcodes.instrument.parameter import ManualParameter
from qcodes.instrument.parameter import StandardParameter
from qcodes.utils.validators import Enum

import re

from qcodes.utils.wrappers import _plot_setup, _save_individual_plots, do1d, do2d

##################################################
# Helper functions and wrappers


def print_voltages():
    """
    Prints qDac voltages of channels in use. Prints the status of those
    channels which were given a label in sample.config.
    """

    max_col_width = 38
    for channel in used_channels():
        col_width = max_col_width - len(QDAC[channel].label)
        mssg = ('Ch {: >2} - {} '.format(channel, QDAC[channel].label) +
                ': {:>{col_width}}'.format(QDAC[channel].get(),
                                           col_width=col_width))
        print(mssg)


def print_voltages_all():
    """
    Prints voltages of all qDac channels, also those which do not have 
    a label in sample.config
    """
    parnames = sorted([par for par in qdac.parameters.keys() if par.endswith('_v')])
    for parname in parnames:
        print('{}: {} V'.format(parname, qdac.parameters[parname].get()))
        
    check_unused_qdac_channels()


def set_all_voltages(voltage):
    """
    Set all qDac voltages to the same value. Voltage dividers and attenuators
    will be taken into account if they have been set.

    Args:
        voltage: voltage (V) value at sample, after dividers/attenuators 
    """
    for channel in range(1, 46):
        QDAC[channel].set(voltage)


def _unassign_qdac_slope(sweep_parameter):
    """
    Helper function for do1D and do2D to unassign QDac slopes.

    Args:
        sweep_parameter: Either a qdac.chXX_v parameter OR
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
    Resets one or multiple qDac channel slopes.
    Input any be a list of sweep_parameter or a single one

    Args:
        sweep_parameters: List or single value of either a
            dac.chXX_v parameter or a VoltageDivider instance.
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
        qdac_channel:   qdac.chXX_v parameter aka channel
        start:  Start of sweep (voltage (V) in most cases)
        stop:  End of sweep (voltage (V) in most cases))
        n_points (int):   Number of data points in a sweep/loop
        delay (s):  Delay between each data point
        ramp_slope (V/s): qDac slope at which qdac_channel will be
            ramped/swept

    Return:
        additional_delay: Additional delay needed to be added in Loop
                          in order to take into account the QDac ramping
                          time.
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


def do1d_M(inst_set, start, stop, n_points, delay, *inst_meas, ramp_slope=None):
    """
    QDev Majorana wrapper of qc.Loop. Sweeps one parameter while measuring one
    or more others.

    Args:
        inst_set:   Instrument parameter to sweep over
        start:  Start of sweep
        stop:   End of sweep
        n_points (int):   Number of data points to acquire
        delay (s):  Delay at every step
        inst_meas:  Any number of instrument parameters to measure
        ramp_slope (Optional[float]): QDac slope at which a qDac channel
            should be swept. In (V/s).

    Returns:
        plot, data : returns the plot and the dataset

    """
    if str(inst_set._instrument.__class__) == "<class 'qcodes.instrument_drivers.QDev.QDac.QDac'>":
        channel_id = int(re.findall('\d+', inst_set.name)[0])
        ramp_qdac(channel_id, start, ramp_slope)

    plot, data = do1d(inst_set, start, stop, n_points, delay, *inst_meas)

    return plot, data


def do2d_M(inst_set, start, stop, n_points, delay, inst_set2, start2, stop2,
           n_points2, delay2, *inst_meas, ramp_slope1=None, ramp_slope2=None):
    """
    qDev Majorana wrapper of a two dimensional Loop.
    Sweeps two parameters while measuring any number of instrument parameters.

    Args:
        inst_set:  Instrument parameter to sweep over; slow axis
        start:  Start of sweep
        stop:  End of sweep
        n_points (int):  Number of data points in outer loop; slow axis
        delay (s):  Delay between inner loops
        inst_set_2:  Second instrument to sweep over; fast axis
        start_2:  Start of sweep for second intsrument
        stop_2:  End of sweep for second instrument
        n_points2 (int):  Number of points of inner loop; slow axis
        delay_2 (s):  Delay between points on slow axis
        inst_meas: Any numnber of instrument parameters to measure
        ramp_slope1 (Optional[float]): qDac slope at which a qDac parameter
            (channel) should be swept; outer loop/slow axis. In (V/s).
        ramp_slope2 (Optional[float]): qDac slope at which a qDac parameter
            (channel) should be swept; inner loop/fast axis. In (V/s).

    Returns:
        plot, data : returns the plot and the dataset
    """

    if str(inst_set2._instrument.__class__) == "<class 'qcodes.instrument_drivers.QDev.QDac.QDac'>":
        channel_id = int(re.findall('\d+', inst_set2.name)[0])
        ramp_qdac(channel_id, start, ramp_slope1)

    # FUGLY hack... but how to do it properly?
    if str(inst_set._instrument.__class__) == "<class 'qcodes.instrument_drivers.QDev.QDac.QDac'>":
        channel_id = int(re.findall('\d+', inst_set.name)[0])
        ramp_qdac(channel_id, start, ramp_slope1)

    for inst in inst_meas:
        if getattr(inst, "setpoints", False):
            raise ValueError("3d plotting is not supported")

    plot, data = do2d(inst_set, start, stop, n_points, delay, inst_set2, start2, stop2, n_points2, delay2, *inst_meas)

    return plot, data


def ramp_qdac(chan, target_voltage, slope=None):
    """
    Ramps a qdac channel to the desired value. It waits until the value
    blocks is reached aka blocking.

    Args:
        chan (int): Qdac channel number
        target_voltage (float): Voltage to ramp to
        slope (Optional[float]): The slope in (V/s). If None, a slope is
            fetched from the QDAC dict.
    """

    if slope is None:
        try:
            slope = QDAC_SLOPES[chan]
        except KeyError:
            raise ValueError('No slope found in QDAC_SLOPES. '
                             'Please provide a slope!')

    # Make the ramp blocking, so that we may unassign the slope
    ramp_time = abs(qdac.parameters['ch{:02}_v'.format(chan)].get() -
                    target_voltage)/slope + 0.03

    qdac.parameters['ch{:02}_slope'.format(chan)].set(slope)
    qdac.parameters['ch{:02}_v'.format(chan)].set(target_voltage)
    sleep(ramp_time)
    qdac.parameters['ch{:02}_slope'.format(chan)].set('Inf')


def ramp_several_qdac_channels(loc, target_voltage, slope=None):
    """
    Ramp several QDac channels to the same value. Channels are ramped
    sequentially. Blocking until all channels are at desired value.

    Args:
        loc (list): List of channels to ramp
        target_voltage (float): Voltage to ramp to
        slope (Optional[float]): The slope in (V/s). If None, a slope is
            fetched from the QDAC dict
    """
    for ch in range(0, len(loc)):
        ramp_qdac(loc[ch], target_voltage, slope)