# This whole cell belongs in a separate script/wrapper file
import time
import numpy as np
import qcodes as qc
from os.path import sep
from qcodes import DataArray
from qcodes.data.data_set import new_data
from qcodes.instrument.parameter import ArrayParameter
import broadbean as bb
ramp = bb.PulseAtoms.ramp
from alazar_controllers.ATSChannelController import ATSChannelController
from alazar_controllers.alazar_channel import AlazarChannel
from qcodes.utils.wrappers import CURRENT_EXPERIMENT
import multiprocessing as mp
import logging

log = logging.getLogger(__name__)


def makeSimpleSequence(hightime, trig_delay, meastime,
                       cycletime, pulsehigh, pulselow,
                       no_of_avgs, SR,
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
        pulselow (float): The amplitude during the measurement (V)
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
    bp1.insertSegment(1, ramp, (pulselow, pulselow),
                      durs=meastime, name='measure')
    # dead time for the scope to re-arm its trigger
    bp1.insertSegment(2, 'waituntil', cycletime)
    bp1.marker1 = [(hightime+trig_delay, meastime)]
    bp1.marker2 = [(hightime+trig_delay, meastime)]

    if compensation_ratio != 0:
        # area to compensate for
        area = pulsehigh*hightime+pulselow*meastime  # Area of pulse in V*s
        compensation_duration = compensation_ratio*(hightime+meastime)
        compensation_height = -area/compensation_duration
        bp1.insertSegment(0, ramp, (compensation_height, compensation_height),
                          durs=compensation_duration)

        # update the marker timing
        bp1.marker1 = [(hightime+trig_delay+compensation_duration,
                        meastime)]
        bp1.marker2 = [(hightime+trig_delay+compensation_duration,
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


def makeT1Sequence(hightime, trig_delay, RF_delay, meastime,
                   cycletime, pulsehigh, pulselow,
                   no_of_avgs, SR,
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
        RF_delay (float): The delay of marker1 relatively to the pulse switch off
        meastime (float): The time of each measurement (s).
        cycletime (float): The time of each pulse-measure cycle (s).
        pulsehigh (float): The amplitude of the pulse (V)
        pulselow (float): The amplitude during the measurement (V)
        no_of_avgs (int): The number of averages
        SR (int): The AWG sample rate (Sa/s)
        compensation_ratio (float): The time of the compensation pre-pulse
            (to ensure zero integral of the pulse) expressed as the ratio
            of the prepulse duration to the hightime+meastime. If zero, then
            no compensation is performed.
    """

    if compensation_ratio < 0:
        raise ValueError('compensation_ratio must bea positive number')

    # The pulsed part
    bp1 = bb.BluePrint()
    bp1.setSR(SR)
    bp1.insertSegment(0, ramp, (pulsehigh, pulsehigh),
                      durs=hightime, name='high')
    bp1.insertSegment(1, ramp, (pulselow, pulselow),
                      durs=meastime, name='measure')
    # dead time for the scope to re-arm its trigger
    bp1.insertSegment(2, 'waituntil', cycletime)
    bp1.marker1 = [(hightime+RF_delay, meastime)]
    bp1.marker2 = [(hightime+trig_delay, meastime)]

    if compensation_ratio != 0:
        # area to compensate for
        area = pulsehigh*hightime+pulselow*meastime  # Area of pulse in V*s
        compensation_duration = compensation_ratio*(hightime+meastime)
        compensation_height = -area/compensation_duration
        bp1.insertSegment(0, ramp, (compensation_height, compensation_height),
                          durs=compensation_duration)

        # update the marker timing
        bp1.marker1 = [(hightime+RF_delay+compensation_duration,
                        meastime)]
        bp1.marker2 = [(hightime+trig_delay+compensation_duration,
                        meastime)]

    # In front of the real sequence, we need some dead time to
    # allow the scope to arm its trigger. The problem is that
    # the scope.get is blocking. Luckily, running the AWG is not
    # therefore, we do:
    # awg.run(); scope.get()
    # with some dead time in the awg.run()


    mainelem = bb.Element()
    mainelem.addBluePrint(1, bp1)

    seq = bb.Sequence()
    seq.addElement(1, mainelem)
    seq.setSR(SR)

    # NB: We have not specified voltage ranges yet
    # this will be done when the uploading is to happen


    # the last zero disables jumping, i.e. seq. plays once
    seq.setSequenceSettings(1, 0, no_of_avgs, 0, 0)

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


def makeT2Sequence(hightimes, trig_delay, RF_delay, meastime,
                       cycletime, pulsehigh, pulselow,
                       no_of_avgs, SR):
    """
    Generate the pulse sequence for the experiment.
    The sequence consists of three parts:
    1: A wait with zeros allowing the ZI to get ready. This part is
    short, but repeated waitbits times
    2: A short zero part with the marker2 trigger for the ramp
    3: The high pulse and a marker1 trigger for the ZI
    Args:
        hightimes (iterables): The widths of the pulse (s)
        trig_delay (float): The delay to start measuring after the end of the
            pulse (s).
        meastime (float): The time of each measurement (s).
        cycletime (float): The time of each pulse-measure cycle (s).
        pulsehigh (float): The amplitude of the pulse (V)
        pulselow (float): The amplitude during the measurement (V)
        no_of_avgs (int): The number of averages
        SR (int): The AWG sample rate (Sa/s)
    """

    segname = 'high'


    # Fail if the sequence would end up being too long for the AWG to handle
    if len(hightimes)*cycletime*SR >= 16e6:
        raise ValueError("Sequence too long. You are trying to build a "
                         "sequence with {:d} MSamples. The maximally allowed "
                         "number of samples is "
                         "16 MSamples.".format(int(len(hightimes)*cycletime*SR/1e6)))

    ##################################################################
    # The pulsed part

    bp1 = bb.BluePrint()
    bp1.setSR(SR)
    bp1.insertSegment(0, ramp, (pulsehigh, pulsehigh),
                      durs=hightimes[0], name=segname)
    bp1.insertSegment(1, ramp, (pulselow, pulselow),
                      durs=meastime, name='measure')
    # dead time for the scope to re-arm its trigger
    bp1.insertSegment(2, 'waituntil', cycletime)

    bp1.setSegmentMarker(segname, (RF_delay, meastime), 1)  # segment name, (delay, duration), markerID
    bp1.setSegmentMarker(segname, (trig_delay, meastime), 2)

    pulseelem = bb.Element()
    pulseelem.addBluePrint(1, bp1)
    
    seq = bb.Sequence()
    seq.setSR(SR)
    
    for index, ht in enumerate(hightimes):
        
        elem = pulseelem.copy()
        elem.changeDuration(1, segname, ht)
        seq.addElement(index+1, elem)
        seq.setSequenceSettings(index+1, 0, no_of_avgs, 0, 0)

    return seq



def prepareZIUHFLI(zi, demod_freq, pts_per_shot,
                   SRstring, no_of_avgs, meastime, outputpwr,
                   single_channel=False):
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
        outputpwr (float): The output power of the ZI UHF-LI (dBm)
        single_channel (bool): Whether to subscribe the scope to just a
            single channel. If true, channel 1 will be used. Default: False.
    """

    # Demodulator
    zi.oscillator1_freq(demod_freq)
    zi.demod1_order(1)
    zi.demod1_timeconstant(100e-9)
    zi.signal_output1_on('ON')
    # TODO: use this in post-processing to remove first part of demod. data

    # output
    zi.signal_output1_ampdef('dBm')
    zi.signal_output1_amplitude(outputpwr)

    # input
    zi.signal_input1_range(30e-3)
    zi.signal_input2_range(30e-3)

    # Scope
    zi.scope_channel1_input('Demod 1 R')
    zi.scope_channel2_input('Signal Input 2')
    zi.scope_mode('Time Domain')
    zi.scope_samplingrate(SRstring)
    zi.scope_length(pts_per_shot)
    if single_channel:
        zi.scope_channels(1)
    else:
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


def prepareZIUHFLIForAlazar(zi, demod_freq, outputpwr, signalscaling):
    """
    Prepare the ZI UHF-LI

    Args:
        zi (ZIUHFLI): QCoDeS instrument instance
        demod_freq (float): The demodulation frequency (Hz)
        outputpwr (float): The output power of the ZI UHF-LI (dBm)
        signalscaling (float): Scaling factor to apply AUX 1 Output signal
    """

    # Demodulator
    zi.oscillator1_freq(demod_freq)
    zi.demod1_order(1)
    zi.demod1_timeconstant(100e-9)
    zi.signal_output1_on('ON')
    # TODO: use this in post-processing to remove first part of demod. data

    # output
    zi.signal_output1_ampdef('dBm')
    zi.signal_output1_amplitude(outputpwr)

    # input
    zi.signal_input1_range(30e-3)
    zi.signal_input2_range(30e-3)


    # output
    zi.aux_out1.output('Demod R')
    zi.aux_out1.channel(1)
    zi.aux_out1.limitupper(0.4)
    zi.aux_out1.limitlower(-0.4)
    zi.aux_out1.scale(signalscaling)


def setupAlazarForT1(alazar, sampling_rate):
    # Configure all settings in the Alazar card
    alazar.config(clock_source='INTERNAL_CLOCK',
                  sample_rate=sampling_rate,
                  #clock_source='EXTERNAL_CLOCK_10MHz_REF',
                  #external_sample_rate=sampling_rate,
                  clock_edge='CLOCK_EDGE_RISING',
                  decimation=1,
                  coupling=['DC','DC'],
                  channel_range=[.4,.4],
                  impedance=[50,50],
                  trigger_operation='TRIG_ENGINE_OP_J',
                  trigger_engine1='TRIG_ENGINE_J',
                  trigger_source1='EXTERNAL',
                  trigger_slope1='TRIG_SLOPE_POSITIVE',
                  trigger_level1=160,
                  trigger_engine2='TRIG_ENGINE_K',
                  trigger_source2='DISABLE',
                  trigger_slope2='TRIG_SLOPE_POSITIVE',
                  trigger_level2=128,
                  external_trigger_coupling='DC',
                  external_trigger_range='ETR_TTL',
                  trigger_delay=0,
                  timeout_ticks=0,
                  aux_io_mode='AUX_IN_AUXILIARY', # AUX_IN_TRIGGER_ENABLE for seq mode on
                  aux_io_param='NONE' # TRIG_SLOPE_POSITIVE for seq mode on
                 )


def setupAlazarForT2(alazar, sampling_rate):
    # Configure all settings in the Alazar card
    alazar.config(clock_source='INTERNAL_CLOCK',
                  sample_rate=sampling_rate,
                  #clock_source='EXTERNAL_CLOCK_10MHz_REF',
                  #external_sample_rate=sampling_rate,
                  clock_edge='CLOCK_EDGE_RISING',
                  decimation=1,
                  coupling=['DC','DC'],
                  channel_range=[.4,.4],
                  impedance=[50,50],
                  trigger_operation='TRIG_ENGINE_OP_J',
                  trigger_engine1='TRIG_ENGINE_J',
                  trigger_source1='EXTERNAL',
                  trigger_slope1='TRIG_SLOPE_POSITIVE',
                  trigger_level1=160,
                  trigger_engine2='TRIG_ENGINE_K',
                  trigger_source2='DISABLE',
                  trigger_slope2='TRIG_SLOPE_POSITIVE',
                  trigger_level2=128,
                  external_trigger_coupling='DC',
                  external_trigger_range='ETR_TTL',
                  trigger_delay=0,
                  timeout_ticks=0,
                  aux_io_mode='AUX_IN_AUXILIARY', # AUX_IN_TRIGGER_ENABLE for seq mode on
                  aux_io_param='NONE' # TRIG_SLOPE_POSITIVE for seq mode on
                 # aux_io_mode='AUX_IN_TRIGGER_ENABLE', 
                 # aux_io_param='TRIG_SLOPE_POSITIVE'
                 )    
    
def setupAlazarControllerForT1(alazar):
    myctrl = ATSChannelController(name='my_controller', alazar_name='Alazar')
    chan1 = AlazarChannel(myctrl, 'mychan', demod=False, integrate_samples=False)
    return chan1
    
    
def setupAlazarControllerForT2(alazar):
    myctrl = ATSChannelController(name='my_controller_t2', alazar_name='Alazar')
    chan1 = AlazarChannel(myctrl, 'T2', demod=False, integrate_samples=False,
                          average_buffers=False)
    return chan1

class AlazarValues(ArrayParameter):
    
    def __init__(self, name, instrument, chan,\
                 save_raw_data=True):
        super().__init__(name=name,
                         shape=(1,),
                         label='Avg. demod. response',
                         unit='Vrms',
                         setpoint_names=('pulse_width',),
                         setpoint_labels=('Pulse width',),
                         setpoint_units=('s',))
        
        self._instrument = instrument
        self._channel = chan
        self._rawdatacounter = 0
        self._ready = False
        self._save_raw_data = save_raw_data
#        self._pool = mp.Pool(30)
#        self._result = []
        
    def prepare_alazar_values(self, pulsewidths):
        self.setpoints = (tuple(pulsewidths),)
        self.shape = (len(pulsewidths),)
        self._rawdatacounter = 0
        self._ready = True
    
    @staticmethod
    def save_single_raw_file(xdata, my_raw_data, rawdatacounter, maincounter):
        xarr = DataArray(preset_data=xdata, is_setpoint=True, name='time', label='Time', unit='s')
        yarr = DataArray(preset_data=my_raw_data,
                         set_arrays=(xarr,), name='demodulated_signal', label='Demodulated Signal', unit='V')
        name = '{0:06d}'.format(rawdatacounter)
        locstring = '{}{:03}_raw{}'.format(CURRENT_EXPERIMENT['exp_folder'],
                                           maincounter, sep)
        rawdataset = new_data(location=locstring, arrays=[xarr, yarr])
        rawdataset.formatter.number_format = '{:g}'
        rawdataset.formatter.extension = '.raw'
        rawdataset.finalize(filename=name, write_metadata=False)
        print('Wrote rawdata to {}'.format(rawdataset.location))

    def get_raw(self):
        
        raw_data = self._channel.data.get()
#        print("waiting for results")
#        for res in self._result:
#            print("waiting for {}".format(res))
#            res.get()
#        self._result = []
        
        #####################################
        # Save raw data to disk
        loc_provider = qc.data.data_set.DataSet.location_provider
        maincounter = loc_provider.counter
        
        xdata = self._channel.data.setpoints[1][0]
        
        # simple tests for signal scaling correctness
        max_val = raw_data.max()
        min_val = raw_data.min()
        
        if max_val > 0.39:
            log.warning('Maximum voltage at the upper clipping edge detected.')
        if min_val < -0.39:
            log.warning('Minimum voltage at the lower clipping edge detected.')
        
        if max_val - min_val < 0.004:
            log.warning('Entire signal falls within 1% of the available '
                        'dynamic Alazar range. Consider rescaling it.')
        
        if self._save_raw_data:
            for rowind in range(np.shape(raw_data)[0]):
#                self._result.append(self._pool.apply_async(self.save_single_raw_file, 
#                                       (xdata, 
#                                        raw_data[rowind,:], 
#                                        self._rawdatacounter, 
#                                        maincounter)))
                
                self.save_single_raw_file(xdata, raw_data[rowind,:], self._rawdatacounter, maincounter)
                self._rawdatacounter += 1


        avg_data = np.mean(raw_data, 1)
        return avg_data