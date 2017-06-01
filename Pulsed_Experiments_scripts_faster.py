import numpy as np
from datetime import datetime
from inspect import signature

import broadbean as bb
import qcodes as qc
from qcodes.instrument.parameter import ArrayParameter, StandardParameter
from qcodes.utils.helpers import full_class
from qcodes.utils.wrappers import do1d

ramp = bb.PulseAtoms.ramp
sine = bb.PulseAtoms.sine


class ArgumentError(Exception):
    pass


# For the main function, we
# make a decorator to detect if all
# keywordarguments have been supplied
def check_kwargs(func):
    """
    Decorator function that ensures that all kwargs of a function taking
    only kwargs have been specified.
    """

    params = signature(func).parameters
    no_of_args = len(params)

    def wrapper(**kwargs):

        given = set(kwargs.keys())
        needed = set(params.keys())

        if len(kwargs) < no_of_args:
            missing = needed.difference(given)
            raise ArgumentError('Unspecified arguments: {}'.format(missing))

        return func(**kwargs)

    wrapper.__doc__ = func.__doc__

    return wrapper


class AverageRampResponse(ArrayParameter):
    """
    The parameter to hold the averaged fast axis of the pulsed experiment,
    i.e. the data axis (out-of-plane, z axis) of the experiment
    """

    def __init__(self, name, awg, zi, no_of_avgs, voltages,
                 awg_channel=1,
                 label=None, unit=None):
        """
        Instantiate the parameter. The setpoints must be known at
        the time of instantiation and can not be changed.

        Args:
            name (str): Name of the parameter
            awg (Tektronix_AWG5014): An instance of the QCoDeS instrument
            zi (ZIUHFLI): An instance of the QCoDeS instrument
            no_of_avgs (int): The number of times to average.
            voltages (list): A list of setpoint voltages
            awg_channel (int): The relevant AWG channel. Each .awg file
                upload switches the channels off, so we must know this
                to switch them back on.
        """

        super().__init__(name, shape=(len(voltages),))

        self.zi = zi
        self.awg = awg
        self.awgchannel = awg_channel

        self.no_of_avgs = no_of_avgs

        self.setpoints = (tuple(voltages),)
        self.setpoint_labels = ('Ramp voltage',)
        self.setpoint_units = ('V',)
        if label is not None:
            self.label = label
        if unit is not None:
            self.unit = unit

        # The QDev-QCoDeS doNd refuses to plot parameters that have no assigned
        # instrument, so we fake one
        # self._instrument = FakeInstrument('Ramp machine')

    def get(self):
        """
        The get call. Performs the measurement no_of_avgs times
        """
        # we expect two scope subscriptions
        # and the relevant one must be on Channel 2
        assert self.zi.scope_channels() == 3

        self.zi.Scope.prepare_scope()

        data = np.zeros(self.zi.scope_segments_count())

        # switch AWG channel on (an .awg file upload will have switched it off)
        self.awg.parameters['ch{}_state'.format(self.awgchannel)].set(1)

        for n in range(self.no_of_avgs):
            self.awg.run()
            temp_data = self.zi.Scope.get()
            self.awg.stop()
            demod_data_avg = [np.mean(arr) for arr in temp_data[1]]
            data += np.array(demod_data_avg)

        data /= self.no_of_avgs

        return data


# TODO: rewrite this set method using the new FULL sequence
class PulseTime(StandardParameter):
    """
    The parameter setting a new pulsetime.

    A candidate for a parameter with the most side effects in its set.
    Builds a new sequence and uploads it to the AWG.
    """

    def __init__(self, name, basesequence, pos, chan, segname, awg,
                 awgchannels):
        """
        Args:
            name (str): The name of the parameter.
            basesequence (Sequence): broadbean Sequence object
            pos (int): sequence position of duration to change
            chan (int): channel number of duration to change
            segname (str): segment name of duration to change
            awg (Tektronix_AWG5014): An instance of the QCoDeS instrument
            awgchannels (list): The channels on the AWG to upload the sequence
                to
        """
        super().__init__(name, set_cmd=self.set, get_cmd=self.get)

        self.unit = 's'
        self.label = 'Pulse width'
        self.seq = basesequence
        self.pos = pos
        self.chan = chan
        self.segname = segname
        self.awg = awg
        self.awgchannels = awgchannels

        # self._instrument = FakeInstrument('Tektronix AWG')

    def set(self, width):
        # change the width of the high time
        self.seq.element(self.pos).changeDuration(self.chan,
                                                  self.segname, width)

        package = self.seq.outputForAWGFile()
        self.awg.make_send_and_load_awg_file(*package[:],
                                             channels=self.awgchannels)

    def get(self):
        return 1

    def snapshot_base(self, update=False):
        """
        State of the pulse time parameter as a JSON-compatible dict.
        Records the entire pulse sequence in the metadata.

        Args:
            update (bool): Not used.

        Returns:
            dict: base snapshot
        """

        state = super().snapshot_base(update=update)

        # We should metadata the sequence and which part of it we are actually
        # modifying

        state['pulse_sequence'] = self.seq.description

        state['to_be_modified'] = {'sequence position': self.pos,
                                   'channel': self.chan,
                                   'segment name': self.segname}

        return state


