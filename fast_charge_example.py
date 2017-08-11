from fast_diagrams import fast_charge_diagram
import time

zi.signal_output1_ampdef('dBm')
zi.signal_output1_amplitude(-50)
zi.signal_output1_offset(0)
zi.signal_output1_on('ON')
zi.oscillator1_freq(274e6)
zi.demod1_timeconstant(0.1e-6)


zi.signal_output2_ampdef('dBm')
zi.signal_output2_amplitude(-50)
zi.signal_output2_offset(0)
zi.signal_output2_on('ON')
zi.oscillator2_freq(274e6)
zi.demod5_timeconstant(0.1e-6)

try:
    start = time.time() 
    plot, data =  fast_charge_diagram(keysight_channel='ch01',
                        fast_v_start=-0.004,
                        fast_v_stop=0.004,
                        n_averages=1000,
                        qdac_channel=qdac.channels.chan1.v,
                        comp_scale=0.5,
                        q_start=0.,
                        q_stop=0.1,
                        npoints=10,
                        delay=0.05,
                        trigger_holdoff=20e-6,
                        zi_samplingrate='1.80 GHz',
                        qdac_fast_channel=qdac.channels.chan3.v,
                        scope_signal='Demod 1 R',
                        zi_trig_signal='Trig Input 1')
    
    stop = time.time()
    print("fast diagram took {}".format(stop-start))
finally:
    zi.signal_output1_on('OFF')
    zi.signal_output2_on('OFF')
