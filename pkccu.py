#!/usr/bin/python

import array
from bootstrap import *
from ola.ClientWrapper import ClientWrapper
import math
import signal
import select
import socket
import sys
import time

UDP_PORT = 5005

STATE_IDLE = 0
STATE_POWERUP = 1
STATE_FADE = 2

STATE_NAME = ['IDLE', 'POWERUP', 'FADE']

wrapper = ClientWrapper()

def DmxSent(status):
  #print 'DmxSent %d' % status.Succeeded()
  wrapper.Stop()

class Dmx(object):
  def __init__(self):
    # Channel 1 is pinspot, channel 2 is motor speed
    self.data = array.array('B', [0, 0]) # B for byte
    self.universe = 0

  # Clockwise High speed (5rpm) is 1; slow speed is 127 (0.5rpm)
  # Counter Clockwise High speed (5rpm) is 255; slow speed is 129 (0.5rpm)
  def Update(self, speed, pinspot):
    if pinspot == 0:
      self.data[0] = 0
    else:
      self.data[0] = 128
    self.data[1] = speed

    wrapper.Client().SendDmx(self.universe, self.data, DmxSent)
    wrapper.Run()

dmx = Dmx()


def Test():
  print 'Led test...'
  led.fill(Color(255.0, 0.0, 0.0, 1.0))
  led.update()
  sleep(1)
  print 'Led off'
  led.all_off()

  print 'DMX motor test...'
  dmx.Update(255, 0)
  sleep(12)
  # SendMotorSpeed(0)
  # sleep(5)
  # SendMotorSpeed(1)
  # sleep(5)

  print 'DMX motor off'
  dmx.Update(0, 0)

def TimeMs():
  return time.time() * 1000

def SignalHandler(sig, frame):
    led.all_off()
    dmx.Update(0, 0)
    sys.exit(0)

def foobar(x):
  if x == 0:
    return 0
  else:
    return math.log(x + 1.0, 2.0 + x/2)

class LedState(object):
  def __init__(self, time_ms):
    self.min_brightness = 0.2
    self.brightness_enhance = 0.0
    self.powerup_width_pixels = 3

  # Given a pixel from 0..17, draws into all strips
  def setPixel(self, pixel, hue):
    if pixel < 0 or pixel > LEDS_PER_STRIP - 1:
      return

    if hue > 0:
      led.setHue(pixel, hue)
      led.setHue(LEDS_PER_STRIP * 2 - pixel - 1, hue)
      led.setHue(LEDS_PER_STRIP * 2 + pixel, hue)
      led.setHue(LEDS_PER_STRIP * 4 - pixel - 1, hue)
      led.setHue(LEDS_PER_STRIP * 4 + pixel, hue)
      led.setHue(LEDS_PER_STRIP * 6 - pixel - 1, hue)
    else:
      led.setOff(pixel)
      led.setOff(LEDS_PER_STRIP * 2 - pixel - 1)
      led.setOff(LEDS_PER_STRIP * 2 + pixel)
      led.setOff(LEDS_PER_STRIP * 4 - pixel - 1)
      led.setOff(LEDS_PER_STRIP * 4 + pixel)
      led.setOff(LEDS_PER_STRIP * 6 - pixel - 1)

  def setPixelV(self, pixel, hue, v):
    if pixel < 0 or pixel > LEDS_PER_STRIP - 1:
      return

    if hue > 0:
      led.setHSV(pixel, hue, 1, v)
      led.setHSV(LEDS_PER_STRIP * 2 - pixel - 1, hue, 1, v)
      led.setHSV(LEDS_PER_STRIP * 2 + pixel, hue, 1, v)
      led.setHSV(LEDS_PER_STRIP * 4 - pixel - 1, hue, 1, v)
      led.setHSV(LEDS_PER_STRIP * 4 + pixel, hue, 1, v)
      led.setHSV(LEDS_PER_STRIP * 6 - pixel - 1, hue, 1, v)
    else:
      led.setOff(pixel)
      led.setOff(LEDS_PER_STRIP * 2 - pixel - 1)
      led.setOff(LEDS_PER_STRIP * 2 + pixel)
      led.setOff(LEDS_PER_STRIP * 4 - pixel - 1)
      led.setOff(LEDS_PER_STRIP * 4 + pixel)
      led.setOff(LEDS_PER_STRIP * 6 - pixel - 1)

  # Draws a powerup band at the location given by percentage
  def drawPowerup(self, pct, hue, hot_hue_deg):
    led.fillHue(hot_hue_deg)

    top = pct * (LEDS_PER_STRIP + self.powerup_width_pixels)
    bottom = top - self.powerup_width_pixels
    top_pixel = math.floor(top)
    bottom_pixel = math.ceil(bottom)

    for pixel in range(int(bottom_pixel), int(top_pixel)):
      self.setPixel(pixel, hue)

    residual_hue = min(360, hue + 20)
    v = 0.4
    self.setPixelV(int(top_pixel), residual_hue, v)
    self.setPixelV(int(bottom_pixel) - 1, residual_hue, v)

  def fillBackground(self, hue_deg):
    led.fillHue(hue_deg)

  def update(self, time_ms):
    brightness = min(1.0, self.min_brightness + self.brightness_enhance)
    led.setMasterBrightness(brightness)

    led.update()

