# Yokogawa.py driver for Yokogawa GS820 multi channel source measure unit
# Hannes Rotzinger, hannes.rotzinger@kit.edu 2010
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from instrument import Instrument
from qkit import visa
import logging
import numpy as np
import time
from distutils.version import LooseVersion


class Yokogawa(Instrument):
    '''
    This is the driver for the Yokogawa GS820 Multi Channel Source Measure Unit
    
    Usage:
    Initialize with
    <name> = qkit.instruments.create('<name>', 'Yokogawa', address='<GBIP address>', reset=<bool>)
    '''

    def __init__(self, name, address, reset=False):
        '''
        Initializes the Yokogawa_GS820, and communicates with the wrapper.
        
        Input:
            name (string)    : name of the instrument
            address (string) : GPIB address
            reset (bool)     : resets to default values, default=False
        '''
        # Start VISA communication
        logging.info(__name__ + ' : Initializing instrument Yokogawa_GS820')
        Instrument.__init__(self, name, tags=['physical'])
        self._address = address
        self._visainstrument = visa.instrument(self._address)

        # Set termination characters (necessary for Ethernet communication)
        if LooseVersion(visa.__version__) < LooseVersion("1.5.0"):  # pyvisa 1.4
            self._visainstrument.term_chars = ''
        else:  # pyvisa 1.5
            self._visainstrument.read_termination = ''
            self._visainstrument.write_termination = ''
        
        # Global constants
        self._measurement_modes = {0: '2-wire', 1: '4-wire'}
        self._IV_modes = {0: 'curr', 1: 'volt'}
        self._IV_units = {0: 'A', 1: 'V'}
        self._bias_status_register = [('EOS1', 'CH1 End of Sweep'),
                                      ('RDY1', 'CH1 Ready for Sweep'),
                                      ('LL01', 'CH1 Low Limiting'),
                                      ('LHI1', 'CH1 High Limiting'),
                                      ('TRP1', 'CH1 Tripped'),
                                      ('EMR1', 'CH1 Emergency (Temperature/Current over)'),
                                      ('', ''),
                                      ('', ''),
                                      ('EOS2', 'CH2 End of Sweep'),
                                      ('RDY2', 'CH2 Ready for Sweep'),
                                      ('LL02', 'CH2 Low Limiting'),
                                      ('LHI2', 'CH2 High Limiting'),
                                      ('TRP2', 'CH2 Tripped'),
                                      ('EMR2', 'CH2 Emergency (Temperature/Current over)'),
                                      ('ILC', 'Inter Locking'),
                                      ('SSB', 'Start Sampling Error')]
        self._sense_status_register = [('EOM1', 'CH1 End of Measure'),
                                       ('', ''),
                                       ('CLO1', 'CH1 Compare result is Low'),
                                       ('CHI1', 'CH1 Compare result is High'),
                                       ('', ''),
                                       ('OVR1', 'CH1 Over Range'),
                                       ('', ''),
                                       ('', ''),
                                       ('EOM2', 'CH2 End of Measure'),
                                       ('', ''),
                                       ('CLO2', 'CH2 Compare result is Low'),
                                       ('CHI2', 'CH1 Compare result is High'),
                                       ('', ''),
                                       ('OVR2', 'CH2 Over Range'),
                                       ('EOT', 'End of Trace'),
                                       ('TSE', 'Trigger Sampling Error')]
        self.err_msg = {-101: '''Invalid_character: Check whether invalid characters such as $ or & are used in the command header or parameters.''',
                        -102: '''Syntax_error: Check that the syntax is correct.''',
                        -103: '''Invalid separator: Check the use of the separator (comma).''',
                        -106: '''Parameter not allowed: Check the command and the number of parameters.''',
                        -107: '''Missing parameter: Check the command and the number of parameters.''',
                        -112: '''Program mnemonic too long: Check the command mnemonic.''',
                        -113: '''Undefined header: Check the command mnemonic.''',
                        -121: '''Invalid character in number: Check that the notation of the numeric parameter is correct (for example, binary notation should not contain characters other than 0 and 1)''',
                        -122: '''Header suffix out of range: Check whether the numeric suffix of the command header is correct.''',
                        -123: '''Exponent too large: Check whether the exponent is within the range of -127 to 127.''',
                        -124: '''Too many digits: Check that the number of digits in the value does not exceed 255.''',
                        -128: '''Numeric data not allowed: Check the parameter format.''',
                        -131: '''Invalid suffix: Check the unit that can be used for the parameter.''',
                        -138: '''Suffix not allowed: Check the parameter format.''',
                        -141: '''Invalid character data: Check the character data that can be used for the parameter.''',
                        -148: '''Character data not allowed: Check the command and parameter format.''',
                        -150: '''String data error: Check that the closing quotation mark (" or ') for a string is available.''',
                        -151: '''Invalid string data: Check that the string parameter is in the correct format.''',
                        -158: '''String data not allowed: Check the command and parameter format.''',
                        -161: '''Invalid block data: Check that the block data is in the correct format.''',
                        -168: '''Block data not allowed: Check the command and parameter format.''',
                        -178: '''Expression data not allowed: Check the command and parameter format.''',
                        -222: '''Data out of range: Check the selectable range of the parameter. If the command can use MINimum and MAXimum as its parameter, the range can also be queried.''',
                        -256: '''Filename not found: Check that the file exists. You can also use the CATalog? command to query the list of files.''',
                        -285: '''Program syntax error: Check that the sweep pattern file is in the correct format.''',
                        -350: '''Queue overflow: Read the error using :SYSTem:ERRor? or clear the error queue using *CLS.''',
                        -361: '''Parity error: Check that the communication settings on the GS820 and PC match. If the settings are correct, check the cable, and lower the baud rate.''',
                        -362: '''Framing error: Check that the communication settings on the GS820 and PC match. If the settings are correct, check the cable, and lower the baud rate.''',
                        -363: '''Input buffer overrun: Set the handshaking to a setting other than OFF. Lower the baud rate.''',
                        -410: '''Query INTERRUPTED: Check transmission/reception procedure.''',
                        -420: '''Query UNTERMINATED: Check transmission/reception procedure.''',
                        -430: '''Query DEADLOCK: Keep the length of a program message less than or equal to 64 KB.''',
                        +101: '''Too complex expression: Keep the total number of constants, variables, and operators in a MATH definition less than or equal to 256.''',
                        +102: '''Math file syntax error: Check that the syntax of the MATH definition file is correct.''',
                        +103: '''Too large file error: Keep MATH definition files less than 4 KB in size.''',
                        +104: '''Illegal file error: Download the file for updating the system firmware again.''',
                        +105: '''No slave SMU found: Check that the connection between the master and slave units is correct.''',
                        +200: '''Sweep stopped because of the setting change: Stop the sweep operation before changing the settings.''',
                        +202: '''Interlocking: Release the interlock, and then turn the output ON.''',
                        +203: '''Cannot relay on in hardware abnormal: Check whether the temperature inside the case is okay.''',
                        +204: '''Hardware input abnormal error: Connect a load within the specifications.''',
                        +205: '''Analog busy: Change the settings after the calibration or self-test is completed.''',
                        +206: '''Low battery: Request to have the battery replaced, because the time stamp when creating files will not be correct.''',
                        +207: '''Power line frequency measure failure: Directly set the line frequency.''',
                        +304: '''Cannot change setting in auto measure function: If you want to change the measurement function, select a measurement mode other than auto function.'''}
        
        # initial variables
        self._sweep_mode = 1 # IV-mode

        # Reset
        if reset:
            self.reset()
        else:
            self.get_all()

    def _write(self, cmd):
        '''
        Sends a visa command <cmd>
        
        Input:
            msg (str)
        Output:
            None
        '''
        self._visainstrument.write(cmd)
        #self._wait_for_OPC()
        return

    def _ask(self, msg):
        '''
        Sends a visa command <msg> and returns the read answer <ans>
        
        Input:
            msg (str)
        Output:
            ans (str)
        '''
        if '?' in msg:
            return self._visainstrument.query(msg).rstrip()
        else:
            return self._visainstrument.query('{:s}?'.format(msg)).rstrip()
        #self._wait_for_OPC()

    def set_measurement_mode(self, val, channel=1):
        '''
        Sets measurement mode (wiring system) of channel <channel> to <val>
        
        Input:
            channel (int) : 1 (default) | 2
            val (int)     : 0 (2-wire) | 1 (4-wire)
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SENSe:REMote 1|0|ON|OFF
        try:
            logging.debug(__name__ + ' : set measurement mode of channel {:d} to {:d}'.format(channel, val))
            self._write(':chan{:d}:sens:rem {:d}'.format(channel, val))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set measurement mode of channel {:d} to {:f}'.format(channel, val))

    def get_measurement_mode(self, channel=1):
        '''
        Gets measurement mode (wiring system) of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (int)     : 0 (2-wire) | 1 (4-wire)
        '''
        # Corresponding Command: [:CHANnel<n>]:SENSe:REMote 1|0|ON|OFF
        try:
            logging.debug(__name__ + ': get measurement mode of channel {:d}'.format(channel))
            return int(self._ask(':chan{:d}:sens:rem'.format(channel)))
        except ValueError:
            logging.error(__name__ + ': Measurement mode of channel {:d} not specified:'.format(channel))

    def set_sync(self, val):
        '''
        Sets the interchannel synchronization to <val>
        (The first channel is always the "master", the second the "slave")
        
        Input:
            val (bool) : 0 (off) | 1 (on)
        Output:
            None
        '''
        # Corresponding Command: :SYNChronize:CHANnel 1|0|ON|OFF
        try:
            logging.debug(__name__ + ': Set the channels in synchronized mode to {:d}'.format(val))
            self._write(':sync:chan {:d}'.format(val))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set the interchannel synchronization to {:f}'.format(val))

    def get_sync(self):
        '''
        Gets the interchannel synchronization
        
        Input:
            None
        Output:
            val (bool) : 0 (off) | 1 (on)
        '''
        # Corresponding Command: :SYNChronize:CHANnel 1|0|ON|OFF
        try:
            logging.debug(__name__ + ': Get the channels in synchronized mode')
            return bool(int(self._ask(':sync:chan')))
        except ValueError:
            logging.error(__name__ + ': Interchannel synchronization not specified:')

    def set_bias_mode(self, mode, channel=1):
        '''
        Sets bias mode of channel <channel> to <mode> regime
        
        Input:
            mode (int)    : 0 (current) | 1 (voltage)
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce:FUNCtion VOLTage|CURRent
        try:
            logging.debug(__name__ + ': Set bias mode of channel {:d} to {:d}'.format(channel, mode))
            self._write(':chan{:d}:sour:func {:s}'.format(channel, self._IV_modes[mode]))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set bias mode of channel {:d} to {:d}'.format(channel, mode))

    def get_bias_mode(self, channel=1):
        '''
        Gets bias mode of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            mode (int)    : 0 (current) | 1 (voltage)
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce:FUNCtion VOLTage|CURRent
        try:
            logging.debug(__name__ + ': get bias mode of channel {:d}'.format(channel))
            return int(self._IV_modes.keys()[self._IV_modes.values().index(self._ask(':chan{:d}:sour:func'.format(channel)).lower())])
        except ValueError:
            logging.error(__name__ + ': Bias mode of channel {:d} not specified:'.format(channel))

    def set_sense_mode(self, mode, channel=1):
        '''
        Sets sense mode of channel <channel> to <mode> regime
        
        Input:
            mode (int)    : 0 (current) | 1 (voltage)
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SENSe:FUNCtion VOLTage|CURRent
        try:
            logging.debug(__name__ + ': Set sense mode of channel {:d} to {:d}'.format(channel, mode))
            self._write(':chan{:d}:sens:func {:s}'.format(channel, self._IV_modes[mode]))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set sense mode of channel {:d} to {:d}'.format(channel, mode))

    def get_sense_mode(self, channel=1):
        '''
        Gets sense mode <mode> of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            mode (str)    : 'volt' | 'curr'
        '''
        # Corresponding Command: [:CHANnel<n>]:SENSe:FUNCtion VOLTage|CURRent
        try:
            logging.debug(__name__ + ': Get sense mode of channel {:d}'.format(channel))
            return int(self._IV_modes.keys()[self._IV_modes.values().index(self._ask(':chan{:d}:sens:func'.format(channel)).lower())])
        except ValueError:
            logging.error(__name__ + ': Sense mode of channel {:d} not specified:'.format(channel))

    def set_bias_range(self, val, channel=1):
        '''
        Sets bias range of channel <channel> to <val>
        
        Input:
            val (float)   : -1 (auto) | 200mV | 2V | 7V | 18V | 200nA | 2uA | 20uA | 200uA | 2mA | 20mA | 200mA | 1 A | 3A
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce[:VOLTage]:RANGe <voltage>|MINimum|MAXimum|UP|DOWN 
        # Corresponding Command: [:CHANnel<n>]:SOURce[:CURRent]:RANGe <current>|MINimum|MAXimum|UP|DOWN 
        try:
            logging.debug(__name__ + ': Set bias voltage range of channel {:d} to {:f}'.format(channel, val))
            if val == -1:
                self._write(':chan{:d}:sour:rang:auto 1'.format(channel))
            else:
                self._write(':chan{:d}:sour:rang {:f}'.format(channel, val))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set bias range of channel {:d} to {:f}'.format(channel, val))

    def get_bias_range(self, channel=1):
        '''
        Gets bias range for the current mode.
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (float)   : 200mV | 2V | 7V | 18V | 200nA | 2uA | 20uA | 200uA | 2mA | 20mA | 200mA | 1 A | 3A
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce[:VOLTage]:RANGe <voltage>|MINimum|MAXimum|UP|DOWN 
        # Corresponding Command: [:CHANnel<n>]:SOURce[:CURRent]:RANGe <current>|MINimum|MAXimum|UP|DOWN 
        try:
            logging.debug(__name__ + ': Get bias voltage range of channel {:d}'.format(channel))
            return float(self._ask(':chan{:d}:sour:rang'.format(channel)))
        except ValueError:
            logging.error(__name__ + ': Bias range of channel {:d} not specified:'.format(channel))

    def set_sense_range(self, val, channel=1):
        '''
        Sets sense range of channel <channel> to <val>
        
        Input:
            val (float)   : -1 (auto) | 200mV | 2V | 7V | 18V | 200nA | 2uA | 20uA | 200uA | 2mA | 20mA | 200mA | 1 A | 3A
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SENSe[:VOLTage]:RANGe <voltage>|MINimum|MAXimum|UP|DOWN
        # Corresponding Command: [:CHANnel<n>]:SENSe[:CURRent]:RANGe <current>|MINimum|MAXimum|UP|DOWN
        try:
            logging.debug(__name__ + ': Set sense range of channel {:d} to {:f}'.format(channel, val))
            if val == -1:
                self._write(':chan{:d}:sens:rang:auto 1'.format(channel))
            else:
                self._write(':chan{:d}:sens:rang {:f}'.format(channel, val))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set sense range of channel {:d} to {:f}'.format(channel, val))

    def get_sense_range(self, channel=1):
        '''
        Gets sense range for the current mode.
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (float)   : 200mV | 2V | 7V | 18V | 200nA | 2uA | 20uA | 200uA | 2mA | 20mA | 200mA | 1 A | 3A
        '''
        # Corresponding Command: [:CHANnel<n>]:SENSe[:VOLTage]:RANGe <voltage>|MINimum|MAXimum|UP|DOWN
        # Corresponding Command: [:CHANnel<n>]:SENSe[:CURRent]:RANGe <current>|MINimum|MAXimum|UP|DOWN
        try:
            logging.debug(__name__ + ': Get sense range of channel {:d}'.format(channel))
            return float(self._ask(':chan{:d}:sens:rang'.format(channel)))
        except ValueError:
            logging.error(__name__ + ': Sense range of channel {:d} not specified:'.format(channel))

    def set_bias_trigger(self, mode, channel=1, **val):
        '''
        Sets bias trigger mode of channel <channel> to <mode> and value <val>
        If <mode> is 'timer' it can be set to <time>
        
        Input:
            mode (str)    : ext (external) | aux (auxiliary) | tim1 (timer1) | tim2 (timer2) | sens (sense)
            channel (int) : 1 (default) | 2
            **val         : 100us <= time (float) <= 3600.000000s
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce:TRIGger EXTernal|AUXiliary|TIMer1|TIMer2|SENSe
        # Corresponding Command: :TRIGger:TIMer1 <time>|MINimum|MAXimum
        try:
            logging.debug(__name__ + ': Set bias trigger of channel {:d} to {:s}'.format(channel, mode))
            self._write(':chan{:d}:sour:trig {:s}'.format(channel, mode))
            if 'time' in val:
                self._write(':trig:{:s} {:f}'.format(mode, val.get('time', 50e-3)))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set bias trigger of channel {:d} to {:s}'.format(channel, mode))

    def get_bias_trigger(self, channel=1):
        '''
        Gets bias trigger of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            trigger (str) : ext (external) | aux (auxiliary) | tim1 (timer1) | tim2 (timer2) | sens (sense)
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce:TRIGger EXTernal|AUXiliary|TIMer1|TIMer2|SENSe
        try:
            logging.debug(__name__ + ': Get bias trigger of channel {:d}'.format(channel))
            return str(self._ask(':chan{:d}:sour:trig'.format(channel)).lower())
        except ValueError:
            logging.error(__name__ + ': Bias trigger of channel {:d} not specified:'.format(channel))

    def set_sense_trigger(self, mode, channel=1, **val):
        '''
        Sets sense trigger mode of channel <channel> to <trigger> and value <val>
        If <mode> is 'timer' it can be set to <time>
        
        Input:
            mode (str)    : ext (external) | aux (auxiliary) | tim1 (timer1) | tim2 (timer2) | sens (sense)
            channel (int) : 1 (default) | 2
            **val         : 100us <= time (float) <= 3600.000000s
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SENSe:TRIGger EXTernal|AUXiliary|TIMer1|TIMer2|SENSe
        # Corresponding Command: :TRIGger:TIMer1 <time>|MINimum|MAXimum
        try:
            logging.debug(__name__ + ': Set sense trigger of channel {:d} to {:s}'.format(channel, mode))
            self._write(':chan{:d}:sens:trig {:s}'.format(channel, mode))
            if 'time' in val:
                self._write(':trig:{:s} {:f}'.format(mode, val.get('time', 50e-3)))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set sense trigger of channel {:d} to {:s}'.format(channel, mode))

    def get_sense_trigger(self, channel=1):
        '''
        Gets sense trigger of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            trigger (str) : ext (external) | aux (auxiliary) | tim1 (timer1) | tim2 (timer2) | sens (sense)
        '''
        # Corresponding Command: [:CHANnel<n>]:SENSe:TRIGger EXTernal|AUXiliary|TIMer1|TIMer2|SENSe
        try:
            logging.debug(__name__ + ': Get sense trigger of channel {:d}'.format(channel))
            return str(self._ask(':chan{:d}:sens:trig'.format(channel)).lower())
        except ValueError:
            logging.error(__name__ + ': Sense trigger of channel {:d} not specified:'.format(channel))

    def set_bias_delay(self, val, channel=1):
        '''
        Sets bias delay of channel <channel> to <val>
        
        Input:
            val (float)   : 15us <= delay <= 3600s
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce:DELay <time>|MINimum|MAXimum
        try:
            logging.debug(__name__ + ': Set bias delay of channel {:d} to {:f}'.format(channel, val))
            self._write(':chan{:d}:sour:del {:f}'.format(channel, val))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set bias delay of channel {:d} to {:f}'.format(channel, val))

    def get_bias_delay(self, channel=1):
        '''
        Gets bias delay of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (float)
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce:DELay <time>|MINimum|MAXimum
        try:
            logging.debug(__name__ + ': Get bias delay of channel {:d}'.format(channel))
            return float(self._ask(':chan{:d}:sour:del'.format(channel)))
        except ValueError:
            logging.error(__name__ + ': Bias delay of channel {:d} not specified:'.format(channel))

    def set_sense_delay(self, val, channel=1):
        '''
        Sets sense delay of channel <channel> to <val>
        
        Input:
            val (float)   : 15us <= delay <= 3600s
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce:DELay <time>|MINimum|MAXimum
        try:
            logging.debug(__name__ + ': Set sense delay of channel {:d} to {:f}'.format(channel, val))
            self._write(':chan{:d}:sens:del {:f}'.format(channel, val))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set sense delay of channel {:d} to {:f}'.format(channel, val))

    def get_sense_delay(self, channel=1):
        '''
        Gets sense delay of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (float)
        '''
        # Corresponding Command: [:CHANnel<n>]:SENSe:DELay <time>|MINimum|MAXimum
        try:
            logging.debug(__name__ + ': Get sense delay of channel {:d}'.format(channel))
            return float(self._ask(':chan{:d}:sens:del'.format(channel)))
        except ValueError:
            logging.error(__name__ + ': Sense delay of channel {:d} not specified:'.format(channel))

    def set_sense_average(self, val, channel=1):
        '''
        Sets sense average of channel <channel> to <val>.
        If <val> is less than 1 average status is turned off, but the set value remains.
        
        Input:
            val (int)
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SENSe:AVERage[:STATe] 1|0|ON|OFF
        # Corresponding Command: [:CHANnel<n>]:SENSe:AVERage:COUNt <integer>|MINimum|MAXimum
        try:
            logging.debug(__name__ + ': Set sense average of channel {:d} to {:d}'.format(channel, val))
            status = not(.5*(1-np.sign(val-1)))  # equals Heaviside(1-<val>) --> turns on for <val> >= 2
            self._write(':chan{:d}:sens:aver:stat {:d}'.format(channel, status))
            if status:
                self._write(':chan{:d}:sens:aver:coun {:d}'.format(channel, val))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set sense average of channel {:d} to {:d}'.format(channel, val))

    def get_sense_average(self, channel=1):
        '''
        Gets sense average of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            status (bool)
            val (int)
        '''
        # Corresponding Command: [:CHANnel<n>]:SENSe:AVERage[:STATe] 1|0|ON|OFF
        # Corresponding Command: [:CHANnel<n>]:SENSe:AVERage:COUNt <integer>|MINimum|MAXimum
        try:
            logging.debug(__name__ + ': Get sense average of channel {:d}'.format(channel))
            status = bool(int(self._ask(':chan{:d}:sens:aver:stat'.format(channel))))
            val = int(self._ask(':chan{:d}:sens:aver:coun'.format(channel)))
            return status, val
        except ValueError:
            logging.error(__name__ + ': Sense average of channel {:d} not specified:'.format(channel))

    def set_plc(self, plc):
        '''
        Sets power line cycle (PLC) to <plc>
        
        Input:
            plc (int) : -1 (auto) | 50 | 60
        Output:
            None
        '''
        # Corresponding Command: :SYSTem:LFRequency 50|60
        # Corresponding Command: :SYSTem:LFRequency:AUTO 1|0|ON|OFF
        try:
            logging.debug(__name__ + ': Set PLC to {:s}'.format(str(plc)))
            cmd = {-1: ':auto 1', 50: ' 50', 60: ' 60'}
            self._write('syst:lfr{:s}'.format(cmd.get(int(plc), cmd[-1])))
        except ValueError:
            logging.error(__name__ + ': PLC not specified:')

    def get_plc(self):
        '''
        Gets power line cycle (PLC)
        
        Input:
            None
        Output:
            plc (int) : 50 | 60
        '''
        # Corresponding Command: :SYSTem:LFRequency 50|60
        # Corresponding Command: :SYSTem:LFRequency:AUTO 1|0|ON|OFF
        try:
            logging.debug(__name__ + ': Get PLC')
            return int(self._ask('syst:lfr'))
        except ValueError:
            logging.error(__name__ + ': PLC not specified:')

    def set_sense_nplc(self, val, channel=1):
        '''
        Sets sense nplc (number of power line cycle) of channel <channel> with the <val>-fold of one power line cycle
        
        Input:
            channel (int) : 1 (default) | 2
            val (int)     : [1, 25]
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SENSe:NPLC <real number>|MINimum|MAXimum
        try:
            logging.debug(__name__ + ': Set sense nplc of channel {:d} to {:2.0f} PLC'.format(channel, val))
            self._write(':chan{:d}:sens:nplc {:2.0f}'.format(channel, val))
        except ValueError:
            logging.error(__name__ + ': Invalid input: cannot set sense nplc of channel {:d} to {:2.0f}'.format(channel, val))

    def get_sense_nplc(self, channel=1):
        '''
        Gets sense nplc (number of power line cycle) of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (int)
        '''
        # Corresponding Command: [:CHANnel<n>]:SENSe:NPLC <real number>|MINimum|MAXimum
        try:
            logging.debug(__name__ + ': Get sense nplc of channel {:d}'.format(channel))
            return float(self._ask(':chan{:d}:sens:nplc'.format(channel)))
        except ValueError:
            logging.error(__name__ + ': Number of PLC of channel {:d} not specified:'.format(channel))

    def set_sense_autozero(self, val, channel=1):
        '''
        Sets autozero of channel <channel> to <val>.
        
        Input:
            val (int): 0 (off) | 1 (on)
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SENSe:ZERo:AUTO 1|0|ON|OFF
        # Corresponding Command: [:CHANnel<n>]:SENSe:ZERo:EXECute
        ### FIXME: Is execute necessary?
        try:
            logging.debug(__name__ + ': Set autozero of channel {:d} to {:d}'.format(channel, val))
            self._write(':chan{:d}:sens:zero:auto {:d}'.format(channel, val))
            #self._write(':chan{:d}:sens:zero:exec'.format(channel))
        except ValueError as e:
            logging.error(__name__ + ': Invalid input: cannot set autozero of channel {:d} to {:d}: {:s}'.format(channel, val, e))

    def get_sense_autozero(self, channel=1):
        '''
        Gets autozero of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (int)
        '''
        # Corresponding Command: [:CHANnel<n>]:SENSe:ZERo:AUTO 1|0|ON|OFF
        try:
            logging.debug(__name__ + ': Get autozero of channel {:d}'.format(channel))
            return bool(self._ask(':chan{:d}:sens:zero:auto'.format(channel)))
        except ValueError as e:
            logging.error(__name__ + ': Autozero of channel {:d} not specified: {:s}'.format(channel), e)

    def set_status(self, status, channel=1):
        '''
        Sets output status of channel <channel> to <status>
        
        Input:
            status (bool) : False (off) | True (on)
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:OUTput:STATus 1|0|ON|OFF
        try:
            logging.debug(__name__ + ': Set output status of channel {:d} to {!r}'.format(channel, status))
            self._write(':chan{:d}:outp:stat {:d}'.format(channel, status))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set output status of channel {:d} to {!r}'.format(channel, status))

    def get_status(self, channel=1):
        '''
        Gets output status of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            status (bool) : False (off) | True (on)
        '''
        # Corresponding Command: [:CHANnel<n>]:OUTput:STATus 1|0|ON|OFF
        try:
            logging.debug(__name__ + ': Get output status of channel {:d}'.format(channel))
            return bool(int(self._ask(':chan{:d}:outp:stat'.format(channel))))
        except ValueError:
            logging.error(__name__ + ': Status of channel {:d} not specified:'.format(channel))

#    def set_stati(self, status):
#        '''
#        Sets output status of both channels to <status>
#        
#        Input:
#            status (int)  : 0 (off) | 1 (on) | 2 (high Z)
#        Output:
#            None
#        '''
#        for channel in range(1, 3):
#            self.set_status(status=status, channel=channel)
#
#    def get_stati(self):
#        '''
#        Gets output status of both channels
#        
#        Input:
#            None
#        Output:
#            status (int)  : 0 (off) | 1 (on) | 2 (high Z)
#        '''
#        stati = []
#        for channel in range(1, 3):
#            stati.append(self.get_status(channel=channel))
#        return stati

    def set_bias_value(self, val, channel=1):
        '''
        Sets bias value of channel <channel> to value >val>
        
        Input:
            val (float)
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce[:VOLTage]:LEVel <voltage>|MINimum|MAXimum
        # Corresponding Command: [:CHANnel<n>]:SOURce[:CURRent]:LEVel <current>|MINimum|MAXimum
        try:
            logging.debug(__name__ + ' : Set bias value of channel {:d} to {:f}'.format(channel, val))
            ### FIXME: digits
            self._write(':chan{:d}:sour:lev {:11.9f}'.format(channel, val))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set bias value of channel {:d} to {:f}'.format(channel, val))

    def get_bias_value(self, channel=1):
        '''
        Gets bias value of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (float)
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce[:VOLTage]:LEVel <voltage>|MINimum|MAXimum
        # Corresponding Command: [:CHANnel<n>]:SOURce[:CURRent]:LEVel <current>|MINimum|MAXimum
        try:
            logging.debug(__name__ + ' : Get bias value of channel {:d}'.format(channel))
            return float(self._ask(':chan{:d}:sour:lev'.format(channel)))
        except ValueError:
            logging.error(__name__ + ': Cannot get bias value of channel {:d}:'.format(channel))

    def get_sense_value(self, channel=1):
        '''
        Gets sense value of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (float)
        '''
        # Corresponding Command: [:CHANnel<n>]:MEASure?
        # Corresponding Command: [:CHANnel<n>]:FETCh? [DUAL]
        try:
            logging.debug(__name__ + ' : Get sense value of channel {:d}'.format(channel))
            # return float(self._ask(':chan{:d}:meas'.format(channel)))
            return float(self._ask(':chan{:d}:fetc'.format(channel)))
        except ValueError:
            logging.error(__name__ + ': Cannot get sense value of channel {:d}:'.format(channel))

    def set_voltage(self, val, channel=1):
        '''
        Sets voltage value of channel <channel> to <val>
        
        Input:
            val (float)
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        if not self.get_bias_mode(channel): # 0 (current bias)
            return self.set_bias_value(val, channel)
        elif self.get_bias_mode(channel):  # 1 (voltage bias)
            logging.error(__name__ + ': Cannot set voltage value of channel {:d}: in the current bias'.format(channel))

    def get_voltage(self, channel=1):
        '''
        Gets voltage value of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (float)
        '''
        if self.get_bias_mode(channel):  # 1 (voltage bias)
            return self.get_bias_value(channel)
        elif self.get_sense_mode(channel):  # 1 (voltage sense)
            return self.get_sense_value(channel)
        else:
            logging.error(__name__ + ': Cannot get voltage value of channel {:d}: neihter bias nor sense in voltage mode'.format(channel))

    def set_current(self, val, channel=1):
        '''
        Sets current value of channel <channel> to <val>
        
        Input:
            val (float)
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        if not self.get_bias_mode(channel): # 0 (current bias)
            return self.set_bias_value(val, channel)
        elif self.get_bias_mode(channel): # 1 (voltage bias)
            logging.error(__name__ + ': Cannot set current value of channel {:d}: in the voltage bias'.format(channel))

    def get_current(self, channel=1):
        '''
        Gets current value of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (float)
        '''
        if not self.get_bias_mode(channel): # 0 (current bias)
            return self.get_bias_value(channel)
        elif not self.get_sense_mode(channel): # 0 (current sense)
            return self.get_sense_value(channel)
        else:
            logging.error(__name__ + ': Cannot get current value of channel {:d}: neihter bias nor sense in current mode'.format(channel))

    def ramp_bias(self, stop, step, step_time=0.1, channel=1):
        '''
        Ramps bias value of channel <channel> from recent value to <stop>
        
        Input:
            stop (float)
            step (float)
            step_time (float)
            channel (int)     : 1 | 2 (default)
        Output:
            None
        '''
        start = self.get_bias_value(channel=channel)
        if stop < start:
            step = -step
        for val in np.arange(start, stop, step)+step:
            self.set_bias_value(val, channel=channel)
            time.sleep(step_time)

    def ramp_voltage(self, stop, step, step_time=0.1, channel=1):
        '''
        Ramps voltage of channel <channel> from recent value to <stop> according to bias_mode
        
        Input:
            stop (float)
            step (float)
            step_time (float)
            channel (int)     : 1 | 2 (default)
        Output:
            None
        '''
        if self.get_bias(channel=channel):  # 1 (voltage bias)
            return self.ramp_bias(stop=stop, step=step, step_time=step_time, channel=channel)
        elif not self.get_bias(channel=channel):  # 0 (current bias)
            logging.error(__name__ + ': Cannot set voltage value of channel {:d}: in the current bias'.format(channel))
            return

    def ramp_current(self, stop, step, step_time=0.1, channel=1):
        '''
        Ramps current of channel <channel> from recent value to <stop> according to bias_mode
        
        Input:
            stop (float)
            step (float)
            step_time (float)
            channel (int)     : 1 | 2 (default)
        Output:
            None
        '''
        if not self.get_bias(channel=channel): # 0 (current bias)
            return self.ramp_bias(stop=stop, step=step, step_time=step_time, channel=channel)
        elif self.get_bias(channel=channel): # 1 (voltage bias)
            logging.error(__name__ + ': Cannot ramp current value of channel {:d}: in the voltage bias'.format(channel))
            return

    def set_sweep_mode(self, mode=1, **kwargs):
        '''
        Sets an internal variable to decide weather voltage is both applied and measured, current is applied and voltage is measured (default) or voltage is applied and current is measured.
        VV-mode needs two different channels (bias channel <channel_bias> and sense channel <channel_sense>), IV-mode and VI-mode only one (<channel>).

        Input:
            mode (int) : 0 (VV-mode) | 1 (IV-mode) (default) | 2 (VI-mode)
            **kwargs   : channel_bias (int)  : 1 (default) | 2 for VV-mode
                         channel_sense (int) : 1 | 2 (default) for VV-mode
                         channel (int)       : 1 (default) | 2 for IV-mode or VI-mode
        Output:
            None
        '''
        self._sweep_mode = mode

    def get_sweep_mode(self):
        '''
        Gets an internal variable to decide weather voltage is both applied and measured, current is applied and voltage is measured or voltage is applied and current is measured.

        Input:
            None
        Output:
            mode (int) : 0 (VV mode) | 1 (IV mode) | 2 (VI-mode)
        '''
        return self._sweep_mode

    def _set_sweep_start(self, val, channel=1):
        '''
        Sets sweep start value of channel <channel> to <val>
        
        Input:
            val (float)
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce[:VOLTage]:SWEep:STARt <voltage>|MINiumum|MAXimum
        try:
            logging.debug(__name__ + ': Set sweep start of channel {:d} to {:f}'.format(channel, val))
            # self._write(':chan{:d}:sour:swe:star {:f}'.format(channel, val))
            self._write(':chan{:d}:sour:{:s}:swe:star {:f}'.format(channel, self._IV_modes[self.get_bias_mode(channel)], val))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set sweep start of channel {:d} to {:f}'.format(channel, val))

    def _get_sweep_start(self, channel=1):
        '''
        Gets sweep start value of channel <channel>
        
        Input:
            channel (int): 1 | 2
        Output:
            val (float)
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce[:VOLTage]:SWEep:STARt <voltage>|MINiumum|MAXimum
        try:
            logging.debug(__name__ + ': Get sweep start of channel {:d}'.format(channel))
            # return float(self._ask(':chan{:d}:sour:swe:star'.format(channel)))
            return float(self._ask(':chan{:d}:sour:{:s}:swe:star'.format(channel, self._IV_modes[self.get_bias_mode(channel)])))
        except ValueError:
            logging.error(__name__ + ': Sweep start of channel {:d} not specified:'.format(channel))

    def _set_sweep_stop(self, val, channel=1):
        '''
        Sets sweep stop value of channel <channel> to <val>
        
        Input:
            val (float)
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce[:VOLTage]:SWEep:STARt <voltage>|MINiumum|MAXimum
        try:
            logging.debug(__name__ + ': Set sweep stop of channel {:d} to {:f}'.format(channel, val))
            # self._write(':chan{:d}:sour:swe:stop {:f}'.format(channel, val))
            self._write(':chan{:d}:sour:{:s}:swe:stop {:f}'.format(channel, self._IV_modes[self.get_bias_mode(channel)], val))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set sweep stop of channel {:d} to {:f}'.format(channel, val))

    def _get_sweep_stop(self, channel=1):
        '''
        Gets sweep stop value of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (float)
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce[:VOLTage]:SWEep:STARt <voltage>|MINiumum|MAXimum
        try:
            logging.debug(__name__ + ': Get sweep stop of channel {:d}'.format(channel))
            # return float(self._ask(':chan{:d}:sour:swe:stop'.format(channel)))
            return float(self._ask(':chan{:d}:sour:{:s}:swe:stop'.format(channel, self._IV_modes[self.get_bias_mode(channel)])))
        except ValueError:
            logging.error(__name__ + ': Sweep stop of channel {:d} not specified:'.format(channel))

    def _set_sweep_step(self, val, channel=1):
        '''
        Sets sweep step value of channel <channel> to <val>
        
        Input:
            val (float)
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce[:VOLTage]:SWEep:STARt <voltage>|MINiumum|MAXimum
        try:
            logging.debug(__name__ + ': Set sweep step of channel {:d} to {:f}'.format(channel, val))
            self._write(':chan{:d}:sour:{:s}:swe:step {:f}'.format(channel, self._IV_modes[self.get_bias_mode(channel)], val))
            # self._write(':chan{:d}:sour:swe:step {:f}'.format(channel, val))
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot set sweep step of channel {:d} to {:f}'.format(channel, val))

    def _get_sweep_step(self, channel=1):
        '''
        Gets sweep step value of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (float)
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce[:VOLTage]:SWEep:STARt <voltage>|MINiumum|MAXimum
        try:
            logging.debug(__name__ + ': Get sweep step of channel {:d}'.format(channel))
            return float(self._ask(':chan{:d}:sour:{:s}:swe:step'.format(channel, self._IV_modes[self.get_bias_mode(channel)])))
            # return float(self._ask(':chan{:d}:sour:swe:step'.format(channel)))
        except ValueError:
            logging.error(__name__ + ': Sweep step of channel {:d} not specified:'.format(channel))

    def _get_sweep_nop(self, channel=1):
        '''
        Gets sweep nop of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (int)
        '''
        try:
            logging.debug(__name__ + ': Get sweep nop of channel {:d}'.format(channel))
            return int((self._get_sweep_stop(channel=channel) - self._get_sweep_start(channel=channel)) / self._get_sweep_step(channel=channel) + 1)
        except ValueError:
            logging.error(__name__ + ': Sweep nop of channel {:d} not specified:'.format(channel))

    def set_sweep_parameters(self, sweep, sweep_mode=None, **kwargs):
        '''
        Sets sweep parameters <sweep> and prepares instrument for VV-mode, IV-mode (default) or VI-mode.
        VV-mode needs two different channels (bias channel <channel_bias> and sense channel <channel_sense>), IV-mode and VI-mode only one (<channel>).
        
        Input:
            sweep (list(float)) : start, stop, step
            sweep_mode (int)    : None <self._sweep_mode> (default) | 0 (VV-mode) | 1 (IV-mode) | 2 (VI-mode)
            **kwargs            : channel_bias (int)  : 1 (default) | 2 for VV-mode
                                  channel_sense (int) : 1 | 2 (default) for VV-mode
                                  channel (int)       : 1 (default) | 2 for IV-mode or VI-mode
        Output:
            None
        '''
        # Corresponding Command: [:CHANnel<n>]:SOURce:MODE FIXed|SWEep|LIST|SINGle
        # Corresponding Command: [:CHANnel<n>]:SWEep:TRIGger EXTernal|AUXiliary|TIMer1|TIMer2|SENSe
        # Corresponding Command: :TRACe:POINts <integer>|MINimum|MAXimum
        # Corresponding Command: :TRACe:CHANnel<n>:DATA:FORMat ASCii|BINary
        # Corresponding Command: :TRACe:BINary:REPLy BINary|ASCii
        # Corresponding Command: :TRACe[:STATe] 1|0|ON|OFF
        if sweep_mode is not None: self._sweep_mode = sweep_mode
        if not self._sweep_mode: # 0 (VV-mode)
            self._channel_bias  = kwargs.get('channel_bias', 1)
            self._channel_sense = kwargs.get('channel_sense', 2)
            self.set_sync(val=True)
        elif self._sweep_mode in [1,2]: # 1 (IV-mode) | 2 (VI-mode)
            self._channel = kwargs.get('channel', 1)
            self._channel_bias  = kwargs.get('channel_bias', self._channel)
            self._channel_sense = kwargs.get('channel_sense', self._channel)
        try:
            self._set_sweep_start(val=float(sweep[0]), channel=self._channel_bias)
            self._set_sweep_stop(val=float(sweep[1]), channel=self._channel_bias)
            self._set_sweep_step(val=np.abs(float(sweep[2])), channel=self._channel_bias)
            self.set_bias_trigger(mode='sens', channel=self._channel_bias)
            self.set_sense_trigger(mode='sour', channel=self._channel_sense)
            self.set_bias_value(val=self._get_sweep_start(channel=self._channel_bias), channel=self._channel_bias)
            self._write(':chan{:d}:sour:mode swe'.format(self._channel_bias))
            self._write(':chan{:d}:swe:trig ext'.format(self._channel_bias))
            self._write(':trac:poin max')  # alternative: self._write(':trac:poin {:d}'.format(self._get_sweep_nop(channel=self._channel_bias)))
            self._write(':trac:chan{:d}:data:form asc'.format(self._channel_sense))
            self._write(':trac:bin:repl asc')
        except:
            logging.error(__name__ + ': Cannot set sweep parameters of channel {:d} and {:d}.'.format(self._channel_bias, self._channel_sense))
        return

    def get_tracedata(self, sweep_mode=None, **kwargs):
        '''
        Starts bias sweep and gets trace data in the VV-mode, IV-mode (default) or VI-mode.
        VV-mode needs two different channels (bias channel <channel_bias> and sense channel <channel_sense>), IV-mode and VI-mode only one (<channel>).
        
        Input:
            sweep_mode (int) : None <self._sweep_mode> (default) | 0 (VV-mode) | 1 (IV-mode) | 2 (VI-mode)
            **kwargs         : channel_bias (int)  : 1 (default) | 2 for VV-mode
                               channel_sense (int) : 1 | 2 (default) for VV-mode
                               channel (int)       : 1 (default) | 2 for IV-mode or VI-mode
        Output:
            bias_values (numpy.array(float))
            sense_values (numpy.array(float))
        '''
        # Corresponding Command: [:CHANnel<n>]:INITiate [DUAL]
        # Corresponding Command: :STARt
        # Corresponding Command: :TRACe[:STATe] 1|0|ON|OFF
        # Corresponding Command: :TRACe:CHANnel<n>:DATA:READ? [TM|DO|DI|SF|SL|MF|ML|LC|HC|CP]
        if sweep_mode is not None: self._sweep_mode = sweep_mode
        if not self._sweep_mode: # 0 (VV-mode)
            self._channel_bias  = kwargs.get('channel_bias', 1)
            self._channel_sense = kwargs.get('channel_sense', 2)
        elif self._sweep_mode in [1,2]: # 1 (IV-mode) | 2 (VI-mode)
            self._channel = kwargs.get('channel', 1)
            self._channel_bias  = kwargs.get('channel_bias', self._channel)
            self._channel_sense = kwargs.get('channel_sense', self._channel)
        try:
            self._write(':chan{:d}:init'.format(self._channel_bias))
            self._wait_for_ready_for_sweep(channel=self._channel_bias)
            self._write(':trac:stat 1')
            self._wait_for_OPC()
            time.sleep(100e-6)
            self._write(':star')
            self._wait_for_end_of_sweep(channel=self._channel_bias)
            time.sleep(self.get_sense_delay(channel=self._channel_sense))
            self._wait_for_end_of_measure(channel=self._channel_sense)
            self._write(':trac:stat 0')
            bias_values = np.fromstring(string=self._ask('trac:chan{:d}:data:read? sl'.format(self._channel_bias)), dtype=float, sep=',')
            sense_values = np.fromstring(string=self._ask('trac:chan{:d}:data:read? ml'.format(self._channel_bias)), dtype=float, sep=',')
            return bias_values, sense_values
        except:
            logging.error(__name__ + ': Cannot take sweep data of channel {:d} and {:d}.'.format(self._channel_bias, self._channel_sense))

    def take_IV(self, sweep, sweep_mode=None, **kwargs):
        '''
        Takes IV curve with sweep parameters <sweep> in the VV-mode or IV-mode.
        VV-mode needs two different channels (bias channel <channel> and sense channel <channel2>), IV-mode and VI-mode only one (<channel>).
        
        Input:
            sweep (list(float)) : start, stop, step
            sweep_mode (int)    : 0 (VV-mode) | 1 (IV-mode) | 2 (VI-mode)
            **kwargs            : channel_bias (int)  : 1 (default) | 2 for VV-mode
                                  channel_sense (int) : 1 | 2 (default) for VV-mode
                                  channel (int)       : 1 (default) | 2 for IV-mode or VI-mode
        Output:
            bias_values (numpy.array(float))
            sense_values (numpy.array(float))
        '''
        self.set_sweep_parameters(sweep=sweep, sweep_mode=sweep_mode, **kwargs)
        return self.get_tracedata(sweep_mode=sweep_mode, **kwargs)

    def get_bias_status_register(self):
        '''
        Gets the entire bias status register
        
        Input:
            None
        Output:
            status_register (bool):
                0:  CH1 End of Sweep
                1:  CH1 Ready for Sweep
                2:  CH1 Low Limiting
                3:  CH1 High Limiting
                4:  CH1 Tripped
                5:  CH1 Emergency (Temperature/Current over)
                6:  ---
                7:  ---
                8:  CH2 End of Sweep
                9:  CH2 Ready for Sweep
                10: CH2 Low Limiting
                11: CH2 High Limiting
                12: CH2 Tripped
                13: CH2 Emergency (Temperature/Current over)
                14: Inter Locking
                15: Start Sampling Error
        '''
        # Corresponding Command: :STATus:SOURce:CONDition?
        try:
            logging.debug(__name__ + ': Get bias status register')
            BSR = int(self._ask(':stat:sour:cond'))
            ans = []
            for i in range(16):
                # ans.append(2**i == (BSR) & 2**i)
                ans.append(bool((BSR >> i) % 2))
            return ans
        except ValueError:
            logging.error(__name__ + ': Bias status register not specified:')

    def print_bias_status_register(self):
        '''
        Prints the entire bias status register including explanation
        
        Input:
            None
        Output
            None
        '''
        bsr = self.get_bias_status_register()
        msg = [('\n\t{:s}:\t{!r}\t({:s})'.format(sb[0], bsr[i], sb[1])) for i, sb in
               enumerate(self._bias_status_register) if sb != ('', '')]
        print 'Bias status register:' + ''.join(msg)

    def get_sense_status_register(self):
        '''
        Gets the entire sense status register
        
        Input:
            None
        Output:
            status_register (bool):
                0:  CH1 End of Measure
                1:  ---
                2:  CH1 Compare result is Low
                3:  CH1 Compare result is High
                4:  ---
                5:  CH1 Over Range
                6:  ---
                7:  ---
                8:  CH2 End of Measure
                9:  ---
                10: CH2 Compare result is Low
                11: CH2 Compare result is High
                12: ---
                13: CH2 Over Range
                14: End of Trace
                15: Trigger Sampling Error
        '''
        # Corresponding Command: :STATus:SENSe:CONDition?
        try:
            logging.debug(__name__ + ': Get sense status register')
            SSR = int(self._ask(':stat:sens:cond'))
            ans = []
            for i in range(16):
                # ans.append(2**i == (SSR) & 2**i)
                ans.append(bool((SSR >> i) % 2))
            return ans
        except ValueError:
            logging.error(__name__ + ': Sense status register not specified:')

    def print_sense_status_register(self):
        '''
        Prints the entire sense status register including explanation
        
        Input:
            None
        Output
            None
        '''
        ssr = self.get_sense_status_register()
        msg = [('\n\t{:s}:\t{!r}\t({:s})'.format(sb[0], ssr[i], sb[1])) for i, sb in
               enumerate(self._sense_status_register) if sb != ('', '')]
        print 'Sense status register:' + ''.join(msg)

    def is_end_of_sweep(self, channel=1):
        '''
        Gets event of bias status register entry "End for Sweep" of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (bool)    : True | False
        '''
        # Corresponding Command: :STATus:SOURce:EVENt?
        try:
            logging.debug(__name__ + ': Get bias status register event "End of Sweep" of channel {:d}'.format(channel))
            return bool((int(self._ask(':stat:sour:even')) >> (0+8*(channel-1)))%2)
        except ValueError:
            logging.error(__name__ + ': Status register event "End of Sweep" of channel {:d} not specified:'.format(channel))

    def _wait_for_end_of_sweep(self, channel=1):
        '''
        Waits until the event of status register entry "End for Sweep" of channel <channel> occurs
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        while not (self.is_end_of_sweep(channel=channel)):
            time.sleep(100e-3)

    def is_ready_for_sweep(self, channel=1):
        '''
        Gets condition of bias status register entry "Ready for Sweep" of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (bool)    : True | False
        '''
        # Corresponding Command: :STATus:SOURce:CONDition?
        try:
            logging.debug(__name__ + ': Get bias status register event "Ready of Sweep" of channel {:d}'.format(channel))
            return bool((int(self._ask(':stat:sour:cond')) >> (1+8*(channel-1)))%2)
        except ValueError:
            logging.error(__name__ + ': Status register condition "Ready for Sweep" of channel {:d} not specified:'.format(channel))

    def _wait_for_ready_for_sweep(self, channel=1):
        '''
        Waits until the condition of status register entry "Ready for Sweep" of channel <channel> occurs
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        while not (self.is_ready_for_sweep(channel=channel)):
            time.sleep(100e-3)

    def is_end_of_measure(self, channel=1):
        '''
        Gets condition of sense status register entry "End of Measure" of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (bool)    : True | False
        '''
        # Corresponding Command: :STATus:SENSe:CONDition?
        try:
            logging.debug(__name__ + ': Get sense status register event "End of Measure" of channel {:d}'.format(channel))
            return bool((int(self._ask(':stat:sens:cond')) >> (0+8*(channel-1)))%2)
        except ValueError:
            logging.error(__name__ + ': Status register event "End of Measure" of channel {:d} not specified:'.format(channel))

    def _wait_for_end_of_measure(self, channel=1):
        '''
        Waits until the condition of sense register entry "End for Measure" of channel <channel> occurs
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        while not (self.is_end_of_measure(channel=channel)):
            time.sleep(100e-3)

    def is_end_of_trace(self, channel=1):
        '''
        Gets condition of sense status register entry "End of Trace" of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            val (bool)    : True | False
        '''
        # Corresponding Command: :STATus:SENSe:CONDition?
        try:
            logging.debug(__name__ + ': Get sense status register event "End of Trace" of channel {:d}'.format(channel))
            return bool((int(self._ask(':stat:sens:cond'))>>14)%2)
        except ValueError:
            logging.error(__name__ + ': Status register event "End of Trace" of channel {:d} not specified:'.format(channel))

    def _wait_for_end_of_trace(self, channel=1):
        '''
        Waits until the condition of sense register entry "End for Trace" of channel <channel> occurs
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        while not (self.is_end_of_trace(channel=channel)):
            time.sleep(100e-3)

    def is_OPC(self):
        '''
        Gets condition of status register entry "Operation complete"
        
        Input:
            None
        Output:
            val (bool) : True | False
        '''
        # Corresponding Command: *OPC
        try:
            logging.debug(__name__ + ': Get status register condition "Operation complete"')
            return bool(int(self._ask('*OPC')))
        except ValueError:
            logging.error(__name__ + ': Status register condition "Operation complete" not specified:')

    def _wait_for_OPC(self):
        '''
        Waits until the event of register entry "Operatiom Complete" of occurs
        
        Input:
            None
        Output:
            None
        '''
        while not (self.is_OPC()):
            time.sleep(1e-3)
        return

    def set_defaults(self, sweep_mode=None, **kwargs):
        '''
        Sets default settings for different sweep modes.
        VV-mode needs two different channels (bias channel <channel_bias> and sense channel <channel_sense>), IV-mode and VI-mode only one (<channel>).
        
        Input:
            sweep_mode (int): None <self._sweep_mode> (default) | 0 (VV-mode) | 1 (IV-mode) | 2 (VI-mode)
            **kwargs        : channel_bias (int)  : 1 (default) | 2 for VV-mode
                              channel_sense (int) : 1 | 2 (default) for VV-mode
                              channel (int)       : 1 (default) | 2 for IV-mode or VI-mode
        Output:
            None
        '''
        # dict of defaults values: defaults[<sweep_mode>][<channel>][<parameter>][<value>]
        defaults = {0:{'channel_bias':{'measurement_mode':0,
                                       'bias_mode':1,
                                       'sense_mode':1,
                                       'bias_range':-1,
                                       'sense_range':-1,
                                       'bias_delay':200e-6,
                                       'sense_delay':15e-6,
                                       'sense_nplc':1,
                                       'sense_average':1,
                                       'sense_autozero':0},
                       'channel_sense':{'measurement_mode':0,
                                       'bias_mode':0,
                                       'sense_mode':1,
                                       'bias_range':-1,
                                       'sense_range':-1,
                                       'bias_delay':200e-6,
                                       'sense_delay':15e-6,
                                       'sense_nplc':1,
                                       'sense_average':1,
                                       'sense_autozero':0}},
                    1:{'channel':{'measurement_mode':1,
                                  'bias_mode':0,
                                  'sense_mode':1,
                                  'bias_trigger':'''str('sens')''',
                                  'sense_trigger':'''str('sour')''',
                                  'bias_range':-1,
                                  'sense_range':-1,
                                  'bias_delay':200e-6,
                                  'sense_delay':15e-6,
                                  'sense_nplc':1,
                                  'sense_average':1,
                                  'sense_autozero':0}},
                    2:{'channel':{'measurement_mode':1,
                                  'bias_mode':1,
                                  'sense_mode':0,
                                  'bias_trigger':'''str('sens')''',
                                  'sense_trigger':'''str('sour')''',
                                  'bias_range':-1,
                                  'sense_range':-1,
                                  'bias_delay':200e-6,
                                  'sense_delay':15e-6,
                                  'sense_nplc':1,
                                  'sense_average':1,
                                  'sense_autozero':0}}}
        self.reset()
        # beeper off
        self._write(':syst:beep 0')
        # distiguish different sweep modes
        if sweep_mode is not None: self._sweep_mode = sweep_mode
        if self._sweep_mode == 0:  # VV-mode
            self._channel_bias  = kwargs.get('channel_bias', 1)
            self._channel_sense = kwargs.get('channel_sense', 2)
            channels = {'channel_bias':self._channel_bias, 'channel_sense':self._channel_sense}
        elif self._sweep_mode in [1,2]:  # IV-mode, VI-mode
            self._channel  = kwargs.get('channel', 1)
            channels = {'channel':self._channel}
        # set values
        for key_channel, val_channel in channels.items():
            for key_parameter, val_parameter in defaults[self._sweep_mode][key_channel].items():
                #print('self.set_{:s}({!s}, channel={:d})'.format(key_parameter, val_parameter, val_channel))
                eval('self.set_{:s}({!s}, channel={:d})'.format(key_parameter, val_parameter, val_channel))

    def get_all(self, channel=1):
        '''
        Prints all settings of channel <channel>
        
        Input:
            channel (int) : 1 (default) | 2
        Output:
            None
        '''
        print('synchronization    = {!r}'.format(self.get_sync()))
        print('measurement mode   = {:s}'.format(self._measurement_modes[self.get_measurement_mode(channel=channel)]))
        print('bias mode          = {:s}'.format(self._IV_modes[self.get_bias_mode(channel=channel)]))
        print('sense mode         = {:s}'.format(self._IV_modes[self.get_sense_mode(channel=channel)]))
        print('bias range         = {:1.0e}{:s}'.format(self.get_bias_range(channel=channel), self._IV_units[self.get_bias_mode(channel=channel)]))
        print('sense range        = {:1.0e}{:s}'.format(self.get_sense_range(channel=channel), self._IV_units[self.get_sense_mode(channel=channel)]))
        print('bias delay         = {:1.3e}s'.format(self.get_bias_delay(channel=channel)))
        print('sense delay        = {:1.3e}s'.format(self.get_sense_delay(channel=channel)))
        print('sense average      = {:d}'.format(self.get_sense_average(channel=channel)[1]))
        print('plc                = {:f}Hz'.format(self.get_plc()))
        print('sense nplc         = {:f}'.format(self.get_sense_nplc(channel=channel)))
        print('sense autozero     = {!r}'.format(self.get_sense_autozero(channel=channel)))
        print('status             = {!r}'.format(self.get_status(channel=channel)))
        print('bias value         = {:f}{:s}'.format(self.get_bias_value(channel=channel), self._IV_units[self.get_bias_mode(channel=channel)]))
        print('sense value        = {:f}{:s}'.format(self.get_sense_value(channel=channel), self._IV_units[self.get_sense_mode(channel=channel)]))
        print('sweep start        = {:f}{:s}'.format(self._get_sweep_start(channel=channel), self._IV_units[self.get_bias_mode(channel=channel)]))
        print('sweep stop         = {:f}{:s}'.format(self._get_sweep_stop(channel=channel), self._IV_units[self.get_bias_mode(channel=channel)]))
        print('sweep step         = {:f}{:s}'.format(self._get_sweep_step(channel=channel), self._IV_units[self.get_bias_mode(channel=channel)]))
        print('sweep nop          = {:d}'.format(self._get_sweep_nop(channel=channel)))
        for err in self.get_error(): print('error              = {:d}\t{:s}'.format(err[0], err[1]))
        self.print_bias_status_register()
        self.print_sense_status_register()

    def reset(self):
        '''
        Resets the instrument to factory settings
        
        Input:
            None
        Output:
            None
        '''
        # Corresponding Command: *RST
        try:
            logging.debug(__name__ + ': resetting instrument')
            self._write('*RST')
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot reset')

    def get_error(self):
        '''
        Gets error of instrument
        
        Input:
            None
        Output:
            error (str)
        '''
        # Corresponding Command: :SYSTem:ERRor?
        try:
            logging.debug(__name__ + ': Get errors')
            err = [self._ask(':syst:err').split(',', 1)]
            while err[-1] != ['0', '"No error"']:
                err.append(self._ask(':syst:err').split(',', 1))
            if len(err) > 1: err = err[:-1]
            err = [[int(e[0]), str(e[1][1:-1])] for e in err]
            return err
        except ValueError:
            logging.error(__name__ + ': Error not specified:')
    
    def _raise_error(self):
        errors = self.get_error()
        if errors[0][0] is 0: # no error
            msg = __name__ + ' raises the following errors:'
            for err in errors:
                msg += '\n' + self.err_msg[err]
            raise ValueError(msg)
        else:
            return

    def clear_error(self):
        '''
        Clears error of instrument
        
        Input:
            None
        Output:
            None
        '''
        # Corresponding Command: *CLS
        try:
            logging.debug(__name__ + ': Clear error')
            self._write('*CLS')
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot clear error')

    def close(self):
        '''
        Closes the VISA-instrument to disconnect the instrument
        
        Input:
            None
        Output:
            None
        '''
        try:
            logging.debug(__name__ + ': Close VISA-instrument')
            self._visainstrument.close()
        except AttributeError:
            logging.error(__name__ + ': Invalid input: cannot close VISA-instrument')

    def get_parameters(self):
        '''
        Gets a parameter list <parlist> of measurement specific setting parameters.
        Needed for .set-file in 'write_additional_files', if qt parameters are not used.
        
        Input:
            None
        Output:
            parlist (dict): Parameter as key, corresponding channels as value
        '''
        parlist = {'measurement_mode': [1, 2],
                   'sync': [None],
                   'bias_mode': [1, 2],
                   'sense_mode': [1, 2],
                   'bias_range': [1, 2],
                   'sense_range': [1, 2],
                   'bias_trigger': [1, 2],
                   'sense_trigger': [1, 2],
                   'bias_delay': [1, 2],
                   'sense_delay': [1, 2],
                   'sense_average': [1, 2],
                   'plc': [None],
                   'sense_nplc': [1, 2],
                   'sense_autozero': [1,2],
                   'status': [1, 2]}
        return parlist

    def get(self, param, **kwargs):
        '''
        Gets the current parameter <param> by evaluation 'get_'+<param> and corresponding channel if needed
        In combination with <self.get_parameters> above.
        
        Input:
            param (str): parameter to be got
            **kwargs   : channels (list[int]): certain channel {1, 2} for channel specific parameter or None if no channel (global parameter)
        Output:
            parlist (dict): Parameter as key, corresponding channels as value
        '''
        channels = kwargs.get('channels')
        if channels != [None]:
            return tuple([eval('self.get_{:s}(channel={!s})'.format(param, channel)) for channel in channels])
        else:
            return eval('self.get_{:s}()'.format(param))

