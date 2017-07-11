
from qcodes.utils.wrappers import do1d
import qcodes as qc

from typing import Sequence, Optional, Union
from functools import wraps
import numpy as np
from qcodes.instrument.parameter import StandardParameter
from qcodes.utils.wrappers import do1d, do1dcombined
from qcodes.instrument_drivers.Keysight.Keysight_33500B_channels import KeysightChannel
from customised_instruments import Scope_avg, ZIUHFLI_T10


def prepare_measurement(keysight_low_V: float, keysight_high_V: float,
                        scope_avger: Scope_avg, qdac_fast_channel: StandardParameter,
                        npts: int, zi, add_offset: bool=True):
    """
    Args:
        keysight_low_V (float): keysight ramp start value
        keysight_high_V (float): keysight ramp stop value
        scope_avger (Scope_avg): The Scope_avg instance
        qdac_fast_channel: The number of the qdac channel to use for label
            offset
        zi: Instance of ZIUHFLI to use
        add_offset: Add the qdac_fast_channel value to the fast axis
    """
    zi.Scope.prepare_scope()
    #npts = zi.scope_length()

    offset = 0
    if add_offset:
        offset = qdac_fast_channel.get()

    scope_avger.make_setpoints(keysight_low_V+offset, keysight_high_V+offset, npts)
    scope_avger.setpoint_names = ('keysight_voltage',)
    scope_avger.setpoint_labels = ('Fast {}'.format(qdac_fast_channel.label),)
    scope_avger.setpoint_units = ('V',)

    # zi.scope_avg_ch1.make_setpoints(keysight_low_V, keysight_high_V, npts)
    # zi.scope_avg_ch1.setpoint_names = ('keysight_voltage',)
    # zi.scope_avg_ch1.setpoint_labels = ('Keysight Voltage',)
    # zi.scope_avg_ch1.setpoint_units = ('V', )


def arrayify_args(f):

    @wraps(f)
    def wrapper(*args, **kwargs):
        main_channel_args = ('keysight_channels', 'fast_v_start', 'fast_v_stop',
                             'qdac_channels', 'q_start', 'q_stop',
                             'qdac_fast_channels')
        compensation_args = ('fast_compensation_channels',
                             'fast_compensation_scale',
                             'fast_compensation_phase_offset')
        scope_args = ('scope_signal',)
        args_to_arrayify = main_channel_args + scope_args
        if kwargs.get('fast_compensation_channels'):
            args_to_arrayify += 'fast_compensation_channels'
        for argname in args_to_arrayify:
            if not isinstance(kwargs[argname], Sequence) or isinstance(kwargs[argname], str):
                kwargs[argname] = [kwargs[argname]]

        # verify that we have the correct number of args for main channels
        # i.e all matching
        n_key_channels = len(kwargs['keysight_channels'])
        for argname in main_channel_args:
            if len(kwargs[argname]) != n_key_channels:
                raise RuntimeError("Inconsistent number of channel args provided. "
                                   "{} channels used but len of {} is {}".format(n_key_channels,
                                                                                 argname,
                                                                                 len(kwargs[argname])))
        if len(kwargs['scope_signal']) < n_key_channels:
            raise RuntimeError("Number of scope channels is smaller than number of keysight_channels")

        return f(*args, **kwargs)
    return wrapper

number = Union[float, int]
num_or_list_of_num = Union[Sequence[number], number]


