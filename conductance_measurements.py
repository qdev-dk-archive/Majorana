# Module file for conductance measurements with the
# SR830. Implementing the good ideas of Dave Wecker

from typing import Union, Optional
from time import sleep
import numpy as np
import qcodes as qc
from qcodes.instrument.parameter import Parameter
from qcodes.utils.wrappers import _do_measurement
from qcodes.instrument_drivers.QDev.QDac import QDac
from qcodes.instrument_drivers.QDev.QDac_channels import QDac as QDacch

try:
    from modules.Majorana.Experiment_init import SR830_T10
except ImportError:
    from Experiment_init import SR830_T10

def do2Dconductance(outer_param: Parameter,
                    outer_start: Union[float, int],
                    outer_stop: Union[float, int],
                    outer_npts: int,
                    inner_param: Parameter,
                    inner_start: Union[float, int],
                    inner_stop: Union[float, int],
                    inner_npts: int,
                    *lockins: SR830_T10,
                    delay: Optional[float]=None):
    """
    Function to perform a sped-up 2D conductance measurement

    Args:
        outer_param: The outer loop voltage parameter
        outer_start: The outer loop start voltage
        outer_stop: The outer loop stop voltage
        outer_npts: The number of points in the outer loop
        inner_param: The inner loop voltage parameter
        inner_start: The inner loop start voltage
        inner_stop: The inner loop stop voltage
        inner_npts: The number of points in the inner loop
        *lockins: One or more lock-in amplifier to mesasure the conductance with.
        delay: Delay to wait after setting inner parameter before triggering lockin.
          If None will use default delay, otherwise used the supplied.
    """
    station = qc.Station.default

    if outer_param._instrument.name not in station.components:
        raise KeyError('Unknown instrument for outer parameter. '
                       'Please add that instrument to the station.')
    if inner_param._instrument.name not in station.components:
        raise KeyError('Unknown instrument for inner parameter. '
                       'Please add that instrument to the station.')
    for sr in lockins:
        # Validate the instruments
        if sr.name not in station.components:
            raise KeyError('Unknown lock-in! Refusing to proceed until the '
                           'lock-in has been added to the station.')

        tau = sr.time_constant()
        min_delay = 0.002  # what's the physics behind this number?
        if delay is None:
            delay = tau + min_delay
        # Prepare for the first iteration
        # Some of these things have to be repeated during the loop
        sr.buffer_SR('Trigger')
        set_sr = sr.buffer_SR()
        if set_sr != 'Trigger':
            raise RuntimeError("Could not set sample rate correctly. "
                               "Try lockin.write('*CLS') and rerun")
        sr.buffer_reset()
        sr.buffer_start()
        sr.ext_trigger('TTL rising')
        sr.conductance.shape = (inner_npts,)
        sr.conductance.setpoint_names = (inner_param.name,)
        sr.conductance.setpoint_labels = (inner_param.label,)
        sr.conductance.setpoint_units = ('V',)
        sr.conductance.setpoints = (tuple(np.linspace(inner_start,
                                                      inner_stop,
                                                      inner_npts)),)

    def trigger():
        for sr in lockins:
            sleep(delay)
            sr.send_trigger()

    def prepare_buffer():
        for sr in lockins:
            # here it should be okay to call ch1_databuffer... I think...
            sr.ch1_databuffer.prepare_buffer_readout()
            # For the dataset/plotting, put in the correct setpoints
            sr.conductance.setpoint_names = (inner_param.name,)
            sr.conductance.setpoint_labels = (inner_param.label,)
            sr.conductance.setpoint_units = ('V',)
            sr.conductance.setpoints = (tuple(np.linspace(inner_start,
                                                          inner_stop,
                                                          inner_npts)),)

    def start_buffer():
        for sr in lockins:
            sr.buffer_start()
            sr.conductance.shape = (inner_npts,)  # This is something

    def reset_buffer():
        for sr in lockins:
            sr.buffer_reset()
    conductance_list = [sr.conductance for sr in lockins]
    trig_task = qc.Task(trigger)
    reset_task = qc.Task(reset_buffer)
    start_task = qc.Task(start_buffer)
    inner_loop = qc.Loop(inner_param.sweep(inner_start,
                                           inner_stop,
                                           num=inner_npts)).each(trig_task)
    outer_loop = qc.Loop(outer_param.sweep(outer_start,
                                           outer_stop,
                                           num=outer_npts)).each(start_task,
                                                                 inner_loop,
                                                                 *conductance_list,
                                                                 reset_task)

    set_params = ((inner_param, inner_start, inner_stop),
                  (outer_param, outer_start, outer_stop))
    meas_params = tuple(conductance_list)
    prepare_buffer()
    qdac = None
    # ensure that any waveform generator is unbound from the qdac channels that we step if
    # we are stepping the qdac
    if isinstance(inner_param._instrument, QDac) or isinstance(inner_param._instrument, QDacch):
        qdac = inner_param._instrument
        # remove this stupid hack once we have real channels
        qdac.parameters["ch{}_slope".format(inner_param.name[2:4])]('Inf')
    if isinstance(outer_param._instrument, QDac) or isinstance(outer_param._instrument, QDacch):
        qdac = outer_param._instrument
        # remove this stupid hack once we have real channels
        qdac.parameters["ch{}_slope".format(outer_param.name[2:4])]('Inf')
    if qdac:
        qdac.fast_voltage_set(True)  # now that we have unbound the function generators
                                     # we don't need to do it in the loop
        qdac.voltage_set_dont_wait(False)  # this is un safe and highly experimental
    _do_measurement(outer_loop, set_params, meas_params, do_plots=True)
