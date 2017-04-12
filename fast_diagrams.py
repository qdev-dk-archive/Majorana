import numpy as np
from qcodes.instrument.parameter import ArrayParameter

try:
     zi
except NameError:
    print("zi not defined; the code will fail")
    from unittest.mock import Mock
    zi= Mock()


class Scope_avg(ArrayParameter):
    """
    Parameter to be added to ZIUHFLI. Read out the scope (one class instance per
    channel) and averages segments together. 
    """
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
        """
        Scope_avg getter. Averages over segments - squeezes all segments into
        one.
        """
        if not self.has_setpoints:
            raise ValueError('Setpoints not made. Run make_setpoints')

        data = self._instrument.Scope.get()[self.channel-1]
        return np.mean(data, 0)


def prepare_measurement(keysight_low_V, keysight_high_V, scope_avger,
                        qdac_fast_channel):
    """
    Prepares scope_avg, UHFLI's scope parameter for fast diagrams. It 
    arms ZI's scope module, sets up qcodes setpoints and plot labeling.

    Args:
        keysight_low_V (float): Keysight ramp start value
        keysight_high_V (float): Keysight ramp stop value
        scope_avger (Scope_avg): A Scope_avg instance
        qdac_fast_channel (int): Number of the QDac channel added to
            the Keysight ramp (DC offset)
    """
    zi.Scope.prepare_scope()
    npts = zi.scope_length()
    
    offset = 0  # qdac.parameters['ch{:02}_v'.format(qdac_fast_channel)].get()

    scope_avger.make_setpoints(keysight_low_V+offset, keysight_high_V+offset,
                               npts)
    scope_avger.setpoint_names = ('keysight_voltage',)
    scope_avger.setpoint_labels = ('Fast {}'.format(QDAC[qdac_fast_channel].label),)
    scope_avger.setpoint_units = ('V',)