@arrayify_args
def fast_charge_diagram(keysight_channels: Union[Sequence[KeysightChannel], KeysightChannel]=None,
                        fast_v_start: num_or_list_of_num=None,
                        fast_v_stop: num_or_list_of_num=None,
                        n_averages: int=None,
                        qdac_channels: Union[Sequence[StandardParameter], StandardParameter]=None,
                        q_start: num_or_list_of_num=None, q_stop: num_or_list_of_num=None,
                        npoints: int=None, delay: number=None,
                        qdac_fast_channels: Union[Sequence[StandardParameter], StandardParameter]=None,
                        comp_scale,
                        scope_signal: Union[Sequence[str], str]=None,
                        zi: ZIUHFLI_T10=None, zi_trig_signal: str='Trig Input 1',
                        trigger_holdoff: float=60e-6,
                        zi_samplingrate: str='14.0 MHz',
                        zi_scope_length: int=4096,
                        zi_trig_hyst: float=0.,
                        zi_trig_level: float=.5,
                        zi_trig_delay: float=0.,
                        print_settings: bool=False,
                        add_offset: bool=True,
                        zi=None, keysight=None,
                        tasks_to_perform: Optional[Sequence[qc.Task]]=None,
                        fast_compensation_channels: Optional[Union[Sequence[KeysightChannel], KeysightChannel]]=None,
                        fast_compensation_scale: float=-1.,
                        fast_compensation_phase_offset: float=0.):
    """
    Args:
        keysight_channels: Which keysight channel to output on
        fast_v_start: Start voltage for fast ramp on Keysight
        fast_v_stop: End voltage for fast ramp on Keysight
        n_averages: Number of avarages to perform
        qdac_channels: QDac voltage channel to scan along the slow axis
        q_start: Start voltage of QDac
        q_stop: Stop voltage of QDac
        npoints: Number of points in QDac scan
        delay: time to wait between each slow axis step
        qdac_fast_channels:
        scope_signal:
        zi:
        zi_trig_signal: Which input to trigger on
        trigger_holdoff:
        zi_samplingrate: Sampling rate of the ZI
        zi_scope_length: Number of points to measure in ZI trace
        zi_trig_hyst: Trigger hysteresis uses to prevent triggers on noise
        zi_trig_level: Trigger level of zi
        zi_trig_delay: Should be the rise time of your signal/trigger signal
               For Keysight sawtooth it is 6e-7s.
        print_settings: print an overview of the settings before performing measurement
        add_offset: Should value of qdac fast channel be added as an offset for display values of keysight
            voltage
        tasks_to_perform: tasks that are performed at each slow measurement. Such as compensating a gate
        fast_compensation_channels: Channels to use for compensation of fast voltage sweep.
        fast_compensation_scale: The fast compensation is the output multiplied by this constant.
            Minus means that output is inverted.
        fast_compensation_phase_offset: Phase offset between fast voltage and fast compensation in degrees.
    """
    if zi is None:
        zi = qc.Instrument.find_instrument('ziuhfli')
    if keysight is None:
        keysight = qc.Instrument.find_instrument('keysight_gen_left')

    if not scope_signal:
        raise ValueError('Select valid scope signal(s).')
    # In order to take thee hold off time of the uhfli into account
    # we need to recalculate the scope duration, sawtooth amplitude
    # and keysight frequency.

    zi.scope_samplingrate.set(zi_samplingrate)
    
    # KDP: allow for fewer points than the UHFLI 4096  min.
    if zi_scope_length < 4096:
        zi.scope_length.set(4096)
    else:
        zi.scope_length.set(zi_scope_length)
    
    zi.daq.sync()

    scope_duration = zi.scope_duration()
    scope_duration_compensated = trigger_holdoff + scope_duration + zi_trig_delay
    key_frequency = 1/scope_duration_compensated

    asym = trigger_holdoff/scope_duration_compensated  # dead time / meas. time

    keysight_amplitudes = []
    key_offsets = []
    for i in range(len(fast_v_start)):
        keysight_amplitudes.append(abs(fast_v_stop[i]-fast_v_start[i]))
        key_offsets.append(fast_v_start[i] + keysight_amplitudes[i]/2)

    zi.scope_channels(3)
    zi.scope_trig_holdoffseconds.set(trigger_holdoff)

    zi.scope_trig_enable.set('ON')
    zi.scope_trig_signal.set(zi_trig_signal)
    zi.scope_trig_slope.set('Rise')

    zi.scope_trig_hystmode('absolute')
    zi.scope_trig_hystabsolute.set(zi_trig_hyst)

    zi.scope_trig_gating_enable.set('OFF')
    zi.scope_trig_holdoffmode.set('s')

    zi.scope_trig_reference.set(0)
    zi.scope_segments('ON')
    zi.scope_segments_count(n_averages)

    zi.scope_trig_level.set(zi_trig_level)
    zi.scope_trig_delay.set(zi_trig_delay)
    zi.daq.sync()

    def set_keysight(keysight_channel: KeysightChannel, measurement: int=0,
                     multiplier: float=1.,
                     phase_offset: float=0.):
        if multiplier < 0:
            multiplier = abs(multiplier)
            keysight_channel.output_polarity('INV')
        else:
            keysight_channel.output_polarity('NORM')
        keysight_channel.function_type('RAMP')
        keysight_channel.ramp_symmetry(100*(1-asym))
        keysight_channel.phase(180*(1+asym)+phase_offset)
        keysight_channel.amplitude_unit('VPP')
        keysight_channel.amplitude(keysight_amplitudes[measurement]*multiplier)
        keysight_channel.offset(key_offsets[measurement])
        keysight_channel.frequency(key_frequency)

    for i, keysight_channel in enumerate(keysight_channels):
        set_keysight(keysight_channel, i)

    mychannel = keysight_channels[0]
    channel_num = None
    if mychannel.short_name == 'ch1':
        channel_num = 1
    elif mychannel.short_name == 'ch2':
        channel_num = 2
    mychannel._parent.sync_source(channel_num)
    mychannel._parent.sync_channel_phases()

    if fast_compensation_channels:
        for fast_compensation_channel in fast_compensation_channels:
            set_keysight(fast_compensation_channel,
                         multiplier=fast_compensation_scale,
                         phase_offset=fast_compensation_phase_offset)
            fast_compensation_channel._parent.sync_channel_phases()

    for keysight_channel in keysight_channels:
        keysight_channel.output('ON')
    if fast_compensation_channels is not None:
        for fast_compensation_channel in fast_compensation_channels:
            fast_compensation_channel.output('ON')

    scope_avger = []
    zi_averager = {0: zi.scope_avg_ch1,
                   1: zi.scope_avg_ch2}

    for ii, sig in enumerate(scope_signal):
        if ii == 0:
            zi.scope_channel1_input(sig)
        elif ii == 1:
            zi.scope_channel2_input(sig)
        else:
            raise ValueError('Select only one or two scope signals.')
        zi_averager[ii].label = sig

        try:
            scope_avger.append(zi_averager[ii])
            if len(keysight_channels) > 1:
                prepare_measurement(fast_v_start[ii], fast_v_stop[ii], zi_averager[ii],
                                    qdac_fast_channels[ii], zi_scope_length, zi, add_offset=add_offset)
            else:
                prepare_measurement(fast_v_start[0], fast_v_stop[0], zi_averager[ii],
                                    qdac_fast_channels[0], zi_scope_length, zi, add_offset=add_offset)
        except KeyError:
            raise ValueError('Invalid scope_channel: {}'.format(sig))

    mychannel._parent.sync_output('ON')
    # set up UHFLI
    # zi.scope_mode.set('Time Domain')  # currently done in ZI driver

    # prepare_measurement(fast_v_start, fast_v_stop, zi_averager[ch])

    if print_settings:
        print('keysight frequency: {}'.format(key_frequency))
        print('keysight amplitude: {}'.format(keysight_amplitudes))
        print('keysight offset: {}'.format(key_offsets))
        print('\n')
        print('zi_samplingrate: {}'.format(zi_samplingrate))
        print('zi_trig_level: {}'.format(zi_trig_level))
        print('zi_trig_delay: {}'.format(zi_trig_delay))
        print('zi_trig_hyst: {}'.format(zi_trig_hyst))


    if len(qdac_channels) > 1:
        combined_sweep = qc.combine(*qdac_channels, name='combined_qdac_channels')
        vals1 = np.linspace(q_start[0], q_stop[0], npoints).reshape(npoints, 1)
        vals2 = np.linspace(q_start[1], q_stop[1], npoints).reshape(npoints, 1)
        setpoints = np.hstack((vals1, vals2))
    else:
        combined_sweep = None
        setpoints = None
    try:
        if len(qdac_channels) > 1:
            if tasks_to_perform is None:
                plot, data = do1dcombined(combined_sweep, setpoints, delay, *scope_avger)
            else:
                plot, data = do1dcombined(combined_sweep, setpoints, delay, *scope_avger,
                                          *tasks_to_perform)
        else:
            if tasks_to_perform is None:
                plot, data = do1d(qdac_channels[0], q_start[0], q_stop[0], npoints, delay, *scope_avger)
            else:
                plot, data = do1d(qdac_channels[0], q_start[0], q_stop[0], npoints, delay, *scope_avger,
                                  *tasks_to_perform)

        for channel in keysight_channels:
            channel.output('OFF')
        if fast_compensation_channels:
            for channel in fast_compensation_channels:
                channel.output('OFF')

    except KeyboardInterrupt:
        for channel in keysight_channels:
            channel.output('OFF')
        if fast_compensation_channels:
            for channel in fast_compensation_channels:
                channel.output('OFF')

        print('Measurement interrupted.')
        raise KeyboardInterrupt
    return plot, data
