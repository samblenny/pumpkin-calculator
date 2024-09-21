# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
# Driver for polling USB device reports with MAX421E host interface chip.
#
from micropython import const
from time import sleep
from usb import core
from usb.core import USBError


class USBDevice:

    def __init__(self, vid, pid,
        interface=0, endpoint=0x81, timeout_ms=300, max_packet_size=8
    ):
        """Remember the config parameters for this USB device.
        CAUTION: setting timeout_ms too low can *severely* reduce the overall
        system responsiveness
        """
        # These describe properties of the USB device
        self.vid = vid
        self.pid = pid
        self.interface = interface
        self.endpoint = endpoint
        # These control the buffer size and timeout for reading USB reports
        self.timeout_ms = timeout_ms
        self.buf = bytearray(max_packet_size)
        # Variable to hold the usb.core.Device object
        self.device = None

    def find_and_configure(self):
        """Connect to a USB numeric keypad.
        Returns: True = success, False = device not found or config failed
        Exceptions: may raise usb.core.USBError or usb.core.USBTimeoutError
        """
        device = core.find(idVendor=self.vid, idProduct=self.pid)
        sleep(0.1)
        if device:
            self._configure(device)  # may raise usb.core.USBError
            return True              # end retry loop
        else:
            # No device was found
            self.reset()
            return False

    def _configure(self, device):
        """Prepare USB device for use (set configuration, etc).
        Exceptions: may raise usb.core.USBError or usb.core.USBTimeoutError
        """
        _INTERFACE = self.interface
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
        """Generator to poll device for USB reports (use this with for loop).
        Exceptions: may raise usb.core.USBError or usb.core.USBTimeoutError
        This generator creates an iterator that can be used with a `for`
        loop. For more on generators, see https://peps.python.org/pep-0255/
        """
        if self.device is None:
            # Caller is trying to poll when device is not connected
            return
        # Cache frequently used names to save typing and dictionary lookups
        _ENDPOINT = self.endpoint
        _devread = self.device.read
        _buf = self.buf
        _MS = self.timeout_ms
        # Generator loop (note how this uses yield instead of return)
        while True:
            try:
                # Poll device endpoint. This seems to always return 0 with no
                # regard for how many bytes were actually written to _buf
                _ = _devread(_ENDPOINT, _buf, timeout=_MS)
                yield _buf
            except core.USBTimeoutError as e:
                # No report available. This happens a lot. It's fine.
                yield None
            except USBError as e:
                # Other errors indicate something unexpected happened
                self.reset()
                raise e

    def device_info_str(self):
        """Return string describing the USB device (or lack thereof)"""
        d = self.device
        if d is None:
            return "[Not connected]"
        (vid, pid) = (d.idVendor, d.idProduct)
        if (vid is None) or (pid is None):
            # Sometimes the usb.core or Max3421E will return 0000:0000 for
            # reasons that I do not understand
            return "[bad vid:pid]"
        else:
            return "Connected: %04x:%04x" % (vid, pid)

    def reset(self):
        """Reset USB device."""
        self.device = None