def fast_charge_diagram(keysight_channel, fast_v_start, fast_v_stop,
                        n_averages, qdac_channel, q_start, q_stop,
                        npoints, delay, qdac_fast_channel, scope_signal,
                        zi_trig_signal='Trig Input 1', trigger_holdoff=60e-6,
                        zi_samplingrate='14.0 MHz', zi_scope_length=4096,
                        zi_trig_hyst=0, zi_trig_level=.5, zi_trig_delay=0,
                        print_settings=False, tasks_to_perform=None):
    """
    Function to perform fast charge diagrams using a Keysight sawtooth as fast
    voltage ramp and a ZI UHFLI for readout and averaging. It generates a
    'fast' 2d diagram, where the slow axis is stepped using a QDac
    and the second via a Keysight sawtooth.
    UHFLI's scope module is used for readout. One keysight sawtooth on the fast
    axis corresponds to one scope shot/one segment. For each voltage value on
    the slow axis we perform N=<n_averages> periods on the keysight, resulting
    in N=<n_averages> segments. These are averaged down to one segment/
    scopeshot, corresponding to one line of the 2d plot.
    Pre-averaging is achieved by adjusting the time constant on the UHFLI.

    ! Warning ! : Do not use ZI's GUI while running this function. It will
    result in data loss. Run the Data Server only.


    Args:
        keysight_channel (str): Keysight output channel outputing a sawtooth
            Choose 'ch01' or 'ch02'.
        fast_v_start (V): Min value of keysight sawtooth
        fast_v_stop (V): Max value of keysight sawtooth
        n_averages: Number of segments averaged together; number of keysight
            periods performed for one voltage on slow axis.
        qdac_channel: QDac parameter ex QDAC[x] or qdac.ch0X_v;
            channel to be stepped in voltage on slow axis
        q_start (V): Start voltage on slow axis
        q_stop (V): End voltage on slow axis
        npoints (int): Number of points on slow axis
        delay (s): Delay between steps on slow axis
        qdac_fast_channel (int): QDac channel providing DC offset on fast axis;
            connected to same BNC as the keysight
        scope_signal (str): One or two signals to record. Choose from ZI's
            input/trigger input list below.
        zi_trig_signal (str): Signal on which ZI's scope module will trigger.
            Choose from ZI's input/trigger input list below.
        trigger_holdoff (s): Delay between individual scope shots/segments.
            Needs to be at least the deadtime of Zi's scope module (50e-6).
        zi_samplingrate (str): Sampling rate of ZI's scope module. Choose one
            in the list below.
        zi_scope_length (int): Number of points in one segments. 4096 is the 
            minimum dictated by the UHFLI.
        zi_trig_hyst (V): Trigger hysteresis (absolute)
        zi_trig_level (V): Trigger level
        zi_trig_delay (s): Trigger delay
        print_settings (bool): Set to True if details about settings should
            be printed to console. Note that this print will not be saved
            anywhere.
        tasks_to_perform (qc.Tasks): Tuple of tasks to perform in between point
            of slow axis. Measurements, delays et. Needs to be a tuple, ex:
            (compensate_gate,), where compensate_gate is a function.

        ZI input/trigger inputs:
                      'Signal Input 1', 'Signal Input 2', 'Trig Input 1',
                      'Trig Input 2', 'Aux Output 1', 'Aux Output 2',
                      'Aux Output 3', 'Aux Output 4', 'Aux In 1 Ch 1',
                      'Aux In 1 Ch 2', 'Osc phi Demod 4', 'osc phi Demod 8',
                      'AU Cartesian 1', 'AU Cartesian 2', 'AU Polar 1',
                      'AU Polar 2', 'Demod 1 X', 'Demod 1 Y', 'Demod 1 R',
                      'Demod 1 Phase', 'Demod 2 X', 'Demod 2 Y', 'Demod 2 R',
                      'Demod 2 Phase', 'Demod 3 X', 'Demod 3 Y', 'Demod 3 R',
                      'Demod 3 Phase', 'Demod 4 X', 'Demod 4 Y', 'Demod 4 R', 
                      'Demod 4 Phase', 'Demod 5 X', 'Demod 5 Y', 'Demod 5 R',
                      'Demod 5 Phase', 'Demod 6 X', 'Demod 6 Y', 'Demod 6 R',
                      'Demod 6 Phase', 'Demod 7 X', 'Demod 7 Y', 'Demod 7 R',
                      'Demod 7 Phase', 'Demod 8 X', 'Demod 8 Y', 'Demod 8 R',
                      'Demod 8 Phase'

    ZI sampling rates:
                    '1.80 GHz', '900 MHz', '450 MHz', '225 MHz', '113 MHz', 
                    '56.2 MHz', 28.1 MHz', '14.0 MHz': 7, '7.03 MHz', '3.50 MHz'
                    '1.75 MHz', '880 kHz', '440 kHz', '220 kHz', '110 kHz',
                    '54.9 kHz', '27.5 kHz'
    """

    if keysight_channel not in ['ch01', 'ch02']:
        raise ValueError('Invalid keysight channel.' +
                         'Must be either "ch01" or "ch02".')

    if not isinstance(scope_signal, list):
        scope_signal = [scope_signal]

    if not scope_signal:
        raise ValueError('Select valid scope signal(s).')
    # In order to take thee hold off time of the uhfli into account
    # we need to recalculate the scope duration, sawtooth amplitude
    # and keysight frequency.

    zi.scope_samplingrate.set(zi_samplingrate)
    zi.scope_length.set(zi_scope_length)
    zi.daq.sync()

    scope_duration = zi.scope_duration()
    scope_duration_compensated = trigger_holdoff + scope_duration
    scope_duration_compensated += zi_trig_delay
    key_frequency = 1/scope_duration_compensated

    asym = trigger_holdoff/scope_duration_compensated

    keysight_amplitude = abs(fast_v_stop-fast_v_start)
    key_offset = fast_v_start + keysight_amplitude/2

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
        if ii == 0:
            zi.scope_channel1_input(sig)
        elif ii == 1:
            zi.scope_channel2_input(sig)
        else:
            raise ValueError('Select only one or two scope signals.')
        zi_averager[ii].label = sig

        try:
            scope_avger.append(zi_averager[ii])
            prepare_measurement(fast_v_start, fast_v_stop, zi_averager[ii],
                                qdac_fast_channel)
        except KeyError:
            raise ValueError('Invalid scope_channel: {}'.format(ch))

    keysight.sync_output('ON')

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


if __name__ == '__main__':

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