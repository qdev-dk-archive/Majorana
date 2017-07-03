from Pulsed_Experiments_scripts import doPulsedExperiment

doPulsedExperiment(fast_axis='ramp',
                   slow_axis='dt',
                   slow_start=1e-6,
                   slow_stop=2e-6,
                   slow_npts=5,
                   fast_start=0,
                   fast_stop=0.1,
                   fast_nptp=3,
                   n_avgs=1,
                   pts_per_shot=4096,
                   hightime=1e-6,
                   meastime=1e-6,
                   trig_delay=1e-6,
                   demod_freq=10e6
                   )
x`
