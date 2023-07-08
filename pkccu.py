#!/usr/bin/python

import array
from bootstrap import *
from ola.ClientWrapper import ClientWrapper
import signal
import select
import socket
import sys
import time

UDP_PORT = 5005

wrapper = ClientWrapper()

def DmxSent(status):
  #print 'DmxSent %d' % status.Succeeded()
  wrapper.Stop()

# Clockwise High speed (5rpm) is 1; slow speed is 127 (0.5rpm)
# Counter Clockwise High speed (5rpm) is 255; slow speed is 129 (0.5rpm)
def SendMotorSpeed(speed):
  universe = 0
  data = array.array('B', [speed]) # B for byte
  wrapper.Client().SendDmx(universe, data, DmxSent)
  wrapper.Run()

def Test():
  print 'Led test...'
  led.fill(Color(255.0, 0.0, 0.0, 1.0))
  led.update()
  sleep(1)
  print 'Led off'
  led.all_off()

  print 'DMX motor test...'
  SendMotorSpeed(255)
  sleep(12)
  # SendMotorSpeed(0)
  # sleep(5)
  # SendMotorSpeed(1)
  # sleep(5)

  print 'DMX motor off'
  SendMotorSpeed(0)

def TimeMs():
  return time.time() * 1000

def SignalHandler(sig, frame):
    led.all_off()
    SendMotorSpeed(0)
    sys.exit(0)

class LedState(object):
  def __init__(self, time_ms):
    self.start_ms = time_ms
    self.fade_duration = 2000
    self.min_brightness = 0.2
    self.max_brightness = 0.2
    self.brightness_enhance = 0.0
    self.direction = 1
    self.hue_deg = 0

  def update(self, time_ms):
    pos_frac = (time_ms - self.start_ms) / self.fade_duration

    if pos_frac > 1.0:
      self.start_ms = time_ms
      self.direction *= -1
      pos_frac = 0.0

    if self.direction < 0:
      pos_frac = 1.0 - pos_frac

    brightness = self.min_brightness + pos_frac * (self.max_brightness - self.min_brightness)
    brightness = min(1.0, brightness + self.brightness_enhance)

    led.setMasterBrightness(brightness)
    led.fillHue(self.hue_deg)
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
    self.hue_fade_per_ms = (self.max_hue_deg - self.min_hue_deg) / self.full_range_fade_ms

  def handle_powerup(self, incr_pct, time_ms):
    self.last_powerup_time_ms = time_ms

    hue_incr = (self.max_hue_deg - self.min_hue_deg) * incr_pct / 100
    self.led_state.hue_deg = min(self.max_hue_deg, self.led_state.hue_deg + hue_incr)

    be_incr = self.be_full_range * incr_pct / 100
    self.led_state.brightness_enhance = min(1.0, self.led_state.brightness_enhance + be_incr)

    speed_incr = self.speed_full_range * incr_pct / 100
    self.motor_speed = min(1.0, self.motor_speed + speed_incr)

    print 'powerup: hue %f brightness_enhance %f motor speed %f' % (self.led_state.hue_deg, self.led_state.brightness_enhance, self.motor_speed)

  def fade_to_idle(self, time_ms):
    # Delay before starting the fade
    fade_start_time = self.last_powerup_time_ms + 3000
    if time_ms > fade_start_time:
      # Hue fades according to time since last powerup
      delta_ms = time_ms - self.last_fade_time_ms
      self.led_state.hue_deg = max(self.min_hue_deg, self.led_state.hue_deg - self.hue_fade_per_ms * delta_ms)
      self.motor_speed = max(0.0, self.motor_speed - self.speed_fade_per_ms * delta_ms)
      self.led_state.brightness_enhance = max(0.0, self.led_state.brightness_enhance - self.be_fade_per_ms * delta_ms)

      #print 'fade: brightness_enhance %f motor speed %f' % (self.led_state.brightness_enhance, self.motor_speed)
      #print 'fade: hue_deg %f time_ms %f' % (self.led_state.hue_deg, time_ms)

    self.last_fade_time_ms = time_ms

  def update_network(self, time_ms):
    inputs = [ self.sock ]
    readable, writable, exceptional = select.select(inputs, [], [], 0)
    for item in readable:
      self.sock.recvfrom_into(self.packet)
      # Receive an increment percentage
      incr_pct = self.packet[0]
      self.handle_powerup(incr_pct, time_ms)

  def update(self, time_ms):
    self.update_network(time_ms)

    self.fade_to_idle(time_ms)

    self.led_state.update(time_ms)

    speed = int(max(1.0, (1.0 - self.motor_speed) * 32.0))
    if speed >= 32:
      SendMotorSpeed(0)
    else:
      SendMotorSpeed(speed)


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
