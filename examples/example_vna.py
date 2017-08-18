
npts = 200
v1.channels.S21.npts(npts)

do1d(deca.lcut, 0, -10, 100, 0.1, v1.channels.S21.trace)

