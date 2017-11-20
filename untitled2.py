# -*- coding: utf-8 -*-
"""
Created on Fri Nov 17 19:22:20 2017

@author: root
"""

for i in range(25):
    
    runfile('A:/qcodes_experiments/modules/Majorana/pulsed_experiment_simple_example_of_running.py')
    sleep(40)
    qdac.channels.chan40.v(qdac.channels.chan40.v()+0.0003)
    
    
    