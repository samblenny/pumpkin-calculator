# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
# Hardware:
# - Adafruit ESP32-S3 TFT Feather - 4MB Flash, 2MB PSRAM (#5483)
# - Adafruit USB Host FeatherWing with MAX3421E (#5858)
# - USB numeric keypad (Perixx PPD-202 or similar)
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
from time import sleep
from usb.core import USBError

from adafruit_st7789 import ST7789
from numpad import Numpad


def main():
#    release_displays()

    # Cache frequently used callables to save time on dictionary name lookups
    _collect = gc.collect

    # Initialize ST7789 display with native display size of 240x135px.
    TFT_W = const(240)
    TFT_H = const(135)
    _collect()
#     spi = SPI()
#     bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS)
#     display = ST7789(bus, rotation=270, width=TFT_W, height=TFT_H, rowstart=40,
#         colstart=53, auto_refresh=False)
#     _collect()

    # Add the TileGrids to the display's root group
    #grp = Group(scale=1)
    #grp.append()
    #grp.append()
    #display.root_group = grp
    #display.refresh()

    # Initialize MAX3421E USB host chip which is needed by usb.core.
    # The link between usb.core and Max3421E happens by way of invisible
    # magic in the CircuitPython core, kinda like with displayio displays.
    print("Initializing USB host port...")
    usbHost = Max3421E(spi, chip_select=D10, irq=D9)
    sleep(0.1)

    # MAIN EVENT LOOP
    numpad = Numpad()
    print("Finding numpad...")
    while True:
        _collect()
        try:
            # Attempt to connect to USB numpad
            if numpad.find_config_numpad():
                print(numpad.device_info_str())
                connected = True
                for keys_ in numpad.poll():
                    # TODO: implement this
                    pass
                # If loop stopped, gamepad connection was lost
                print("Numpad disconnected")
                print("Finding numpad...")
            else:
                # No connection yet, so sleep briefly then try again
                sleep(0.1)
        except USBError as e:
            # This might mean gamepad was unplugged, or maybe some other
            # low-level USB thing happened which this driver does not yet
            # know how to deal with. So, log the error and keep going
            print(e)
            print("USB Error")
            print("Finding numpad...")


main()
