import numpy as np
from qcodes.instrument.parameter import ArrayParameter


class Scope_avg(ArrayParameter):

    def __init__(self, name, channel=1, **kwargs):

        super().__init__(name, shape=(1,), **kwargs)
        self.has_setpoints = False
        self.zi = self._instrument

        if not channel in [1, 2]:
            raise ValueError('Channel must be 1 or 2')

        self.channel = channel

    def make_setpoints(self, sp_start, sp_stop, sp_npts):
        """
        Makes setpoints and prepares the averager (updates its unit)
        """
        self.shape = (sp_npts,)
        self.unit = self._instrument.Scope.units[self.channel-1]
        self.setpoints = (tuple(np.linspace(sp_start, sp_stop, sp_npts)),)
        self.has_setpoints = True

    def get(self):

        if not self.has_setpoints:
            raise ValueError('Setpoints not made. Run make_setpoints')

        data = self._instrument.Scope.get()[self.channel-1]
        return np.mean(data, 0)


try:
    zi.add_parameter('scope_avg_ch1',
                     channel=1,
                     label='',
                     parameter_class=Scope_avg)
except KeyError:
    pass

try:
    zi.add_parameter('scope_avg_ch2',
                     channel=2,
                     label='',
                     parameter_class=Scope_avg)
except KeyError:
    pass


def prepare_measurement(keysight_low_V, keysight_high_V, scope_avger, qdac_fast_channel):
    """
    Args:
        keysight_low_V (float): keysight ramp start value
        keysight_high_V (float): keysight ramp stop value
        scope_avger (Scope_avg): The Scope_avg instance
        qdac_fast_channel (int): The number of the QDac channel added to
            the Keysight ramp
    """
    zi.Scope.prepare_scope()
    npts = zi.scope_length()
    
    offset = qdac.parameters['ch{:02}_v'.format(qdac_fast_channel)].get()

    scope_avger.make_setpoints(keysight_low_V+offset, keysight_high_V+offset, npts)
    scope_avger.setpoint_names = ('keysight_voltage',)
    scope_avger.setpoint_labels = ('Fast q{}'.format(qdac_fast_channel),)
    scope_avger.setpoint_units = ('V',)

    # zi.scope_avg_ch1.make_setpoints(keysight_low_V, keysight_high_V, npts)
    # zi.scope_avg_ch1.setpoint_names = ('keysight_voltage',)
    # zi.scope_avg_ch1.setpoint_labels = ('Keysight Voltage',)
    # zi.scope_avg_ch1.setpoint_units = ('V', )



