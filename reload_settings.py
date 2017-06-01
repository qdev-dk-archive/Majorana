from functools import partial
import logging

import qcodes as qc
from qcodes.instrument_drivers.devices import VoltageDivider
from qcodes.utils.validators import Numbers

from qcodes.instrument.parameter import ManualParameter
from qcodes.utils.validators import Enum

from .configreader import Config

log = logging.getLogger(__name__)


def bias_channels():
    """
    A convenience function returning a list of bias channels.
    """

    configs = Config.default

    bias_chan1 = configs.get('Channel Parameters', 'topo bias channel')
    bias_chan2 = configs.get('Channel Parameters', 'left sensor bias channel')
    bias_chan3 = configs.get('Channel Parameters', 'right sensor bias channel')

    return [int(bias_chan1), int(bias_chan2), int(bias_chan3)]


def used_channels():
    """
    Return a list of currently labelled channels as ints.
    """

    configs = Config.default

    l_chs = configs.get('QDac Channel Labels')
    return sorted([int(key) for key in l_chs.keys()])


def used_voltage_params():
    """
    Returns a list of qdac voltage parameters for the used channels
    """
    station = qc.Station.default

    qdac = station['qdac']

    chans = sorted(used_channels())
    voltages = [qdac.parameters['ch{:02}_v'.format(ii)] for ii in chans]

    return voltages


def channel_labels():
    """
    Returns a dict of the labelled channels. Key: channel number (int),
    value: label (str)
    """
    configs = Config.default

    labs = configs.get('QDac Channel Labels')
    output = dict(zip([int(key) for key in labs.keys()], labs.values()))

    return output


def print_voltages_all():
    """
    Convenience function for printing all qdac voltages
    """

    station = qc.Station.default
    qdac = station['qdac']

    parnames = sorted([par for par in qdac.parameters.keys() if par.endswith('_v')])
    for parname in parnames:
        print('{}: {} V'.format(parname, qdac.parameters[parname].get()))

    check_unused_qdac_channels()


def qdac_slopes():
    """
    Returns a dict with the QDac slopes defined in the config file
    """
    qdac_slope = float(configs.get('Ramp speeds',
                                   'max rampspeed qdac'))
    bg_slope = float(configs.get('Ramp speeds',
                                 'max rampspeed bg'))
    bias_slope = float(configs.get('Ramp speeds',
                                   'max rampspeed bias'))

    QDAC_SLOPES = dict(zip(used_channels(),
                           len(used_channels())*[qdac_slope]))

    QDAC_SLOPES[int(configs.get('Channel Parameters',
                                'backgate channel'))] = bias_slope
    for ii in bias_channels():
        QDAC_SLOPES[ii] = bias_slope

    return QDAC_SLOPES

def check_unused_qdac_channels():
    qdac._get_status()
    for ch in [el for i, el in enumerate(range(1,48)) if el not in used_channels()]:
        temp_v = qdac.parameters['ch{:02}_v'.format(ch)].get_latest()
        if temp_v > 0.0:
            log.warning('Unused qDac channel not zero: channel {:02}: {}'.format(ch, temp_v))

check_unused_qdac_channels()


def reload_SR830_settings():
    """
    Function to update the SR830 voltage divider values based on the conf. file
    """

    # Get the two global objects containing the instruments and settings
    station = qc.Station.default
    configs = Config.default

    # one could put in some validation here if wanted

    lockin_topo = station['lockin_topo']
    lockin_right = station['lockin_right']
    lockin_left = station['lockin_left']

    lockin_topo.acfactor = float(configs.get('Gain settings',
                                             'ac factor topo'))
    lockin_right.acfactor = float(configs.get('Gain settings',
                                              'ac factor right'))
    lockin_left.acfactor = float(configs.get('Gain settings',
                                             'ac factor left'))

    lockin_topo.ivgain = float(configs.get('Gain settings',
                                           'iv topo gain'))
    lockin_right.ivgain = float(configs.get('Gain settings',
                                            'iv right gain'))
    lockin_left.ivgain = float(configs.get('Gain settings',
                                           'iv left gain'))

    lockin_topo.dcfactor = float(configs.get('Gain settings',
                                             'dc factor topo'))
    lockin_right.dcfactor = float(configs.get('Gain settings',
                                              'dc factor right'))
    lockin_left.dcfactor = float(configs.get('Gain settings',
                                             'dc factor left'))

##################################################
# The QDAC dict exposed to the user. This dict contains a mapping from
# channel number to QCoDeS object whose 'get' method returns the voltage
# AT SAMPLE (attenuation not taken into account yet) from that channel

# first initialise it with the 'raw' voltages
QDAC = dict(zip(used_channels(), used_voltage_params()))

# User defined special channels with special names exposed to the user
topo_bias = VoltageDivider(QDAC[int(configs.get('Channel Parameters',
                                                'topo bias channel'))],
                           float(configs.get('Gain settings',
                                             'dc factor topo')))
sens_r_bias = VoltageDivider(QDAC[int(configs.get('Channel Parameters',
                                                  'right sensor bias channel'))],
                             float(configs.get('Gain settings',
                                               'dc factor right')))
sens_l_bias = VoltageDivider(QDAC[int(configs.get('Channel Parameters',
                                                  'left sensor bias channel'))],
                             float(configs.get('Gain settings',
                                               'dc factor left')))
# update the QDAC dict with these as well
QDAC[int(configs.get('Channel Parameters', 'topo bias channel'))] = topo_bias
QDAC[int(configs.get('Channel Parameters', 'left sensor bias channel'))] = sens_l_bias
QDAC[int(configs.get('Channel Parameters', 'right sensor bias channel'))] = sens_r_bias

# now overwrite the channel labels
for ch in used_channels():
    QDAC[ch].label = channel_labels()[ch]


# A dictionary with max ramp speed for qDac channels.
# Bias channels, backgate and cutters/plungers have their own values
QDAC_SLOPES = qdac_slopes()


def set_ranges(qdac_channel_dictionary):
    """
    Set ranges to channels if:
    - channels range are defined
    - in the config file and if the channel is in use.

    Args:
      -qdac_channel_dictionary: dict of chan_id:chan parameter
    """
    ranges = configs.get('Channel ranges')
    for chan_id in qdac_channel_dictionary:
        try:
            chan_range = ranges[str(chan_id)]
        except KeyError:
            log.debug("No range defined for chan %s. Using default.", chan_id)
            continue

        minmax = chan_range.split(" ")
        if len(minmax) != 2:
            raise ValueError("Expected: min max. Got {}".format(chan_range))
        else:
            rangemin = float(minmax[0])
            rangemax = float(minmax[1])
        channel = qdac_channel_dictionary[chan_id]
        if isinstance(channel, VoltageDivider):
            # set the validator on the underlying qdac channel
            channel.v1.set_validator(Numbers(rangemin, rangemax))
        else:
            channel.set_validator(Numbers(rangemin, rangemax))

set_ranges(QDAC)
