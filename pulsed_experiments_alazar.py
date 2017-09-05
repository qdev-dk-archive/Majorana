import numpy as np
from inspect import signature
from Typing import List

import broadbean as bb
import qcodes as qc
from qcodes.instrument.parameter import ArrayParameter, StandardParameter
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

    TODO: put in Alazar card response
    """

    def __init__(self):
        pass


class PulseTime(StandardParameter):
    """
    The parameter setting a new pulsetime.

    TODO: write
    """

    def __init__(self):
        pass


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


def _DPE_prepareAlazar():
    """
    Prepare the Alazar card

    TODO: write
    """

    pass


def _DPE_correct_meastime(meastime: float, npts: int,
                          SRs: List[float]) -> float:
    """
    Given a number of points to measure, and a desired measurement time,
    find the measurement time closest to the given one that the alazar can
    actually realise.

    Args:
        meastime: The desired measurement time
        npts: The desired number of points
        SRs: The sample rates of the acquisition system

    Returns:
        The new measurement time
    """

    # TODO: is a logarithmic error measure better than a linear one?

    realtimes = np.array([npts/SR for SR in SRs])
    errors = np.abs(meastime-realtimes)

    newtime = realtimes[errors.argmin()]

    # Do some rounding for safety
    newtime = float('{:.4e}'.format(newtime))

    return newtime


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

    # Alazar
    _DPE_prepareAlazar()

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
