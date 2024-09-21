# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
"""
This is a PyUSB script for Linux to Poll for USB numeric keypad events. The
USBDevice class is reasonably general and could probably be reused with minimal
adjustments.

CAUTION: CircuitPython's usb.core.Device.read() function works differently than
PyUSB on Linux in that you must allocate your own buffer before calling it.
See:
https://docs.circuitpython.org/en/latest/shared-bindings/usb/core/index.html#usb.core.Device.read

Interesting vendor:product IDs:
  04d9:a0s1  Perixx PPD-202 numeric keypad

names available in the CircuitPython version of usb.core:
 find Device USBError USBTimeoutError
The full PyUSB version has more classes and methods, but those extra things
won't transfer over to CircuitPython, so I'm ignoring them.
"""
from struct import unpack
from sys import stdout
from time import sleep
from usb import core


class USBDevice:
    def __init__(self, vid, pid,
        interface=0, endpoint=0x81, timeout_ms=5, max_packet_size=9
    ):
        self.vid = vid
        self.pid = pid
        self.interface = interface
        self.endpoint = endpoint
        self.timeout_ms = timeout_ms
        self.max_packet_size = max_packet_size
        self.device = None

    def find_and_connect(self):
        """Attempt to connect to the USB device"""
        _INTERFACE = self.interface
        print("Finding USB device...")
        device = core.find(idVendor=self.vid, idProduct=self.pid)
        if not device:
            print("Did not find device")
            return False
        self.device = device
        print("\nFound device...")
        sleep(1)  # Wait briefly to let adapter and USB bus settle
        print(device)
        # Take USB device away from kernel if necessary
        if device.is_kernel_driver_active(_INTERFACE):
            print("detaching kernel driver")
            device.detach_kernel_driver(_INTERFACE)
        # Make sure that configuration is set (kernel might have done this)
        try:
            _ = device.get_active_configuration()
            print("configuration already set")
        except core.USBError:
            print("setting configuration")
            device.set_configuration()
        return True

    def poll(self):
        """Generator to poll for input events"""
        _ENDPOINT = self.endpoint
        _MS = self.timeout_ms
        _SIZE = self.max_packet_size
        while True:
            try:
                sleep(0.001)
                yield self.device.read(_ENDPOINT, _SIZE, timeout=_MS)
            except core.USBTimeoutError as e:
                # No report available. This happens a lot. It's fine.
                yield None

def main():
    """Establish and maintain a USB device connection"""
    while True:
        try:
            numpad = USBDevice(0x04d9, 0xa02a)
            if not numpad.find_and_connect():
                # connect failed, so try again
                sleep(0.5)
                continue
            # Connect succeeded, so start polling for input
            print("Polling for HID events..")
            for event in numpad.poll():
                if event:
                    print(event)
        except core.USBError as e:
            print(e, "errno:", e.errno)
            raise e


main()


"""
DEVICE ID 04d9:a02a on Bus 001 Address 002 =================
 bLength                :   0x12 (18 bytes)
 bDescriptorType        :    0x1 Device
 bcdUSB                 :  0x110 USB 1.1
 bDeviceClass           :    0x0 Specified at interface
 bDeviceSubClass        :    0x0
 bDeviceProtocol        :    0x0
 bMaxPacketSize0        :    0x8 (8 bytes)
 idVendor               : 0x04d9
 idProduct              : 0xa02a
 bcdDevice              :  0x300 Device 3.0
 ...
 bNumConfigurations     :    0x1
  CONFIGURATION 1: 100 mA ==================================
   bLength              :    0x9 (9 bytes)
   bDescriptorType      :    0x2 Configuration
   wTotalLength         :   0x22 (34 bytes)
   bNumInterfaces       :    0x1
   bConfigurationValue  :    0x1
   iConfiguration       :    0x0
   bmAttributes         :   0xa0 Bus Powered, Remote Wakeup
   bMaxPower            :   0x32 (100 mA)
    INTERFACE 0: Human Interface Device ====================
     bLength            :    0x9 (9 bytes)
     bDescriptorType    :    0x4 Interface
     bInterfaceNumber   :    0x0
     bAlternateSetting  :    0x0
     bNumEndpoints      :    0x1
     bInterfaceClass    :    0x3 Human Interface Device
     bInterfaceSubClass :    0x1
     bInterfaceProtocol :    0x1
     iInterface         :    0x0
      ENDPOINT 0x81: Interrupt IN ==========================
       bLength          :    0x7 (7 bytes)
       bDescriptorType  :    0x5 Endpoint
       bEndpointAddress :   0x81 IN
       bmAttributes     :    0x3 Interrupt
       wMaxPacketSize   :    0x8 (8 bytes)
       bInterval        :    0xa
"""
