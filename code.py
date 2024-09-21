# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
# Hardware:
# - Adafruit ESP32-S3 TFT Feather - 4MB Flash, 2MB PSRAM (#5483)
# - Adafruit USB Host FeatherWing with MAX3421E (#5858)
# - USB numeric keypad (Perixx PPD-202 or similar)
#
# Perixx PPD-202:
# - vid:pid = 04d9:a02a
# - HID reports can be read from default config: interface 0: endpoint 0x81
#
# Pinouts:
# | TFT feather | USB Host | ST7789 TFT |
# | ----------- | -------- | ---------- |
# |  SCK        |  SCK     |            |
# |  MOSI       |  MOSI    |            |
# |  MISO       |  MISO    |            |
# |  D9         |  IRQ     |            |
# |  D10        |  CS      |            |
# |  TFT_CS     |          |  CS        |
# |  TFT_DC     |          |  DC        |
#
# Related Documentation:
# - https://learn.adafruit.com/adafruit-esp32-s3-tft-feather
# - https://learn.adafruit.com/adafruit-1-14-240x135-color-tft-breakout
# - https://learn.adafruit.com/adafruit-usb-host-featherwing-with-max3421e
#
from board import D9, D10, SPI, TFT_CS, TFT_DC
from digitalio import DigitalInOut, Direction
from displayio import Bitmap, Group, Palette, TileGrid, release_displays
from fourwire import FourWire
import gc
from max3421e import Max3421E
from micropython import const
from struct import unpack
from time import sleep
from usb.core import USBError

from adafruit_st7789 import ST7789
from usbdevice import USBDevice


def main():
    release_displays()
    _collect = gc.collect

    # USB HID Scancodes for numeric keypad. For the big list, refer to
    # chapter 10, "Keyboard/Keypad Page (0x07)" of the USB HID Usages and
    # Descriptions pdf at https://usb.org/sites/default/files/hut1_5.pdf
    SCANCODES = {
        0x01: 'ErrRollOver',
        0x2a: 'Bksp', 0x2b: 'Tab',
        0x49: 'Ins',  0x4a: 'Home',  0x4b: 'PgUp', 0x4c: 'Del', 0x4d: 'End',
        0x4e: 'PgDn', 0x4f: 'Right', 0x50: 'Left', 0x51: 'Down', 0x52: 'Up',
        0x54: '/', 0x55: '*', 0x56: '-', 0x57: '+', 0x58: 'Enter',
        0x59: '1', 0x5a: '2', 0x5b: '3', 0x5c: '4', 0x5d: '5',
        0x5e: '6', 0x5f: '7', 0x60: '8', 0x61: '9', 0x62: '0',
        0x63: '.',
    }

    # Cache frequently used callables to save time on dictionary name lookups
    _unpack = unpack
    (_VID, _PID) = (const(0x04d9), const(0xa02a))  # Perixx PPD-202 numpad
    _FINDING_DEVICE = 'Finding USB device %04x:%04x...' % (_VID, _PID)

    # Initialize ST7789 display with native display size of 240x135px.
    TFT_W = const(240)
    TFT_H = const(135)
    _collect()
    spi = SPI()
    bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS)
    display = ST7789(bus, rotation=270, width=TFT_W, height=TFT_H, rowstart=40,
        colstart=53, auto_refresh=False)
    _collect()

    # Add the TileGrids to the display's root group
    #grp = Group(scale=1)
    #grp.append()
    #grp.append()
    display.root_group = None
    display.refresh()

    # Initialize MAX3421E USB host chip which is needed by usb.core.
    # The link between usb.core and Max3421E happens by way of invisible
    # magic in the CircuitPython core, kinda like with displayio displays.
    print("Initializing USB host port...")
    usbHost = Max3421E(spi, chip_select=D10, irq=D9)
    sleep(0.1)

    # MAIN EVENT LOOP
    numpad = USBDevice(_VID, _PID, max_packet_size=8)
    print(_FINDING_DEVICE)
    while True:
        _collect()
        try:
            # Attempt to connect to USB numpad
            if numpad.find_and_configure():
                sleep(1)
                print(numpad.device_info_str())
                # INNER LOOP: poll for keyscan reports
                print("Polling for USB reports...")
                for report in numpad.poll():
                    if not (report is None):
                        (n, bytes_) = report
                        # Notes on contents of bytes_ (the HID report)
                        # - codes[0] is 0 (proably modifier bitfield)
                        # - codes[1] is 0 (may be reserved?)
                        # - codes[2:8] have key scancodes
                        # CAUTION: the bytes_[2:8] here hides modifiers!
                        codes = [int(b) for b in bytes_[2:8]]
                        hex_codes = ['%02x' % c for c in codes]
                        # Look up names for the scancodes, allowing for
                        # possibility of numlock may be either on or off
                        names = [SCANCODES[n] for n in codes if n != 0]
                        print(' '.join(hex_codes), "--", ' '.join(names))
                # If inner loop stopped, device connection was lost
                print("USB device disconnected")
                print(_FINDING_DEVICE)
            else:
                # No connection yet, so sleep briefly then try again
                sleep(0.2)
        except USBError as e:
            # This might mean gamepad was unplugged, or maybe some other
            # low-level USB thing happened which this driver does not yet
            # know how to deal with. So, log the error and keep going
            print(e)
            print("USB Error")
            print(_FINDING_DEVICE)


main()
