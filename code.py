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
from sys import stdout
from time import sleep
from usb.core import USBError

import adafruit_imageload
from adafruit_st7789 import ST7789
from usbdevice import USBDevice


# Feather TFT display size is 240x135 px
_TFT_W = const(240)
_TFT_H = const(135)

# USB HID Scancodes for numeric keypad. For the big list, refer to
# chapter 10, "Keyboard/Keypad Page (0x07)" of the USB HID Usages and
# Descriptions pdf at https://usb.org/sites/default/files/hut1_5.pdf
_ErrRollover = const(0x01)
_Bksp = const(0x2a)
_Tab  = const(0x2b)
_Div  = const(0x54)
_Mul  = const(0x55)
_Sub  = const(0x56)
_Add  = const(0x57)
_Entr = const(0x58)
_1    = const(0x59)
_2    = const(0x5a)
_3    = const(0x5b)
_4    = const(0x5c)
_5    = const(0x5d)
_6    = const(0x5e)
_7    = const(0x5f)
_8    = const(0x60)
_9    = const(0x61)
_0    = const(0x62)
_Dot  = const(0x63)


class Pumpkin:
    """This class manages a TileGrid and 2x zoom group for the pumpkins."""

    def __init__(self):
        gc.collect()
        (bmp, pal) = adafruit_imageload.load(
            "pumpkin-sprites.png", bitmap=Bitmap, palette=Palette)
        gc.collect()
        # Make a Group with TileGrids with top left corner at (x, y)
        _W = const(_TFT_W // (8 * 2))  # 15
        _H = const(_TFT_H // (8 * 2))  #  8
        tg = TileGrid(
            bmp, pixel_shader=pal, width=_W, height=_H,
            tile_width=8, tile_height=8, x=0, y=0, default_tile=12)
        gc.collect()
        g = Group(scale=2)
        g.append(tg)
        tilemap = (
            (12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12,),  # 0: blank
            (12, 12, 12, 14, 15, 12, 12, 12, 12, 12, 14, 15, 12, 12, 12,),  # 1: stems / 'ERR'
            (12, 22, 23, 24, 25, 26, 27, 12, 22, 23, 24, 25, 26, 27, 12,),  # 2: stem/top
            (12, 32, 33, 34, 35, 36, 37, 38, 32, 33, 34, 35, 36, 37, 38,),  # 3: top + 1
            # x=4:   0   1   2   3   4           +   -   *   /   .
            (12, 62, 63, 64, 65, 66, 67, 68,102,103,104,105,106,107,108,),  # 4: 0..4, '+'..'.'
            # x=5:   5   6   7   8   9         Tab Bksp Entr
            (12, 72, 73, 74, 75, 76, 77, 78,112,113,114,115,116,117,118,),  # 5: 5..9, 'tab'..'Entr'

            (12,122,123,124,125,126,127,128,122,123,124,125,126,127,128,),  # bottom - 1
            (12, 12,133,134,135,136,137, 12, 12,133,134,135,136,137, 12,),  # bottom
        )
        for (y, row) in enumerate(tilemap):
            for (x, sprite) in enumerate(row):
                tg[x, y] = sprite
        gc.collect()
        # This dictionary helps with swapping light/dark sprites for keys that
        # are being pressed. The format of each item except for _Entr is:
        #    key_name: (y, x, light_sprite, dark_sprite)
        # The Entr key gets two sprites
        lightdarkmap = {
            _ErrRollover: ((1, 6, 12, 16), (1, 7, 12, 17)),

            _0:   (4,  2,  63, 43),   _1: (4,  3,  64, 44),   _2: (4,  4,  65, 45),
            _3:   (4,  5,  66, 46),   _4: (4,  6,  67, 47),
            _Add: (4,  9, 103, 83), _Sub: (4, 10, 104, 84), _Mul: (4, 11, 105, 85),
            _Div: (4, 12, 106, 86), _Dot: (4, 13, 107, 87),

            _5:    ( 5,  2,  73, 53),    _6: (5,  3,  74, 54), _7: (5, 4, 75, 55),
            _8:    ( 5,  5,  76, 56),    _9: (5,  6,  77, 57),
            _Tab:  ( 5,  9, 113, 93), _Bksp: (5, 10, 114, 94),
            _Entr: ((5, 11, 115, 95), (5, 12, 116, 96)),
        }
        gc.collect()
        self.lightdarkmap = lightdarkmap
        self.tg = tg
        self.group = g

    def set_lightdark(self, scancodes):
        """Set key indicator sprites from the scancodes list to dark."""
        _ldmap = self.lightdarkmap
        _tg = self.tg
        for (k, v) in _ldmap.items():
            if (k == _Entr) or (k == _ErrRollover):
                # Enter key has 2 sprites
                (y, x, light, dark) = v[0]
                s = dark if k in scancodes else light
                if _tg[x, y] != s:
                    _tg[x, y] = s
                (y, x, light, dark) = v[1]
                s = dark if k in scancodes else light
                if _tg[x, y] != s:
                    _tg[x, y] = s
            else:
                # All the other keys have 1 sprite
                (y, x, light, dark) = v
                s = dark if k in scancodes else light
                if _tg[x, y] != s:
                    _tg[x, y] = s


def main():
    release_displays()

    # Cache frequently used callables to save time on dictionary name lookups
    _collect = gc.collect
    (_VID, _PID) = (const(0x04d9), const(0xa02a))  # Perixx PPD-202 numpad
    _FINDING_DEVICE = 'Finding USB device %04x:%04x...' % (_VID, _PID)
    _wr = stdout.write

    # Initialize ST7789 display with native display size of 240x135px.
    _collect()
    spi = SPI()
    bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS)
    display = ST7789(bus, rotation=270, width=_TFT_W, height=_TFT_H, rowstart=40,
        colstart=53, auto_refresh=False)
    _collect()

    # Add the TileGrids to the display's root group
    pumpkin = Pumpkin()
    display.root_group = pumpkin.group
    display.refresh()

    # Initialize MAX3421E USB host chip which is needed by usb.core.
    # The link between usb.core and Max3421E happens by way of invisible
    # magic in the CircuitPython core, kinda like with displayio displays.
    print("Initializing USB host port...")
    usbHost = Max3421E(spi, chip_select=D10, irq=D9)
    sleep(0.1)

    # These help to look up key names from scancodes
    _NAMES = {
        _ErrRollover: 'ErrRollover',
        _Bksp: 'Bksp',
        _Tab: 'Tab',
        _Div: '/',
        _Mul: '*',
        _Sub: '-',
        _Add: '+',
        _Entr: 'Entr',
        _1: '1',
        _2: '2',
        _3: '3',
        _4: '4',
        _5: '5',
        _6: '6',
        _7: '7',
        _8: '8',
        _9: '9',
        _0: '0',
        _Dot: '.',
    }

    # MAIN EVENT LOOP
    numpad = USBDevice(_VID, _PID, max_packet_size=8)
    print(_FINDING_DEVICE)
    while True:
        _collect()
        try:
            # Attempt to connect to USB numpad
            if numpad.find_and_configure():
                sleep(0.5)
                print(numpad.device_info_str())
                # INNER LOOP: poll for keyscan reports
                print("Polling for USB reports...")
                for report in numpad.poll():
                    if not (report is None):
                        # Notes on contents of bytes_ (the HID report)
                        # - codes[0] is 0 (proably modifier bitfield)
                        # - codes[1] is 0 (may be reserved?)
                        # - codes[2:8] have key scancodes
                        # CAUTION: the report[2:8] here hides modifiers!
                        codes = [int(b) for b in report[2:8]]
                        hex_codes = ' '.join(['%02x' % c for c in codes])
                        names = ' '.join([_NAMES[k] for k in codes if k != 0])
                        print(hex_codes, "--", names)
                        # Update the display sprites
                        pumpkin.set_lightdark(codes)
                        display.refresh()
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
