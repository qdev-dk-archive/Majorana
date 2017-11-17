# This whole cell belongs in a separate script/wrapper file

import numpy as np
from qcodes.instrument.parameter import ArrayParameter
import broadbean as bb
ramp = bb.PulseAtoms.ramp


def makeSimpleSequence(hightime, trig_delay, meastime,
                       cycletime, pulsehigh, no_of_avgs, SR,
                       compensation_ratio=0):
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
        cycletime (float): The time of each pulse-measure cycle (s).
        pulsehigh (float): The amplitude of the pulse (V)
        no_of_avgs (int): The number of averages
        SR (int): The AWG sample rate (Sa/s)
        compensation_ratio (float): The time of the compensation pre-pulse
            (to ensure zero integral of the pulse) expressed as the ratio
            of the prepulse duration to the hightime+meastime. If zero, then
            no compensation is performed.
    """

    segname = 'high'
    trigarmtime = 100e-6  # how long does the ZI need to arm its trigger?
    trigbits = 100

    if compensation_ratio < 0:
        raise ValueError('compensation_ratio must bea positive number')

    # The pulsed part
    bp1 = bb.BluePrint()
    bp1.setSR(SR)
    bp1.insertSegment(0, ramp, (pulsehigh, pulsehigh),
                      durs=hightime, name=segname)
    bp1.insertSegment(1, ramp, (0, 0), durs=meastime, name='measure')
    # dead time for the scope to re-arm its trigger
    bp1.insertSegment(2, 'waituntil', cycletime)
    bp1.marker1 = [(hightime+trig_delay, meastime)]

    if compensation_ratio != 0:
        # area to compensate for
        area = pulsehigh*hightime  # Area of pulse in V*s
        compensation_duration = compensation_ratio*(hightime+meastime)
        compensation_height = -area/compensation_duration
        bp1.insertSegment(0, ramp, (compensation_height, compensation_height),
                          durs=compensation_duration)

        # update the marker timing
        bp1.marker1 = [(hightime+trig_delay+compensation_duration,
                        meastime)]

    # In front of the real sequence, we need some dead time to
    # allow the scope to arm its trigger. The problem is that
    # the scope.get is blocking. Luckily, running the AWG is not
    # therefore, we do:
    # awg.run(); scope.get()
    # with some dead time in the awg.run()

    prebp = bb.BluePrint()
    prebp.insertSegment(0, ramp, (0, 0), durs=trigarmtime/trigbits)
    prebp.setSR(SR)

    pretrigelem = bb.Element()
    pretrigelem.addBluePrint(1, prebp)

    mainelem = bb.Element()
    mainelem.addBluePrint(1, bp1)

    seq = bb.Sequence()
    seq.addElement(1, pretrigelem)
    seq.addElement(2, mainelem)
    seq.setSR(SR)

    # NB: We have not specified voltage ranges yet
    # this will be done when the uploading is to happen

    seq.setSequenceSettings(1, 0, trigbits, 0, 0)
    # the last zero disables jumping, i.e. seq. plays once
    seq.setSequenceSettings(2, 0, no_of_avgs, 0, 0)

    return seq


def sendSequenceToAWG(awg, seq):
    """
    Function to upload a sequence to an AWG (5014C)
    The sequence is checked to be realisable on the AWG,
    i.e. do sample rates match? Are the voltages within the
    range on the AWG?

    Args:
        awg (Tektronix_AWG5014): The relevant awg
        seq (bb.Sequence): The sequence to upload
    """

    # Check sample rates
    if awg.clock_freq() != seq.SR:
        raise ValueError('AWG sample rate does not match '
                         'sequence sample rate. Rates: '
                         '{} Sa/s and {} Sa/s'.format(awg.clock_freq(), seq.SR))

    seq.setChannelVoltageRange(1, awg.ch1_amp(), awg.ch1_offset())

    package = seq.outputForAWGFile()
    awg.make_send_and_load_awg_file(*package[:])


class Scope_avg(ArrayParameter):

    def __init__(self, name, channel=1, **kwargs):

        super().__init__(name, shape=(1,), **kwargs)
        self.has_setpoints = False
        self.zi = self._instrument

        if channel not in [1, 2]:
            raise ValueError('Channel must be 1 or 2')

        self.channel = channel

    def make_setpoints(self):
        """
        Makes setpoints and prepares the averager (updates its unit)
        """

        sp_start = 0
        sp_stop = self._instrument.scope_duration()
        sp_npts = self._instrument.scope_length()

        self.shape = (sp_npts,)
        self.setpoint_labels = ('Time',)
        self.setpoint_units = ('s',)  #  self._instrument.Scope.units[self.channel-1]
        self.setpoints = (tuple(np.linspace(sp_start, sp_stop, sp_npts)),)
        self.has_setpoints = True

    def get_raw(self):

        if not self.has_setpoints:
            raise ValueError('Setpoints not made. Run make_setpoints')

        data = self._instrument.Scope.get()[self.channel-1]
        return np.mean(data, 0)


def correctMeasTime(meastime, npts):
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

    if npts < 4096:
        raise ValueError('Sorry, but npts must be at least 4096.')

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


def prepareZIUHFLI(zi, demod_freq, pts_per_shot,
                   SRstring, no_of_avgs, meastime):
    """
    Prepare the ZI UHF-LI

    Args:
        zi (ZIUHFLI): QCoDeS instrument instance
        demod_freq (float): The demodulation frequency (Hz)
        pts_per_shot (int): No. of points per measurement. Most likely 4096.
        SRstring (str): The string version of the sample rate used by the
            lock-in, e.g. '113 MHz'. Should be the output of
            _DPE_correct_meastime.
        no_of_pulses (int): No. of averages, i.e. number
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
    zi.scope_trig_signal('Trig Input 2')
    zi.scope_trig_level(0.5)  # we expect the AWG marker to have a 1 V high lvl
    #
    zi.scope_segments('ON')
    zi.scope_segments_count(no_of_avgs)
