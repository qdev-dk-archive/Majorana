import logging

import qcodes as qc
from qcodes.utils.validators import Numbers

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

    parnames = sorted([par for par in qdac.parameters.keys()
                       if par.endswith('_v')])
    for parname in parnames:
        print('{}: {} V'.format(parname, qdac.parameters[parname].get()))

    check_unused_qdac_channels()


def qdac_slopes():
    """
    Returns a dict with the QDac slopes defined in the config file
    """

    config = Config.default

    qdac_slope = float(config.get('Ramp speeds',
                                  'max rampspeed qdac'))
    bg_slope = float(config.get('Ramp speeds',
                                'max rampspeed bg'))
    bias_slope = float(config.get('Ramp speeds',
                                  'max rampspeed bias'))

    QDAC_SLOPES = dict(zip(used_channels(),
                           len(used_channels())*[qdac_slope]))

    QDAC_SLOPES[int(config.get('Channel Parameters',
                               'backgate channel'))] = bias_slope
    for ii in bias_channels():
        QDAC_SLOPES[ii] = bias_slope

    return QDAC_SLOPES


def check_unused_qdac_channels():
    """
    Check whether any UNASSIGNED QDac channel has a non-zero voltage
    """
    station = qc.Station.default

    qdac = station['qdac']

    qdac._get_status()
    for ch in [el for el in range(1, 48) if el not in used_channels()]:
        temp_v = qdac.parameters['ch{:02}_v'.format(ch)].get_latest()
        if temp_v > 0.0:
            log.warning('Unused qDac channel not zero: channel '
                        '{:02}: {}'.format(ch, temp_v))

def get_current(dmm, iv_conv):
    """get_cmd for dmm readout of IV_TAMP parameter"""
    return dmm.volt()/iv_conv*1E12

# Delete ivconv parameters, if they are already defined
try:
    del keysightdmm_top.parameters['ivconv']
except KeyError:
    pass

keysightdmm_top.add_parameter(name='ivconv',
                              label='Current (pA)',
                              unit='',
                              get_cmd=partial(get_current, keysightdmm_top, 
                              float(configs.get('Gain settings', 'iv topo gain'))),
                              set_cmd=None)
            
            
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


def reload_QDAC_settings():
    """
    Function to update the qdac based on the configuration file
    """

    config = Config.default
    station = qc.Station.default

    # Update the voltage dividers
    topo_dc = float(config.get('Gain settings',
                               'dc factor topo'))
    sens_r_dc = float(config.get('Gain settings',
                                 'dc factor right'))
    sens_l_dc = float(config.get('Gain settings',
                                 'dc factor left'))
    qdac = station['qdac']
    qdac.topo_bias.division_value = topo_dc
    qdac.sens_r_bias.division_value = sens_r_dc
    qdac.sens_l_bias.division_value = sens_l_dc

    # Set the range validators
    # NB: This is the voltage AT the QDac, BEFORE votlage dividers
    ranges = config.get('Channel ranges')
    for chan in range(1, 49):
        try:
            chan_range = ranges[str(chan)]
        except KeyError:
            continue

        minmax = chan_range.split(" ")
        if len(minmax) != 2:
            raise ValueError("Expected: min max. Got {}".format(chan_range))
        else:
            rangemin = float(minmax[0])
            rangemax = float(minmax[1])

        vldtr = Numbers(rangemin, rangemax)
        qdac.parameters['ch{:02}_v'.format(chan)].set_validator(vldtr)

    # Update the channels' labels
    labels = channel_labels()
    for chan, label in labels.items():
        qdac.parameters['ch{:02}_v'.format(chan)].label = label