def _DPE_prepareKeysight(no_of_pulses=None, cycletime=None, ramp_low=None,
                         ramp_high=None, keysight=None):
    """
    Prepare the Keysight
    """
    if None in [no_of_pulses, cycletime, ramp_low, ramp_high, keysight]:
        raise ValueError('Keysight settings underspecified!')

    keysight.ch1_function_type('RAMP')
    keysight.ch1_ramp_symmetry(100)

    period = no_of_pulses*cycletime
    keysight.ch1_frequency(1/period)  # plus some trigger dead time?
    keysight.ch1_amplitude(ramp_high-ramp_low)
    keysight.ch1_offset(ramp_low)

    keysight.ch1_trigger_source('EXT')
    keysight.ch1_trigger_delay(0)
    keysight.ch1_trigger_slope('POS')

    keysight.ch1_burst_mode('N Cycle')
    keysight.ch1_burst_ncycles(1)
    keysight.ch1_burst_phase(180)
    keysight.ch1_burst_state('ON')


def _DPE_prepareTektronixAWG(awg, awg_channel, SR, pulsehigh):
    """
    Prepare the AWG.

    Args:
        awg (Tektronix_AWG5014): QCoDeS instrument instance
        awg_channel (int): The awg channel to use (1-4)
        SR (int): The sample rate (Sa/s)
        pulsehigh (float): The highest level of the desired pulse
    """

    # NB: If you change these settings, make sure to change them in
    # _DPE_makeSequence as well!

    awg.clock_freq(SR)
    awg.parameters['ch{}_amp'.format(awg_channel)].set(2*pulsehigh)
    awg.parameters['ch{}_offset'.format(awg_channel)].set(0)
    awg.parameters['ch{}_state'.format(awg_channel)].set(1)
    awg.parameters['ch{}_add_input'.format(awg_channel)].set('"ESIG"')


def _DPE_prepareZIUHFLI(zi, demod_freq, pts_per_shot,
                        SRstring, no_of_pulses, meastime):
    """
    Prepare the ZI UHF-LI

    Args:
        zi (ZIUHFLI): QCoDeS instrument instance
        demod_freq (float): The demodulation frequency (Hz)
        pts_per_shot (int): No. of points per measurement. Most likely 4096.
        SRstring (str): The string version of the sample rate used by the
            lock-in, e.g. '113 MHz'. Should be the output of
            _DPE_correct_meastime.
        no_of_pulses (int): No. of pulses riding on the ramp, i.e. number
            of scope segments.
        meastime (float): The data acquisition time per point (s)
    """

    # Demodulator
    zi.oscillator1_freq(demod_freq)
    zi.demod1_order(1)
    zi.demod1_timeconstant(0.1*meastime)
    zi.signal_output1_on('ON')
    # TODO: use this in post-processing to remove first part of demod. data

    # Scope
    zi.scope_channel1_input('Demod 1 R')
    zi.scope_channel2_input('Signal Input 2')
    zi.scope_mode('Time Domain')
    zi.scope_samplingrate(SRstring)
    zi.scope_length(pts_per_shot)
    zi.scope_channels(3)
    #
    zi.scope_trig_enable('ON')
    # trigger delay reference point: at trigger event time
    zi.scope_trig_reference(0)
    zi.scope_trig_delay(1e-6)
    zi.scope_trig_holdoffmode('s')
    zi.scope_trig_holdoffseconds(60e-6)
    zi.scope_trig_gating_enable('OFF')
    zi.scope_trig_signal('Trig Input 1')
    #
    zi.scope_segments('ON')
    zi.scope_segments_count(no_of_pulses)