def fast_charge_diagram(keysight_channel, fast_v_start, fast_v_stop, n_averages,
                        qdac_channel, q_start, q_stop, npoints, delay,
                        scope_signal=['Demod 1 R', 'Demod 5 R'], zi_trig_signal='Trig Input 1',
                        qdac_fast_channel=48,  
                        trigger_holdoff=60e-6, zi_samplingrate='14.0 MHz', zi_scope_length=4096,
                        zi_trig_hyst=0, zi_trig_level=.5, zi_trig_delay = 0, print_settings=False,
                        tasks_to_perform=None):
    """
    Args:
        keysight_channel:
        fast_v_start
        fast_v_stop
        keys_freq
        n_averages
        qdac_channel
        q_start
        q_stop
        npoints:
        delay:
        zi_input_chan:
        zi_trig_signal:
        trigger_holdoff;
        zi_samplingrate:
        zi_trig_hyst:
        zi_trig_level:
        zi_trig_delay: Should be the rise time of your signal/trigger signal 
                       For Keysight sawtooth it is 6e-7s.
    """

    if keysight_channel not in ['ch01', 'ch02']:
        raise ValueError('Invalid keysight channel. Must be either "ch01" or "ch02".')

    if not isinstance(scope_signal, list):
        scope_signal = [scope_signal]
    
    # In order to take thee hold off time of the uhfli into account
    # we need to recalculate the scope duration, sawtooth amplitude
    # and keysight frequency.

    zi.scope_samplingrate.set(zi_samplingrate)
    zi.scope_length.set(zi_scope_length)
    zi.daq.sync()

    scope_duration = zi.scope_duration()
    scope_duration_compensated = trigger_holdoff + scope_duration + zi_trig_delay
    key_frequency = 1/scope_duration_compensated

    asym = trigger_holdoff/scope_duration_compensated  # dead time / meas. time

    # # obsolete next line
    # additional_sawtooth_amplitude = keysight_amplitude * ((trigger_holdoff)/scope_duration)


    keysight_amplitude = abs(fast_v_stop-fast_v_start)
    key_offset = fast_v_start + keysight_amplitude/2
    # fast_v_start -= additional_sawtooth_amplitude

    print(keysight_amplitude, key_offset)

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
    if keysight_channel == 'ch01':
        keysight.ch1_function_type('RAMP')
        keysight.ch1_ramp_symmetry(100*(1-asym))
        keysight.ch1_phase(180*(1+asym))
        keysight.ch1_amplitude_unit('VPP')
        keysight.ch1_amplitude(keysight_amplitude)
        keysight.ch1_offset(key_offset)
        keysight.ch1_frequency(key_frequency)
        keysight.sync_source(1)
        keysight.ch1_output('ON')
    elif keysight_channel == 'ch02':
        keysight.ch2_function_type('RAMP')
        keysight.ch2_ramp_symmetry(100*(1-asym))
        keysight.ch2_phase(180*(1+asym))
        keysight.ch2_amplitude_unit('VPP')
        keysight.ch2_amplitude(keysight_amplitude)
        keysight.ch2_offset(key_offset)
        keysight.ch2_frequency(key_frequency)
        keysight.sync_source(2)
        keysight.ch2_output('ON')
    else:
        raise ValueError('Select a valid Keysight channel.')

    scope_avger = []
    zi_averager = {0: zi.scope_avg_ch1,
                   1: zi.scope_avg_ch2}

    for ii, sig in enumerate(scope_signal):
        zi.scope_channel1_input(sig)
        zi_averager[ii].label = sig

        try:
            scope_avger.append(zi_averager[ii])
            prepare_measurement(fast_v_start, fast_v_stop, zi_averager[ii],
                                qdac_fast_channel)
        except KeyError:
            raise ValueError('Invalid scope_channel: {}'.format(ch))

    keysight.sync_output('ON')
    # set up UHFLI
    # zi.scope_mode.set('Time Domain')  # currently done in ZI driver

    # prepare_measurement(fast_v_start, fast_v_stop, zi_averager[ch])

    if print_settings:
        print('keysight frequency: {}'.format(key_frequency))
        print('keysight amplitude: {}'.format(keysight_amplitude))
        print('keysight offset: {}'.format(key_offset))
        print('\n')
        print('zi_samplingrate: {}'.format(zi_samplingrate))
        print('zi_trig_level: {}'.format(zi_trig_level))
        print('zi_trig_delay: {}'.format(zi_trig_delay))
        print('zi_trig_hyst: {}'.format(zi_trig_hyst))

    try:
        if tasks_to_perform is None:
            #plot, data = do1d_M(qdac_channel, q_start, q_stop, npoints, delay, scope_avger)
            plot, data = do1d(qdac_channel, q_start, q_stop, npoints, delay, *scope_avger)
        else:
            #plot, data = do1d_M(qdac_channel, q_start, q_stop, npoints, delay, scope_avger, *tasks_to_perform)
            plot, data = do1d(qdac_channel, q_start, q_stop, npoints, delay, *scope_avger, *tasks_to_perform)

        if keysight_channel == 'ch01':
            keysight.ch1_output('OFF')
        elif keysight_channel == 'ch02':
            keysight.ch2_output('OFF')

    except KeyboardInterrupt:
        if keysight_channel == 'ch01':
            keysight.ch1_output('OFF')
        elif keysight_channel == 'ch02':
            keysight.ch2_output('OFF')

        print('Measurement interrupted.')

    return plot, data
