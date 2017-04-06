# Majorana
Wrappers for Majorana QCoDeS

The repository contains the following files:

* Experiment_init.py: Sets up a QCoDeS station, the device annotator, and the commands.log
* sample.config: Configuration file containing settings like BNC connection numbers, IV convertion settings
* reload_settings.py: Reloads the sample.config and initialises a bunch of parameters for use in the notebook
* majorana_wrappers.py: Contains T10-specific versions of do1d, i.e. do1d_M, do2d_M.
* fast_diagrams.py: Contains the `fast_charge_diagram` function. 