def _DPE_correct_meastime(meastime, npts):
    """
    Given a number of points to measure, and a desired measurement time,
    find the measurement time closest to the given one that the ZI UHF-LI can
    actually realise.

    Args:
        meastime (float): The desired measurement time
        npts (int): The desired number of points

    Returns:
        tuple (float, str): A tuple with the new measurement time and
            a string with the sample rate achieving this
    """

    # TODO: is a logarithmic error measure better than a linear one?

    # the sample rates of the lock-in
    SRs = [1.8e9/2**n for n in range(17)]

    realtimes = np.array([npts/SR for SR in SRs])
    errors = np.abs(meastime-realtimes)

    newtime = realtimes[errors.argmin()]

    SRstrings = ['1.80 GHz', '900 MHz', '450 MHz', '225 MHz', '113 MHz',
                 '56.2 MHz',
                 '28.1 MHz', '14.0 MHz', '7.03 MHz', '3.50 MHz', '1.75 MHz',
                 '880 kHz',
                 '440 kHz', '220 kHz', '110 kHz', '54.9 kHz', '27.5 kHz']

    SRstring = SRstrings[errors.argmin()]

    # Do some rounding for safety
    newtime = float('{:.4e}'.format(newtime))

    return newtime, SRstring


def _DPE_makeFullSequence(hightimes, trig_delay, meastime, prewaittime,
                          cycletime, no_of_avgs,
                          no_of_pulses, pulsehigh, SR, segname):
    """
    Generate the full sequence (to be uploaded exactly once).

    The sequence is a varied sequence with a baseelement consisting
    of four parts:
    1: A wait with zeros allowing the ZI to get ready. This part is
    short, but repeated waitbits times
    2: A short zero part with the marker2 trigger for the ramp
    3: The high pulse and a marker1 trigger for the ZI
    4: A short zero part with an event jump leading back to part one.
    This leading back happens no_of_avgs times.

    Args:
        hightime (float): The width of the pulse (s)p
        trig_delay (float): The delay to start measuring after the end of the
            pulse (s).
        meastime (float): The time of each measurement (s).
        prewaittime (float): The time to wait before each ramp (s).
        cycletime (float): The time of each ramp (s).
        no_of_pulses (int): The number of pulse per ramp.
        pulsehigh (float): The amplitude of the pulse (V)
        SR (int): The AWG sample rate (Sa/s)
        segname (str): The name of the high pulse segment as used internally
            by broadbean.
    """

    waitbits = 100  # no. of repetitions of the first part
    waitbittime = prewaittime/waitbits
    trig_duration = 5e-6

    if waitbittime < 10/SR:
        raise ValueError('prewaittime too short.')

    # The pulsed part
    bp_pulse = bb.BluePrint()
    bp_pulse.setSR(SR)
    bp_pulse.insertSegment(0, ramp, (pulsehigh, pulsehigh),
                           durs=hightimes[0], name=segname)
    bp_pulse.insertSegment(1, ramp, (0, 0), durs=meastime, name='measure')
    # dead time for the scope to re-arm its trigger
    bp_pulse.insertSegment(2, 'waituntil', cycletime)
    bp_pulse.setSegmentMarker('measure', (trig_delay, 10e-6), 1)

    # initial wait time to allow ZI trigger to get ready. This BP is repeated
    bp_wait = bb.BluePrint()
    bp_wait.setSR(SR)
    bp_wait.insertSegment(0, 'waituntil', waitbittime)

    bp_minimalwait = bb.BluePrint()
    bp_minimalwait.setSR(SR)
    bp_minimalwait.insertSegment(0, 'waituntil', 10/SR)  # FIXME!

    bp_ramptrig = bb.BluePrint()  # segment to trigger the ramp
    bp_ramptrig.insertSegment(0, 'waituntil', trig_duration)
    bp_ramptrig.marker2 = [(0, trig_duration)]  # the signal to trigger a new ramp
    bp_ramptrig.setSR(SR)

    bp_return = bb.BluePrint()
    bp_return.insertSegment(0, 'waituntil', 10/SR)
    bp_return.setSR(SR)

    # The one-element router sequence
    routerelem = bb.Element()
    routerelem.addBluePrint(1, bp_minimalwait)

    routerseq = bb.Sequence()
    routerseq.addElement(1, routerelem)
    routerseq.setSequenceSettings(1, 1, 1, 0, 0)  # overridden below
    routerseq.setSR(SR)
    routerseq.setChannelVoltageRange(1, 2*pulsehigh, 0)

    # The base sequence to be repeated and varied
    resetelem = bb.Element()
    resetelem.addBluePrint(1, bp_wait)

    trigrampelem = bb.Element()
    trigrampelem.addBluePrint(1, bp_ramptrig)

    mainelem = bb.Element()
    mainelem.addBluePrint(1, bp_pulse)

    returnelem = bb.Element()
    returnelem.addBluePrint(1, bp_return)

    baseseq = bb.Sequence()

    baseseq.addElement(1, resetelem)
    baseseq.setSequenceSettings(1, 0, waitbits, 0, 0)

    baseseq.addElement(2, trigrampelem)
    baseseq.setSequenceSettings(2, 0, 1, 0, 0)

    baseseq.addElement(3, mainelem)
    baseseq.setSequenceSettings(3, 0, no_of_pulses, 0, 0)

    baseseq.addElement(4, returnelem)
    # is an event jump even needed? Can't we just rerun from top?
    baseseq.setSequenceSettings(4, 0, 0, 1, 0)

    baseseq.setSR(SR)
    baseseq.setChannelVoltageRange(1, 2*pulsehigh, 0)

    # Now make the variation
    poss = [3]
    channels = [1]
    names = [segname]
    args = ['duration']
    iters = [hightimes]

    # might as well have a bit of auto-debug...
    baseseq.checkConsistency(verbose=True)

    longseq = bb.repeatAndVarySequence(baseseq, poss, channels, names,
                                       args, iters)

    fullseq = routerseq + longseq

    # Now set all event jumps to point back to the first (routing) element
    for ii in range(len(hightimes)):
        fullseq.setSequenceSettings(1+(ii+1)*4, 0, 0, 1, 0)
    # And set the routing element to route correctly for the first iteration
    fullseq.setSequenceSettings(1, 1, 1, 0, 2)

    return fullseq


