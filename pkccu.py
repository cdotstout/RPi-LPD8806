#!/usr/bin/python

import array
from bootstrap import *
from ola.ClientWrapper import ClientWrapper

print 'Led test...'
led.fill(Color(255.0, 0.0, 0.0, 1.0))
led.update()
sleep(1)
print 'Led off'
led.all_off()

print 'DMX motor test...'
def DmxSent(status):
  #print 'DmxSent %d' % status.Succeeded()
  wrapper.Stop()

universe = 0
motor_speed = 10 # 0..255
data = array.array('B', [motor_speed]) # B for byte
wrapper = ClientWrapper()
wrapper.Client().SendDmx(universe, data, DmxSent)
wrapper.Run()
sleep(3)

print 'DMX motor off'
motor_speed = 0 # 0..255
data = array.array('B', [motor_speed]) # B for byte
wrapper = ClientWrapper()
wrapper.Client().SendDmx(universe, data, DmxSent)
wrapper.Run()

print 'Exiting...'
