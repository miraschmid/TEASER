#!/usr/bin/env python
# coding=utf-8
"""
Shared code for all VDI 6007 test cases
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

from teaser.project import Project
from teaser.logic.buildingobjects.building import Building
from teaser.logic.buildingobjects.thermalzone import ThermalZone
from teaser.logic.buildingobjects.calculation.two_element import TwoElement
from teaser.data.weatherdata_df import WeatherDataDF


def prepare_thermal_zone(timesteps, room, weather=None):
    """Prepare the thermal zone for running VDI test case

    Parameters
    ----------
    timesteps : int
        Number of time steps
    room : str
        Type of room {"S1", "S2", "L"}; "S" indicates "small", "L" indicates "large";
        the numbers 1 and 2 indicate the number of exterior walls
    weather : numpy.array
        Optional weather input

    Returns
    -------
    tz : teaser.logic.buildingobjects.thermalzone.ThermalZone
        Thermal zone object with setup for test case
    """

    if weather is None:
        weather = WeatherDataDF()
        weather.weather_df["air_temp"] = 295.15
        weather.reindex_weather_df(format="minutes")
        weather.weather_df = weather.weather_df.loc[:timesteps-1]

    prj = Project()
    prj.weather_data = weather

    bldg = Building(prj)
    tz = ThermalZone(bldg)

    model_data = TwoElement(tz, merge_windows=False, t_bt=5)

    if room == "S1":
        model_data.r1_iw = 0.000595693407511  # Yes
        model_data.c1_iw = 14836354.6282  # Yes
        model_data.area_iw = 75.5  # Yes
        model_data.r_rest_ow = 0.03895919557  # Yes
        model_data.r1_ow = 0.00436791293674  # Yes
        model_data.c1_ow = 1600848.94  # Yes
    elif room == "S2":
        model_data.r1_iw = 0.000668895639141
        model_data.c1_iw = 12391363.8631
        model_data.area_iw = 60.5
        model_data.r_rest_ow = 0.01913729904
        model_data.r1_ow = 0.0017362530106
        model_data.c1_ow = 5259932.23
    elif room == "L":
        model_data.r1_iw = 0.003237138
        model_data.c1_iw = 7297100
        model_data.area_iw = 75.5
        model_data.r_rest_ow = 0.039330865
        model_data.r1_ow = 0.00404935160802
        model_data.c1_ow = 47900
    else:
        raise LookupError("Unknown room type selected. Choose from {'S1', 'S2', 'L'}")

    if room == "S2":
        model_data.area_ow = 25.5
        model_data.outer_wall_areas = [10.5, 15]
        model_data.window_areas = [0, 0]
        model_data.transparent_areas = [7, 7]
    else:
        model_data.area_ow = 10.5  # Yes
        model_data.outer_wall_areas = [10.5]  # Yes
        model_data.window_areas = np.zeros(1)  # Yes
        model_data.transparent_areas = np.zeros(1)  # Yes

    tz.volume = 52.5  # No, is 0 in case 11
    tz.density_air = 1.19
    tz.heat_capac_air = 0

    model_data.ratio_conv_rad_inner_win = 0.09  # No, is 0 in case 11
    model_data.weighted_g_value = 1  # Yes
    if room == "S2":
        model_data.alpha_comb_inner_iw = 2.12
    else:
        model_data.alpha_comb_inner_iw = 2.24  # No, is 3 in case 11
    model_data.alpha_comb_inner_ow = 2.7  # Yes
    model_data.alpha_conv_outer_ow = 20  # No effect because only used in equalAir
    model_data.alpha_rad_outer_ow = 5  # Yes
    model_data.alpha_comb_outer_ow = 25  # Yes, in Modelica alpha_wall is 25 * 10.5
    model_data.alpha_rad_inner_mean = 5  # Yes

    tz.model_attr = model_data

    return tz


def hourly_average(data, times_per_hour):
    """Calculate the hourly average of the data in smaller time steps

    Parameters
    ----------
    data : numpy.array
        Input data in small time steps
    times_per_hour : int
        Number of time steps per hour (usually 60: 1 for each minute)

    Returns
    -------
    result : numpy.array
        Output data in hourly averages
    """

    result = np.array(
        [
            np.mean(data[i * times_per_hour: (i + 1) * times_per_hour])
            for i in range(24 * 60)
        ]
    )

    return result


def plot_result(res, ref, title, temperature_or_heat, res_raw=None):
    """Plot result comparison to reference values

    Parameters
    ----------
    res : numpy.array
        Simulation result (averaged values)
    ref : numpy.array
        Reference values
    title : str
        Title of the plot
    temperature_or_heat : str
        Decide between {"temperature", "heat"}
    """

    if temperature_or_heat == "temperature":
        y_label_top = "Temperature in °C"
        y_label_bottom = "Temperature difference in K"
    elif temperature_or_heat == "heat":
        y_label_top = "Heat load in W"
        y_label_bottom = "Heat load difference in W"
    else:
        raise LookupError("Unknown plot type. Must be 'temperature' or 'heat'")

    plt.figure()
    ax_top = plt.subplot(211)
    plt.plot(ref, label="Reference", color="black", linestyle="--")
    plt.plot(res, label="Simulation", color="blue", linestyle="-")
    plt.scatter(range(len(ref)), ref, color="black", marker="x")
    plt.scatter(range(len(res)), res, color="blue", marker="o")
    if res_raw is not None:
        plt.plot(
            [x / 60 for x in range(len(res_raw))],
            res_raw,
            color="red",
            linestyle="dotted",
            alpha=0.5,
            label="Simulation raw output",
        )

    plt.legend()
    plt.ylabel(y_label_top)

    plt.title(title)

    plt.subplot(212, sharex=ax_top)
    plt.plot(res[:len(ref)] - ref, label="Ref. - Sim.")
    plt.legend()
    plt.ylabel(y_label_bottom)
    plt.xticks([4 * i for i in range(7)])
    # plt.xlim([1, 48])
    plt.xlim([1, 24])
    plt.xlabel("Time in h")

    plt.show()


def plot_debug_data(data_debug, var, save_as):
    """Plot debug data

    Parameters
    ----------
    data_debug : pandas.DataFrame
        Debug data output
    var : str
        Name of the variable to plot
    save_as : pathlib.Path
        File path to store the plot into
    """

    if var == "t_ow":
        y_label = "Outside outer wall temperature in °C"
    else:
        raise LookupError("Unknown variable")

    if "t_" in var:
        data_to_plot = data_debug[var] - 273.15
    else:
        data_to_plot = data_debug[var]

    plt.figure()
    plt.subplot(111)
    plt.plot(data_to_plot, label="Simulation", color="blue", linestyle="-")

    plt.ylabel(y_label)

    plt.xlabel("Time in h")

    plt.savefig(save_as)


def plot_set_temperature(tset):
    """Plot set temperature used in e.g. case 11

    Parameters
    ----------
    tset : : numpy.array
        Time series of prescribed set temperature
    """

    reference = [
        [0, 22],
        [3600, 22],
        [7200, 22],
        [10800, 22],
        [14400, 22],
        [18000, 22],
        [21600, 22],
        [21600.1, 27],
        [28800, 27],
        [32400, 27],
        [36000, 27],
        [39600, 27],
        [43200, 27],
        [46800, 27],
        [50400, 27],
        [54000, 27],
        [57600, 27],
        [61200, 27],
        [64800, 27],
        [64800.1, 22],
        [72000, 22],
        [75600, 22],
        [79200, 22],
        [82800, 22],
    ]

    reference = [[x[0] / 60, x[1]] for x in reference]

    plt.figure()
    plt.subplot(111)
    plt.plot(tset - 273.15, color="blue", label="Simulation", linestyle="-")
    plt.plot(
        [x[0] for x in reference],
        [x[1] for x in reference],
        color="black",
        label="Reference (Modelica)",
        linestyle="--",
    )
    plt.ylabel("Temperature in °C")
    plt.xlabel("Time in minutes")

    plt.xlim([0, 60 * 24])

    plt.legend()
    plt.title("Set temperature in °C for one day")

    plt.show()


def plot_internal_gains_rad(ig_rad):
    """Plot internal radiative gains used in e.g. case 11

    Parameters
    ----------
    ig_rad : : numpy.array
        Time series of internal radiative gains
    """

    reference = [
        [0, 0],
        [3600, 0],
        [7200, 0],
        [10800, 0],
        [14400, 0],
        [18000, 0],
        [21600, 0],
        [21600, 1000],
        [25200, 1000],
        [28800, 1000],
        [32400, 1000],
        [36000, 1000],
        [39600, 1000],
        [43200, 1000],
        [46800, 1000],
        [50400, 1000],
        [54000, 1000],
        [57600, 1000],
        [61200, 1000],
        [64800, 1000],
        [64800, 0],
        [68400, 0],
        [72000, 0],
        [75600, 0],
        [79200, 0],
        [82800, 0],
        [86400, 0],
    ]

    reference = [[x[0] / 60, x[1]] for x in reference]

    plt.figure()
    plt.subplot(111)
    plt.plot(ig_rad, color="blue", label="Simulation", linestyle="-")
    plt.plot(
        [x[0] for x in reference],
        [x[1] for x in reference],
        color="black",
        label="Reference (Modelica)",
        linestyle="--",
    )
    plt.ylabel("Internal gains in W")
    plt.xlabel("Time in minutes")

    plt.xlim([0, 60 * 24])

    plt.legend()
    plt.title("Internal gains in W for one day")

    plt.show()


def prepare_internal_gains_rad(timesteps_day):
    """Prepare a time series of prescribed internal radiative gains

    Parameters
    ----------
    timesteps_day : int
        Number of time steps in a day

    Returns
    -------
    result : numpy.array
        Time series of prescribed internal radiative gains
    """
    result = np.zeros(timesteps_day)
    for q in range(int(6 * timesteps_day / 24), int(18 * timesteps_day / 24)):
        result[q] = 1000
    result = np.tile(result, 60)

    return result


def prepare_set_temperature(timesteps_day):
    """Prepare a time series of prescribed set temperature

    Parameters
    ----------
    timesteps_day : int
        Number of time steps in a day

    Returns
    -------
    result : numpy.array
        Time series of prescribed set temperature

    """
    result = np.zeros(timesteps_day) + 273.15 + 22
    for q in range(int(6 * timesteps_day / 24), int(18 * timesteps_day / 24)):
        result[q] = 273.15 + 27
    result = np.tile(result, 60)

    return result
