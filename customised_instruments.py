# -*- coding: utf-8 -*-
"""
Customised instruments with extra features such as voltage dividers and derived
parameters for use with T10
"""
import numpy as np

from qcodes.instrument_drivers.QDev.QDac_channels import QDac
from qcodes.instrument_drivers.stanford_research.SR830 import SR830
from qcodes.instrument_drivers.stanford_research.SR830 import ChannelBuffer
from qcodes.instrument_drivers.Keysight.Keysight_34465A import Keysight_34465A
from qcodes.instrument_drivers.devices import VoltageDivider
from qcodes.instrument_drivers.ZI.ZIUHFLI import ZIUHFLI
from qcodes import ArrayParameter, Parameter


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
        self.setpoint_labels = ('Time',)
        self.setpoint_units = ('s',)
        self.has_setpoints = True
        self.label = self.zi.parameters['scope_channel{}_input'.format(self.channel)].get()

    def get(self):

        if not self.has_setpoints:
            raise ValueError('Setpoints not made. Run make_setpoints')

        data = self._instrument.Scope.get()[self.channel-1]
        data_avg = np.mean(data, 0)

        # KDP: handle less than 4096 points
        # (4096 needs to be multiple of number of points)
        down_samp = np.int(self._instrument.scope_length.get()/self.shape[0])
        if down_samp > 1:
            data_ret = data_avg[::down_samp]
        else:
            data_ret = data_avg

        return data_ret


class Scope_full_avg(Parameter):
    """
    Parameter class to return the fully averaged value of N scope
    segments, i.e., N segments averaged together to a single point
    """

    def __init__(self, name, instrument, channel, **kwargs):
        super().__init__(name, instrument, **kwargs)

        if channel not in [1, 2]:
            raise ValueError('Channel must be 1 or 2')

        self.channel = channel
        self.label = instrument.parameters['scope_channel{}_input'.format(self.channel)].get()

    def get_raw(self):

        data = self._instrument.Scope.get()[self.channel-1]
        data_avg = np.mean(data)

        return data_avg


# A conductance buffer, needed for the faster 2D conductance measurements
# (Dave Wecker style)
class ConductanceBuffer(ChannelBuffer):
    """
    A full-buffered version of the conductance based on an
    array of X measurements

    We basically just slightly tweak the get method
    """

    def __init__(self, name: str, instrument: 'SR830_T10', **kwargs):
        super().__init__(name, instrument, channel=1)
        self.unit = ('e^2/h')

    def get(self):
        # If X is not being measured, complain
        if self._instrument.ch1_display() != 'X':
            raise ValueError('Can not return conductance since X is not '
                             'being measured on channel 1.')

        resistance_quantum = 25.818e3  # (Ohm)
        xarray = super().get()
        iv_conv = self._instrument.ivgain
        ac_excitation = self._instrument.amplitude_true()

        gs = xarray/iv_conv/ac_excitation*resistance_quantum

        return gs

# Subclass the SR830

class SR830_T10(SR830):
    """
    An SR830 with the following super powers:
        - a Voltage divider
        - An I/V converter
        - A conductance buffer
    """

    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, **kwargs)

        # using the vocabulary of the config file
        self.ivgain = 1
        self.__acf = 1

        self.add_parameter('amplitude_true',
                           parameter_class=VoltageDivider,
                           v1=self.amplitude,
                           division_value=self.acfactor)

        self.add_parameter('g',
                           label='{} conductance'.format(self.name),
                           # use lambda for late binding
                           get_cmd=self._get_conductance,
                           unit='e^2/h',
                           get_parser=float)

        self.add_parameter('conductance',
                           label='{} conductance'.format(self.name),
                           parameter_class=ConductanceBuffer)

    def _get_conductance(self):
        """
        get_cmd for conductance parameter
        """
        resistance_quantum = 25.818e3  # (Ohm)
        i = self.X() / self.ivgain
        # ac excitation voltage at the sample
        v_sample = self.amplitude_true()

        return (i/v_sample)*resistance_quantum

    @property
    def acfactor(self):
        return self.__acf

    @acfactor.setter
    def acfactor(self, acfactor):
        self.__acf = acfactor
        self.amplitude_true.division_value = acfactor


# Subclass the QDAC


class QDAC_T10(QDac):
    """
    A QDac with three voltage dividers
    """
    def __init__(self, name, address, config, **kwargs):
        super().__init__(name, address, **kwargs)

        # Define the named channels

        topo_channel = int(config.get('Channel Parameters',
                                      'topo bias channel'))
        topo_channel = self.channels[topo_channel-1].v

#        topo_current_num = int(config.get('Channel Parameters',
#                                        'topo current channel'))
#        topo_current = self.channels[topo_current_num-1].v

#        self.add_parameter('current_bias',
#                           label='{} {} conductance'.format(self.name, topo_current_num),
#                           # use lambda for late binding
#                           get_cmd=lambda: topo_current.get()/10E6*1E9,
#                           set_cmd=lambda value: topo_current.set(value*1E-9*10E6),
#                           unit='nA',
#                           get_parser=float)

        #sens_r_channel = int(config.get('Channel Parameters',
        #                                'right sensor bias channel'))
        #sens_r_channel = self.channels[sens_r_channel-1].v

        #sens_l_channel = int(config.get('Channel Parameters',
        #                                 'left sensor bias channel'))
        #sens_l_channel = self.channels[sens_l_channel-1].v

        self.topo_bias = VoltageDivider(topo_channel,
                                        float(config.get('Gain settings',
                                                         'dc factor topo')))
        #self.sright_bias = VoltageDivider(sens_r_channel,
        #                                  float(config.get('Gain settings',
        #                                                   'dc factor right')))
        #self.sleft_bias = VoltageDivider(sens_l_channel,
        #                                  float(config.get('Gain settings',
        #                                                    'dc factor left')))


# Subclass the DMM


class Keysight_34465A_T10(Keysight_34465A):
    """
    A Keysight DMM with an added I-V converter
    """
    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, **kwargs)

        self.iv_conv = 1

        self.add_parameter('ivconv',
                           label='Current',
                           unit='pA',
                           get_cmd=self._get_current,
                           set_cmd=None)

    def _get_current(self):
        """
        get_cmd for dmm readout of IV_TAMP parameter
        """
        return self.volt()/self.iv_conv*1E12


class ZIUHFLI_T10(ZIUHFLI):

    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, **kwargs)

        self.add_parameter('scope_avg_ch1',
                           channel=1,
                           label='',
                           parameter_class=Scope_avg)
        self.add_parameter('scope_avg_ch2',
                           channel=2,
                           label='',
                           parameter_class=Scope_avg)

        self.add_parameter('scope_full_avg_ch1',
                           channel=1,
                           parameter_class=Scope_full_avg)

        self.add_parameter('scope_full_avg_ch2',
                           channel=2,
                           parameter_class=Scope_full_avg)
