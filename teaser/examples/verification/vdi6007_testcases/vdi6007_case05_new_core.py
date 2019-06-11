#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

"""

import os
import numpy as np

from teaser.logic.simulation.vdi_core import VDICore
import teaser.examples.verification.vdi6007_testcases.vdi6007_case01 as vdic
from teaser.examples.verification.vdi6007_testcases.vdi6007shared import \
    prepare_thermal_zone, hourly_average, plot_result


def run_case5(plot_res=False):
    """
    Run test case 5

    Parameters
    ----------
    plot_res : bool, optional
        Defines, if results should be plotted (default: False)

    Returns
    -------
    result_tuple : tuple (of floats)
        Results tuple with maximal temperature deviations
        (max_dev_1, max_dev_10, max_dev_60)
    """

    # Definition of time horizon
    times_per_hour = 60
    timesteps = 24 * 60 * times_per_hour  # 60 days
    timesteps_day = int(24 * times_per_hour)

    # Variable inputs
    Q_ig = np.zeros(timesteps_day)
    source_igRad = np.zeros(timesteps_day)
    for q in range(int(7 * timesteps_day / 24), int(17 * timesteps_day / 24)):
        Q_ig[q] = 200 + 80
        source_igRad[q] = 80
    Q_ig = np.tile(Q_ig, 60)
    source_igRad = np.tile(source_igRad, 60)

    this_path = os.path.dirname(os.path.abspath(__file__))
    ref_file = 'case05_q_sol.csv'
    ref_path = os.path.join(this_path, 'inputs', ref_file)

    solarRad_raw = np.loadtxt(ref_path, usecols=(1,))
    solarRad = solarRad_raw[0:24]
    solarRad[solarRad > 100] = solarRad[solarRad > 100] * 0.15
    solarRad_adj = np.repeat(solarRad, times_per_hour)
    solarRad_in = np.array([np.tile(solarRad_adj, 60)])

    this_path = os.path.dirname(os.path.abspath(__file__))
    ref_file = 'case05_t_amb.csv'
    ref_path = os.path.join(this_path, 'inputs', ref_file)

    t_outside_raw = np.loadtxt(ref_path, delimiter=",")
    t_outside = ([t_outside_raw[2 * i, 1] for i in range(24)])
    t_outside_adj = np.repeat(t_outside, times_per_hour)
    weatherTemperature = np.tile(t_outside_adj, 60)

    equalAirTemp = weatherTemperature

    tz = prepare_thermal_zone(timesteps * 60, room="S1")
    tz.model_attr.transparent_areas = [7]  # Adjust setting for this test case

    calc = VDICore(tz)
    calc.equal_air_temp = np.zeros(timesteps) + 295.15

    # TODO: Check if t_set_heating is defined like this in the VDI
    calc.sim_vars["t_set_heating"] = 0  # in Kelvin
    calc.sim_vars["t_set_cooling"] = 600  # in Kelvin

    calc.heater_limit = np.zeros(3) + 1e10
    calc.cooler_limit = np.zeros(3) - 1e10

    calc.sim_vars["internal_gains_rad"] = source_igRad
    calc.sim_vars["internal_gains"] = Q_ig

    calc.sim_vars["equal_air_temp"] = equalAirTemp
    len_transp_areas = len(calc.thermal_zone.model_attr.transparent_areas)
    for i in range(len_transp_areas):
        calc.sim_vars[f"solar_rad_in_{i}"] = solarRad_in[i]

    t_air, q_air_hc = calc.simulate()

    T_air_mean = hourly_average(data=t_air - 273.15, times_per_hour=times_per_hour)

    T_air_1 = T_air_mean[0:24]
    T_air_10 = T_air_mean[216:240]
    T_air_60 = T_air_mean[1416:1440]

    ref_file = 'case05_res.csv'
    ref_path = os.path.join(this_path, 'inputs', ref_file)

    # Load reference results
    (T_air_ref_1, T_air_ref_10, T_air_ref_60) = vdic.load_res(ref_path)
    T_air_ref_1 = T_air_ref_1[:, 0]
    T_air_ref_10 = T_air_ref_10[:, 0]
    T_air_ref_60 = T_air_ref_60[:, 0]

    if plot_res:
        plot_result(T_air_1, T_air_ref_1, "Results day 1", "temperature")
        plot_result(T_air_10, T_air_ref_10, "Results day 10", "temperature")
        plot_result(T_air_60, T_air_ref_60, "Results day 60", "temperature")

    max_dev_1 = np.max(np.abs(T_air_1 - T_air_ref_1))
    max_dev_10 = np.max(np.abs(T_air_10 - T_air_ref_10))
    max_dev_60 = np.max(np.abs(T_air_60 - T_air_ref_60))

    print("Max. deviation day 1: " + str(max_dev_1))
    print("Max. deviation day 10: " + str(max_dev_10))
    print("Max. deviation day 60: " + str(max_dev_60))

    return (max_dev_1, max_dev_10, max_dev_60)


if __name__ == '__main__':
    run_case5(plot_res=True)
