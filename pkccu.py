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
    self.min_brightness = 0.4
    self.max_brightness = 0.6
    self.brightness_enhance = 0.0
    self.direction = 1

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

    led.fill(Color(0.0, 0.0, 255.0, brightness))
    led.update()

class App(object):
  def __init__(self):
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.sock.bind(('', UDP_PORT))
    self.led_state = LedState(TimeMs())
    self.motor_speed = 0.0
    self.last_action_time_ms = 0.0
    self.powerup_count = 0

  def handle_powerup(self, time_ms):
    self.last_action_time_ms = time_ms
    self.powerup_count += 1

    self.led_state.brightness_enhance = min(1.0, self.led_state.brightness_enhance + 0.1)
    self.motor_speed = min(1.0, self.motor_speed + 0.1)

    print 'powerup: brightness_enhance %f motor speed %f' % (self.led_state.brightness_enhance, self.motor_speed)

  def timeout(self, time_ms):
    if self.powerup_count == 0:
      return

    self.powerup_count -= 1
    self.last_action_time_ms = time_ms

    self.led_state.brightness_enhance = max(0.0, self.led_state.brightness_enhance - 0.1)
    self.motor_speed = max(0.0, self.motor_speed - 0.1)

    print 'timeout: brightness_enhance %f motor speed %f' % (self.led_state.brightness_enhance, self.motor_speed)

  def update_network(self, time_ms):
    bufsize = 1024
    inputs = [ self.sock ]
    readable, writable, exceptional = select.select(inputs, [], [], 0)
    for item in readable:
      result = self.sock.recvfrom(bufsize)
      self.handle_powerup(time_ms)

  def update(self, time_ms):
    self.update_network(time_ms)

    if time_ms - self.last_action_time_ms > 2000:
      self.timeout(time_ms)

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
