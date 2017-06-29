# Pulsed Experiment Setup

In the scripts `Pulsed_Experiments_scripts`, some assumption are made on the connections of the setup.

Here is a description of the intended setup.

## Boxes

* Zurich Instruments UHF Lock-In Amplifier (ZI)
* Keysight 33500 B Function Generator (KEY)
* Tektronix AWG 5014C Arbitrary Waveform Generator (AWG)
* Mini-circuits ZASWA-2-50DR+ swtich (SWITCH)
* Whatever artificial sample you can get, perhaps just a BNC cable (SAMPLE)

## Wiring

KEY output 1 -> AWG add input ch 1 (on the back of the box)
AWG channel 1 mkr 2 -> KEY Ext Trig/ Gate/ FSK/ Burst (on the back of the box)
AWG channel 1 analog -> SAMPLE
AWG channel 1 mkr 1 (split) -> ZI Ref / Trigger 1
AWG channel 1 mkr 1 -> SWITCH TTL
SAMPLE -> ZI Signal Input 1
ZI Signal Output 1 -> SWITCH RF In
SWITCH RF Out 2 -> SAMPLE
