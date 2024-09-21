# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
# Driver for USB wired numeric kepad with MAX421E host interface chip.
#
from micropython import const
from usb import core
from usb.core import USBError


class Numpad:

    _INTERFACE = const(0)

    def __init__(self):
        # Variable to hold the usb.core.Device object
        self.device = None

    def find_and_configure(self):
        # Connect to a USB numeric keypad
        #
        # Returns: True = success, False = device not found or config failed
        # Exceptions: may raise usb.core.USBError or usb.core.USBTimeoutError
        #
#         device = core.find(idVendor=0x045e, idProduct=0x028e)
#         sleep(0.1)
#         if device:
#             self._configure(device)  # may raise usb.core.USBError
#             return True              # end retry loop
#         else:
#             # No gamepad was found
#             self.reset()
#             return False

    def _configure(self, device):
        # Prepare USB numpad for use (set configuration, etc)
        #
        # Exceptions: may raise usb.core.USBError or usb.core.USBTimeoutError
        try:
            # Make sure CircuitPython core is not claiming the device
            if device.is_kernel_driver_active(_INTERFACE):
                device.detach_kernel_driver(_INTERFACE)
            # Make sure that configuration is set
            device.set_configuration()
        except USBError as e:
            self.reset()
            raise e
        # All good, so save a reference to the device object
        self.device = device

    def poll(self):
        # Generator to poll numpad for key press events
        # Exceptions: may raise usb.core.USBError or usb.core.USBTimeoutError
        #
        # This generator creates an iterator that can be used with a `for`
        # loop. To read more about generators, see
        # https://peps.python.org/pep-0255/
        #
        if self.device is None:
            # Caller is trying to poll buttons when gamepad is not connected
            return
        # Caching frequently used objects saves time on dictionary name lookups
        _devread = self.device.read
        # Generator loop (note how this uses yield instead of return)
        prev = 0
        while True:
            try:
#                 # Poll gamepad endpoint to get button and joystick status bytes
#                 n = _devread(_ENDPOINT, _buf, timeout=_TIMEOUT_MS)
#                 if n < 14:
#                     # skip unexpected responses (too short to be a full report)
#                     yield prev
#                 # Only bytes 2 and 3 are interesting (ignore sticks/triggers)
#                 (buttons,) = _unpack('<H', self.buf64[2:4])
#                 prev = buttons
                yield 0
            except USBError as e:
                self.reset()
                raise e

    def device_info_str(self):
        # Return string describing gamepad device (or lack thereof)
        d = self.device
        if d is None:
            return "[Numpad not connected]"
        (v, pi, pr, m) = (d.idVendor, d.idProduct, d.product, d.manufacturer)
        if (v is None) or (pi is None):
            # Sometimes the usb.core or Max3421E will return 0000:0000 for
            # reasons that I do not understand
            return "[bad vid:pid]"
        else:
            return "Connected: %04x:%04x prod='%s' mfg='%s'" % (v, pi, pr, m)

    def reset(self):
        # Reset USB device
        self.device = None