def _DPE_makeSequence(hightime, trig_delay, meastime, prewaittime,
                      cycletime,
                      no_of_pulses, pulsehigh, SR, segname):
    """
    Generate the pulse sequence for the experiment.

    The sequence consists of three parts:
    1: A wait with zeros allowing the ZI to get ready. This part is
    short, but repeated waitbits times
    2: A short zero part with the marker2 trigger for the ramp
    3: The high pulse and a marker1 trigger for the ZI

    Args:
        hightime (float): The width of the pulse (s)p
        trig_delay (float): The delay to start measuring after the end of the
            pulse (s).
        meastime (float): The time of each measurement (s).
        prewaittime (float): The time to wait before each ramp (s).
        cycletime (float): The time of each ramp (s).
        no_of_pulses (int): The number of pulse per ramp.
        pulsehigh (float): The amplitude of the pulse (V)
        SR (int): The AWG sample rate (Sa/s)
        segname (str): The name of the high pulse segment as used internally
            by broadbean.
    """

    waitbits = 100  # no. of repetitions of the first part
    waitbittime = prewaittime/waitbits
    trig_duration = 5e-6

    if waitbittime < 10/SR:
        raise ValueError('prewaittime too short.')

    # The pulsed part
    bp1 = bb.BluePrint()
    bp1.setSR(SR)
    bp1.insertSegment(0, ramp, (pulsehigh, pulsehigh),
                      durs=hightime, name=segname)
    bp1.insertSegment(1, ramp, (0, 0), durs=meastime, name='measure')
    # dead time for the scope to re-arm its trigger
    bp1.insertSegment(2, 'waituntil', cycletime)
    bp1.marker1 = [(hightime+trig_delay, 10e-6)]

    # initial wait time to allow ZI trigger to get ready. This BP is repeated
    bp3 = bb.BluePrint()
    bp3.setSR(SR)
    bp3.insertSegment(0, 'waituntil', waitbittime)

    bp4 = bb.BluePrint()  # segment to trigger the ramp
    bp4.insertSegment(0, 'waituntil', trig_duration)
    bp4.marker2 = [(0, trig_duration)]  # the signal to trigger a new ramp
    bp4.setSR(SR)

    mainelem = bb.Element()
    mainelem.addBluePrint(1, bp1)

    trigelem = bb.Element()
    trigelem.addBluePrint(1, bp4)

    resetelem = bb.Element()
    resetelem.addBluePrint(1, bp3)

    seq = bb.Sequence()
    seq.addElement(1, resetelem)
    seq.addElement(2, trigelem)
    seq.addElement(3, mainelem)
    seq.setSR(SR)

    seq.setChannelVoltageRange(1, 2*pulsehigh, 0)

    seq.setSequenceSettings(1, 0, waitbits, 0, 2)
    seq.setSequenceSettings(2, 0, 1, 0, 3)
    # the last zero disables jumping, i.e. seq. plays once
    seq.setSequenceSettings(3, 0, no_of_pulses, 0, 0)

    return seq


