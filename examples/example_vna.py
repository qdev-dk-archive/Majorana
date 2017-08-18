
# Example how to use a Rhode & Schwarz VNA, here called v1
## See also https://github.com/QCoDeS/Qcodes/blob/master/docs/examples/driver_examples/Qcodes%20example%20with%20Rohde%20Schwarz%20ZNB.ipynb


## Set power on all channels
v1.channels.power(-50)

## Set power of specific channel:
v1.channels.S21.power(-30)

## Turn rf on
v1.rf_on()

## Do a measurement 
### Define parameters for traces:

v1.channels.S21.start(100e3)
v1.channels.S21.stop(6e6)

npts = 200
v1.channels.S21.npts(npts)

## sweep left cutter and take traces
do1d(deca.lcut, 0, -10, 100, 0.1, v1.channels.S21.trace)

### define a frequency span
#v1.channels.S11.span(200e3)
#v1.channels.S11.center(1e6)
#v1.channels.S11.npts(100)