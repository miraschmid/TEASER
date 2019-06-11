#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

"""
import os
import numpy as np

from teaser.project import Project
from teaser.logic.buildingobjects.building import Building
from teaser.logic.buildingobjects.thermalzone import ThermalZone
from teaser.logic.buildingobjects.calculation.two_element import TwoElement
from teaser.logic.simulation.vdi_core import VDICore

# import customized weather class
from teaser.data.weatherdata_df import WeatherDataDF

import teaser.examples.verification.vdi6007_testcases.vdi6007_case01 as vdic
from teaser.examples.verification.vdi6007_testcases.vdi6007shared import \
    hourly_average, plot_result


def run_case10(plot_res=False):
    """
    Run test case 10

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

    # Zero inputs
    solarRad_wall = np.zeros((timesteps, 1))

    # Constant inputs
    t_black_sky = np.zeros(timesteps) + 273.15

    # Variable inputs
    Q_ig = np.zeros(timesteps_day)
    source_igRad = np.zeros(timesteps_day)
    for q in range(int(7 * timesteps_day / 24), int(17 * timesteps_day / 24)):
        Q_ig[q] = 200 + 80
        source_igRad[q] = 80
    Q_ig = np.tile(Q_ig, 60)
    source_igRad = np.tile(source_igRad, 60)

    this_path = os.path.dirname(os.path.abspath(__file__))
    ref_file = 'case10_q_sol.csv'
    ref_path = os.path.join(this_path, 'inputs', ref_file)

    q_sol_rad_win_raw = np.loadtxt(ref_path, usecols=(1,))
    solarRad_win = q_sol_rad_win_raw[0:24]
    solarRad_win[solarRad_win > 100] = solarRad_win[solarRad_win > 100] * 0.15
    solarRad_win_adj = np.repeat(solarRad_win, times_per_hour)
    solarRad_win_in = np.array([np.tile(solarRad_win_adj, 60)])

    ref_file = 'case10_t_amb.csv'
    ref_path = os.path.join(this_path, 'inputs', ref_file)

    t_outside_raw = np.loadtxt(ref_path, delimiter=",")
    t_outside = ([t_outside_raw[2 * i, 1] for i in range(24)])
    t_outside_adj = np.repeat(t_outside, times_per_hour)
    weatherTemperature = np.tile(t_outside_adj, 60)

    weather = WeatherDataDF()
    weather.reindex_weather_df(format="minutes")
    weather.weather_df = weather.weather_df[:timesteps]
    weather.weather_df["air_temp"] = weatherTemperature

    prj = Project()
    prj.weather_data = weather

    bldg = Building(prj)

    tz = ThermalZone(bldg)

    model_data = TwoElement(tz, merge_windows=True, t_bt=5)

    #  Store building parameters for testcase 10
    model_data.r1_iw = 0.000779671554640369
    model_data.c1_iw = 12333949.4129606
    model_data.area_iw = 58
    model_data.r_rest_ow = 0.011638548
    model_data.r1_ow = 0.00171957697767797
    model_data.c1_ow = 4338751.41
    model_data.area_ow = 28
    model_data.outer_wall_areas = [28]
    model_data.window_areas = np.zeros(1)
    model_data.transparent_areas = [7]
    tz.volume = 52.5
    tz.density_air = 1.19
    tz.heat_capac_air = 0
    tz.t_ground = 288.15
    model_data.ratio_conv_rad_inner_win = 0.09
    model_data.weighted_g_value = 1
    model_data.alpha_comb_inner_iw = 2.12
    model_data.alpha_comb_inner_ow = 2.398
    # alpha_conv_outer_ow needs to be area weighted for groundfloor ((1.7 *
    # 17.5 + 20* 3.5)/21)=4.75
    model_data.alpha_conv_outer_ow = 4.75
    model_data.alpha_rad_outer_ow = 5
    model_data.alpha_comb_outer_ow = 9.75
    model_data.alpha_rad_inner_mean = 5

    model_data.solar_absorp_ow = 0.7
    model_data.ir_emissivity_outer_ow = 0.9
    model_data.weightfactor_ow = [0.04646093176283288]
    model_data.weightfactor_win = [0.32441554918476245]
    model_data.weightfactor_ground = 0.6291235190524047

    tz.model_attr = model_data

    calc = VDICore(tz)

    calc.initial_air_temp = 273.15 + 17.6
    calc.initial_outer_wall_temp = 273.15 + 17.6
    calc.initial_inner_wall_temp = 273.15 + 17.6

    calc.sim_vars["equal_air_temp"] = np.zeros(timesteps) + 295.15

    calc.sim_vars["t_set_heating"] = np.zeros(timesteps)  # in Kelvin
    calc.sim_vars["t_set_cooling"] = 600  # in Kelvin

    calc.heater_limit = np.zeros(3) + 1e10
    calc.cooler_limit = np.zeros(3) - 1e10

    calc.sim_vars["internal_gains_rad"] = source_igRad
    calc.sim_vars["internal_gains"] = Q_ig

    len_transp_areas = len(calc.thermal_zone.model_attr.transparent_areas)
    for i in range(len_transp_areas):
        calc.sim_vars[f"solar_rad_in_{i}"] = solarRad_win_in[i]

    calc.sim_vars["equal_air_temp"] = weatherTemperature

    calc.sim_vars["equal_air_temp"] = calc._eq_air_temp(
        h_sol=solarRad_wall, t_black_sky=t_black_sky)

    t_air, q_air_hc = calc.simulate()

    T_air_mean = hourly_average(data=t_air-273.15, times_per_hour=times_per_hour)

    T_air_1 = T_air_mean[0:24]
    T_air_10 = T_air_mean[216:240]
    T_air_60 = T_air_mean[1416:1440]

    ref_file = 'case10_res.csv'
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
    run_case10(plot_res=True)