@check_kwargs
def doPulsedExperiment(fast_axis=None, slow_axis=None,
                       slow_start=None, slow_stop=None, slow_npts=None,
                       fast_start=None, fast_stop=None, fast_npts=None,
                       # Acquisition variables
                       n_avgs=None,
                       pts_per_shot=None,
                       # Pulse variables
                       hightime=None,
                       meastime=None,
                       cycletime=None,
                       transfertime=None,
                       pulsehigh=None,
                       trig_delay=None,
                       # Demodulation variables
                       demod_freq=None,
                       # AWG setting
                       awg_channel=None,
                       awg=None, ZI=None, keysight=None):
    """
    Top level function for performing pulsed experiments, i.e. sending a
    single square pulse riding on a ramp to the sample and measuring by
    demodulating and shining RF with a ZI UHF-LI
    """

    # INPUT VALIDATORS
    fa_vals = ['ramp']
    sa_vals = ['dt']  # TODO: add 'amp' and maybe even DC

    # VALIDATION
    if fast_axis not in fa_vals:
        raise NotImplementedError('Fast axis specifier '
                                  'must be in {}.'.format(fa_vals))
    if slow_axis not in sa_vals:
        raise NotImplementedError('Slow axis specifier '
                                  'must be in {}.'.format(sa_vals))

    if cycletime < 200e-6:
        raise ValueError('Cycle time too low. Must be at least 200 mu s')
    if transfertime < 150e-3:
        raise ValueError('Transfer time too low. Must be at least 150 ms.')

    # Settings we hide from the experimenalists
    # trig_duration = 10e-6  # not used currently. Is it needed?
    SR = 1e9

    # Meas. time calculation
    meastime, SRstring = _DPE_correct_meastime(meastime, pts_per_shot)

    # Prepare the instruments

    # Keysight
    _DPE_prepareKeysight(no_of_pulses=fast_npts, cycletime=cycletime,
                         ramp_low=fast_start, ramp_high=fast_stop,
                         keysight=keysight)

    # AWG
    _DPE_prepareTektronixAWG(awg=awg, awg_channel=awg_channel, SR=SR,
                             pulsehigh=pulsehigh)

    # ZI UHF-LI
    _DPE_prepareZIUHFLI(zi=ZI, demod_freq=demod_freq,
                        pts_per_shot=pts_per_shot, SRstring=SRstring,
                        no_of_pulses=fast_npts, meastime=meastime)

    # Build the basesequence
    base_sequence = _DPE_makeSequence(hightime=hightime, trig_delay=trig_delay,
                                      meastime=meastime,
                                      prewaittime=transfertime,
                                      cycletime=cycletime,
                                      no_of_pulses=fast_npts,
                                      pulsehigh=pulsehigh,
                                      SR=SR, segname='high')

    # Make the two measurement parameters
    if slow_axis == 'dt':
        pulseTime = PulseTime(name='pulse_time', basesequence=base_sequence,
                              pos=3, chan=1, segname='high', awg=awg,
                              awgchannels=[awg_channel])

    # setpoints
    voltages = np.linspace(fast_start, fast_stop, fast_npts)

    ramp_avg = AverageRampResponse(name='ramp_response', awg=awg, zi=ZI,
                                   no_of_avgs=n_avgs, voltages=voltages,
                                   awg_channel=awg_channel,
                                   label='Demod response', unit=None)

    awg.parameters['pulsetime'] = pulseTime
    pulseTime._instrument = awg
    awg.parameters['ramp_avg'] = ramp_avg
    ramp_avg._instrument = awg

    do1d(pulseTime, slow_start, slow_stop, slow_npts, 0, ramp_avg)


def showPulsedExperiment(fast_npts=None,
                         hightime=None,
                         meastime=None,
                         cycletime=None,
                         transfertime=None,
                         pulsehigh=None,
                         trig_delay=None):
    """
    Function to visualise the pulsed experiment
    """

    seq = _DPE_makeSequence(hightime=hightime,
                            trig_delay=trig_delay,
                            meastime=meastime,
                            prewaittime=transfertime,
                            cycletime=cycletime,
                            no_of_pulses=fast_npts,
                            pulsehigh=pulsehigh,
                            SR=1e9, segname='high')


    seq.plotSequence()


def print_all_instruments():
    """
    Just me testing a clever use of a class variable
    """
    station = qc.Station.default

    print(station.components)