class App(object):
  def __init__(self):
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.sock.bind(('', UDP_PORT))
    self.led_state = LedState(TimeMs())
    self.motor_speed = 0.0
    self.full_range_fade_ms = 30000.0
    self.speed_full_range = 1.0
    self.speed_fade_per_ms = self.speed_full_range / self.full_range_fade_ms
    self.be_full_range = 1.0
    self.be_fade_per_ms = self.be_full_range / self.full_range_fade_ms
    self.last_powerup_time_ms = 0.0
    self.last_fade_time_ms = 0.0
    self.packet = bytearray(4096)
    # Hue is in degrees (0..360)
    self.min_hue_deg = 155 * 360.0 / 255.0
    self.max_hue_deg = 255 * 360.0 / 255.0
    self.bg_hue_deg = self.min_hue_deg
    self.hue_fade_per_ms = (self.max_hue_deg - self.min_hue_deg) / self.full_range_fade_ms
    self.state = STATE_IDLE
    self.state_start_ms = 0
    self.powerup_hue = 0
    self.powerup_travel_ms = 500
    self.pinspot = 0

  def set_state(self, state, time_ms):
    self.state = state
    self.state_start_ms = time_ms
    print 'state: %s' % STATE_NAME[self.state]

  def handle_powerup(self, incr_pct, hue, time_ms):
    self.last_powerup_time_ms = time_ms

    # Jump in brightness and motor speed.
    # Background hue animates over powerup.
    be_incr = self.be_full_range * incr_pct / 100
    self.led_state.brightness_enhance = min(1.0, self.led_state.brightness_enhance + be_incr)


    self.set_state(STATE_POWERUP, time_ms)
    self.powerup_hue = hue

    print 'powerup: powerup_hue %f background hue %f brightness_enhance %f' % (self.powerup_hue, self.bg_hue_deg, self.led_state.brightness_enhance)

  def fade_to_idle(self, time_ms):
    # Delay before starting the fade
    fade_start_time = self.state_start_ms + 3000
    if time_ms > fade_start_time:
      # Hue fades according to time since last powerup
      delta_ms = time_ms - self.last_fade_time_ms
      self.bg_hue_deg = max(self.min_hue_deg, self.bg_hue_deg - self.hue_fade_per_ms * delta_ms)

      self.led_state.brightness_enhance = max(0.0, self.led_state.brightness_enhance - self.be_fade_per_ms * delta_ms)

      #print 'fade: brightness_enhance %f bg_hue_deg %f' % (self.led_state.brightness_enhance, self.bg_hue_deg)
      if self.led_state.brightness_enhance <= 0:
        self.set_state(STATE_IDLE, time_ms)

    self.led_state.fillBackground(self.bg_hue_deg)
    self.last_fade_time_ms = time_ms

  def update_network(self, time_ms):
    inputs = [ self.sock ]
    readable, writable, exceptional = select.select(inputs, [], [], 0)
    for item in readable:
      self.sock.recvfrom_into(self.packet)
      # Receive a hue
      powerup_hue_deg = self.packet[0] * 360.0 / 255.0
      incr_pct = 10
      self.handle_powerup(incr_pct, powerup_hue_deg, time_ms)

  def update_led(self, time_ms):
    if self.state == STATE_IDLE:
      self.led_state.fillBackground(self.bg_hue_deg)

    elif self.state == STATE_FADE:
      self.fade_to_idle(time_ms)

    elif self.state == STATE_POWERUP:
      pos_frac = (time_ms - self.state_start_ms) / self.powerup_travel_ms
      pos_frac = foobar(pos_frac)
      hue_delta_deg = 5
      hue_deg = min(self.max_hue_deg, self.bg_hue_deg + min(1.0, pos_frac) * hue_delta_deg)
      self.led_state.drawPowerup(pos_frac, self.powerup_hue, hue_deg)
      if pos_frac >= 0.99:
        self.set_state(STATE_FADE, time_ms)
        self.bg_hue_deg = hue_deg

    self.led_state.update(time_ms)

  def update(self, time_ms):
    self.update_network(time_ms)
    self.update_led(time_ms)

    # motor speed is driven by the "heat" (bg_hue), from update_led
    heat_frac = (self.bg_hue_deg - self.min_hue_deg) / (self.max_hue_deg - self.min_hue_deg)
    self.motor_speed = heat_frac

    if heat_frac > 0.9:
      self.pinspot = 1
    else:
      self.pinspot = 0

    speed = int(max(1.0, (1.0 - self.motor_speed) * 32.0))
    if speed >= 32:
      dmx.Update(0, self.pinspot)
    else:
      dmx.Update(speed, self.pinspot)


def Loop():
  signal.signal(signal.SIGINT, SignalHandler)

  app = App()

  frame_time_ms = 10

  print 'Entering loop...'
  while True:
    start_ms = TimeMs()

    app.update(start_ms)

    stop_ms = TimeMs()
    delay_time_ms = frame_time_ms - (stop_ms - start_ms)
    if delay_time_ms > 0:
      time.sleep(delay_time_ms / 1000.0)


#Test()
Loop()

print 'Exiting...'
led.all_off()
