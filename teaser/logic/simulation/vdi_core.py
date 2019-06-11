# -*- coding: utf-8 -*-
"""Module contains class to calculate a thermal zone with VDI core

This is the latest implementation of the VDI core. An older (obsolete) implementation is
located at TEASER/teaser/logic/simulation/low_order_VDI.py

The tests for this VDI core are located at
TEASER/teaser/examples/verification/vdi6007_testcases

Furthermore, there is an example simulating a demo building with this core located
at TEASER/teaser/examples/simulation/example_vdi_core.py
"""

from __future__ import division

import math
import numpy as np
import pandas as pd


class VDICore(object):
    """Class to handle VDI 6007 simulation directly in Python.

    Contains function and classes to simulate according to VDI core directly in
    python.

    Attributes
    ----------
    thermal_zone: instance of ThermalZone
        TEASER instance of ThermalZone
    interval: int
        Interval of timesteps in seconds {1, 60, 3600}
    stoptime: int
        Stoptime of calculation in seconds (should be a multiple of the interval)
    sim_vars: pandas.DataFrame
        Simulation variables
    weather_data:  instance of WeatherData class
        TEASER isntance of WeatherData class containing TRY weather data.
    building: instance of Building
        TEASER instance of Building
    room_air_temperature: np.array or pd.series
        simulation results for room air temperature in degree Celsius
    heat_load: np.array         #TODO: this is not used!
        simulation results for heating load in Watt
    cooling_load: np.array      #TODO: this is not used!
        simulation results for cooling load in Watt
    heater_limit: list (of floats)
        List with heater limit values in Watt
    cooler_limit: list (of floats)
        List with cooler limit values in Watt
    initial_air_temp : float
        Initial indoor air temperature in Kelvin
    initial_inner_wall_temp : float
        Initial inner wall temperature in Kelvin
    initial_outer_wall_temp : float
        Initial outer wall temperature in Kelvin
    heater_order : np.array (of int)
        describes in which order the different heating devices are turned on;
        Current assumption is that the 3 possible heaters are
        1: Heat added to air volume
        2: Heat added to inner walls
        3: Heat added to outer walls
    cooler_order : np.array (of int)
        describes in which order the different cooling devices are turned on
        For assumption on what the coolers do see heater_order doc above
    debug : boolean
        Set to True for additional debug output of simulation

    """

    def __init__(self, thermal_zone, interval=60, stoptime=5_184_000):
        """Constructor of DataClass

        Parameters
        ----------
        thermal_zone: instance of ThermalZone
            TEASER instance of ThermalZone
        interval: int
            Interval of timesteps in seconds {1, 60, 3600}
        stoptime: int
            Stoptime of calculation in seconds
            (should be a multiple of the interval)

        """

        self.thermal_zone = thermal_zone
        self.interval = interval
        self.stoptime = stoptime
        self.weather_data = self.thermal_zone.parent.parent.weather_data
        self.building = self.thermal_zone.parent
        self.room_air_temperature = None

        cols = [
            "outdoor_temp",
            "alpha_rad",
            "q_solar_conv",
            "q_solar_rad_to_in_wall",
            "q_solar_rad_to_outer_wall",
            "q_loads_rad",
            "q_loads_to_inner_wall",
            "q_loads_to_outer_wall",
            "equal_air_temp",
            "vent_rate",
            "internal_gains",
            "internal_gains_rad",
            "t_ow",
            "t_owi",
            "t_iw",
            "t_iwi",
            "t_air",
            "q_air",
            "q_air_hc",
            "q_iw_hc",
            "q_ow_hc",
        ]

        len_transp_areas = len(self.thermal_zone.model_attr.transparent_areas)
        for i in range(len_transp_areas):
            cols.append(f"e_solar_conv_{i}")

        for i in range(len_transp_areas):
            cols.append(f"e_solar_rad_{i}")

        for i in range(len_transp_areas):
            cols.append(f"solar_rad_in_{i}")

        len_area_ow = len(self.thermal_zone.model_attr.outer_wall_areas)
        for i in range(len_area_ow):
            cols.append(f"q_solar_rad_iw_{i}")
            cols.append(f"q_solar_rad_ow_{i}")

        idx = np.arange(0, self.stoptime, self.interval)
        self.sim_vars = pd.DataFrame(index=idx, columns=cols)

        sol_rad_transp = np.transpose(self._solar_radiation())
        if sol_rad_transp.size != 0:
            for i in range(len_transp_areas):
                self.sim_vars[f"solar_rad_in_{i}"] = sol_rad_transp[i]

        #  Todo: Get heater limits from thermal_zone
        self.heater_limit = [1e10, 1e10, 1e10]
        self.cooler_limit = [-1e10, -1e10, -1e10]

        # time setting for simulation
        # self.timesteps = 60 * 60 * 24

        self.initial_air_temp = 295.15
        self.initial_inner_wall_temp = 295.15
        self.initial_outer_wall_temp = 295.15

        self.heater_order = np.array([1, 2, 3])
        self.cooler_order = np.array([1, 2, 3])

        self.sim_vars["internal_gains"] = 0
        self.sim_vars["internal_gains_rad"] = 0

        # self.equal_air_temp = self._eq_air_temp(h_sol=self.solar_rad_in)

        self.t_set_heat_day = (
            np.array(
                [
                    18,
                    18,
                    18,
                    18,
                    18,
                    18,
                    21,
                    21,
                    21,
                    21,
                    21,
                    21,
                    21,
                    21,
                    21,
                    21,
                    21,
                    21,
                    21,
                    21,
                    21,
                    21,
                    21,
                    18,
                ]
            )
            + 273.15
        )
        self.t_set_heating = np.tile(self.t_set_heat_day, 365)
        self.t_set_cooling = np.zeros(self.stoptime) + 273.15 + 1000

        self.sim_vars["vent_rate"] = 0 + (
            self.thermal_zone.volume * self.thermal_zone.infiltration_rate / 3600
        )
        # self.heater_order = np.array([1, 2, 3])
        # self.cooler_order = np.array([1, 2, 3])
        self.debug = False

    def _eq_air_temp(self, h_sol, t_black_sky, with_longwave=False, i_max=100):
        """
        Calculates equal air temperature

        corresponds to function eqAirTemp from eqAirTemp

        h_sol - solar radiation per unit area
        sunblind - opening factor of sunblinds for each direction
        (0 = open to
        1 = closed)
        with_longwave

        Parameters
        ----------
        h_sol
        sunblind
        with_longwave
        i_max

        Returns
        -------
        t_eq_air
        """
        #  Todo: Cleanup docstring

        #  Todo: Where to store t_balck_sky?
        # t_black_sky = np.zeros(timesteps) + 273.15
        t_dry_bulb = self.weather_data.weather_df[
            "air_temp"
        ]  # in Kelvin TODO: in Kelvin?

        list_window_areas = []
        list_sunblind = []
        for window in self.thermal_zone.windows:
            list_window_areas.append(window.area)
            list_sunblind.append(0.0)

        sunblind_in = np.zeros_like(h_sol)
        sunblind_in[h_sol > i_max] = 0.85
        # sunblind_in = np.repeat(sunblind_in, 60, axis=0)
        # sunblind_in = np.tile(sunblind_in.T, 60).T

        # sunblind_in = np.zeros_like(h_sol)
        # sunblind_in[h_sol > i_max] = 0.85

        #  Todo: Check inputs (set correctly?)
        a_ext = self.thermal_zone.model_attr.solar_absorp_ow
        e_ext = self.thermal_zone.model_attr.ir_emissivity_outer_ow
        wf_wall = self.thermal_zone.model_attr.weightfactor_ow
        wf_win = self.thermal_zone.model_attr.weightfactor_win
        wf_ground = self.thermal_zone.model_attr.weightfactor_ground
        t_ground = self.thermal_zone.t_ground
        alpha_conv_outer_ow = self.thermal_zone.model_attr.alpha_conv_outer_ow
        alpha_rad_outer_ow = self.thermal_zone.model_attr.alpha_rad_outer_ow

        #

        n = len(wf_wall)

        # Compute equivalent long wave and short wave temperatures
        del_t_eq_lw = (t_black_sky - t_dry_bulb) * (
            e_ext
            * alpha_rad_outer_ow
            / (alpha_rad_outer_ow + alpha_conv_outer_ow * 0.93)
        )
        del_t_eq_sw = h_sol * a_ext / (alpha_rad_outer_ow + alpha_conv_outer_ow)

        # Compute equivalent window and wall temperatures
        if with_longwave:
            t_eq_win = np.array(
                [t_dry_bulb + del_t_eq_lw * (1 - sunblind_in[:, i]) for i in range(n)]
            ).T
            t_eq_wall = np.array(
                [t_dry_bulb + del_t_eq_lw[:, i] + del_t_eq_sw[:, i] for i in range(n)]
            ).T
        else:
            t_eq_win = np.array([t_dry_bulb for i in range(n)]).T
            t_eq_wall = np.array([t_dry_bulb + del_t_eq_sw[:, i] for i in range(n)]).T

        # Compute equivalent air temperature
        t_eq_air = (
            np.dot(t_eq_wall, wf_wall) + np.dot(t_eq_win, wf_win) + t_ground * wf_ground
        )

        # Return result
        return t_eq_air

    def _solar_radiation(
        self, albedo=0.2, time_zone=1, altitude=0, location=(49.5, 8.5)
    ):
        """
        Calculates solar radiation on tilted surface

        corresponds to function calc_sun_rad from weather

        Parameters
        ----------
        albedo
        time_zone
        altitude
        location

        Returns
        -------

        """
        #  FIXME: Deal with input values (to weather / project?)
        timesteps = 60 * 60 * 24
        dt = 3600
        initial_time = 0

        #  Get beta angle
        beta = self.thermal_zone.model_attr.tilt_facade
        gamma = self.thermal_zone.model_attr.orientation_facade

        #  Calculate gamma angle
        #  TEASER definition
        #  orientation_facade: list of floats[degree]
        #         Orientation of facades(Azimuth).
        #         0 - North
        #         90 - East
        #         180 - South
        #         270 - West
        #   TEASER: [180.0, -1, 0.0, -2, 90.0, 270.0]
        #   South, horizontal, North, ground, east, west
        #  VDI: [-180, -90, 0, 90, 0, 0],  # north, east, south, west,
        #  horizontal

        #  Recalculate to VDI core azimuth usage
        for i in range(len(gamma)):
            angle = gamma[i]
            if angle == -1 or angle == -2:
                gamma[i] = 0.0
            else:
                gamma[i] = angle - 180

        # Get weather data
        # TODO: Check weather
        direct_rad = self.weather_data.weather_df["direct_radiation"]
        diffuse_rad = self.weather_data.weather_df["diffuse_radiation"]

        geometry = self.get_geometry(
            initial_time=initial_time,
            dt=dt,
            time_zone=time_zone,
            location=location,
            altitude=altitude,
        )

        #  Extract geometry values
        omega = geometry["omega"]
        delta = geometry["delta"]
        theta_z = geometry["theta_z"]
        airmass = geometry["airmass"]
        gon = geometry["gon"]

        # iterate over all surfaces (given in beta/gamma)
        results = []
        for i in range(len(gamma)):
            # compute incidence angle on each surface
            theta = self.get_incidence_angle(
                beta=beta[i], gamma=gamma[i], phi=location[0], omega=omega, delta=delta
            )
            theta = theta[1]  # cos_theta is not required

            # compute radiation on tilted surface for each surface
            radiation = self.get_rad_on_tilted_surface(
                theta=theta,
                theta_z=theta_z,
                beam_rad=direct_rad,
                diffuse_rad=diffuse_rad,
                airmass=airmass,
                extra_terr_irr=gon,
                beta=beta[i],
                albedo=albedo,
            )

            results.append(radiation)

        # return radiation on each surface
        return np.array(results)

    def get_geometry(
        self,
        initial_time,
        dt,
        time_zone=1,
        location=(50.76, 6.07),
        altitude=0,
    ):
        """
        This function computes hour angle, declination, zenith angle of the sun
        and solar azimuth angle for a given location and time.

        The implemented equations can be found in:
        Duffie, Beckman - Solar Engineering of Thermal Processes, 2013 (4th ed.)

        Parameters
        ----------
        initial_time : integer
            Time passed since January 1st, 00:00:00 in seconds
        dt : integer
            Time between two consecutive time steps in seconds
        timesteps : integer
            Number of investigated / requested time steps
        time_zone : integer, optional
            Shift between the location's time and GMT in hours. CET would be 1.
        location : tuple, optional
            (latitude, longitude) of the simulated system's position. Standard
            values (50.76, 6.07) represent Aachen, Germany.
        altitude : float, optional
            The locations altitude in meters

        Returns
        -------
        res: pandas.DataFrame
            Contains results
            (omega: Hour angle. The angular displacement of the sun east or west of the
                local meridian due to rotation of the earth on its axis at 15 degrees
                per hour; morning negative, afternoon positive
            delta: Declination. The angular position of the sun at solar noon (i.e., when
                the sun is on the local meridian) with respect to the plane of the
                equator, north positive; −23.45 <= delta <= 23.45
            theta_z: Zenith angle. The angle between the vertical and the line to the sun,
                that is, the angle of incidence of beam radiation on a horizontal
                surface; 0 <= theta_z <= 90
            airmass
            gon)

        """
        #  TODO: Add missing explanations to docstring

        timesteps = self.stoptime / self.interval

        # Define pi
        pi = math.pi

        # Notice:
        # All inputs and outputs are given/expected in degrees. For the
        # computation, radians are required. Angles are converted from degrees to
        # radians via np.radians(angle). The resulting radian value is noted with
        # an R-suffix. Converting radian values to degrees is done via
        # np.rad2deg(angleR).
        # This conversion can also be done by multiplying/dividing with 180°/pi

        # Split location into latitude (phi) and longitude (lambda).
        (latitude, longitude) = location

        # Create time array
        time = (np.linspace(0, timesteps - 1, num=timesteps)) * dt + initial_time

        #  Determine the day's number and standard time
        #  (neglect daylight saving)
        number_day = time / (3600 * 24)
        standard_time = time / 3600 - np.floor(number_day) * 24

        # Equation 1.4.2, page 9
        b_param = 360 / 365.26 * number_day
        br_param = np.radians(b_param)
        #  Compute abbreviations for e_param and extraterrestrial irradiation
        #  (gon)
        cos_b = np.cos(br_param)
        sin_b = np.sin(br_param)
        cos_b_2 = np.cos(2 * br_param)
        sin_b_2 = np.sin(2 * br_param)

        # Convert local time into solar time
        # Equation 1.5.3, page 11
        e_param = (
            229.2
            / 60
            * (
                0.000_075
                + 0.001_868 * cos_b
                - 0.032_077 * sin_b
                - 0.014_615 * cos_b_2
                - 0.040_890 * sin_b_2
            )
        )

        # Compute standard meridian
        # Footnote 5 of chapter 1. Can be found on page 11.
        lambda_standard = time_zone * 15

        # Compute solar time
        # Equation 1.5.2, page 11 (conversion to hours instead of minutes)
        solar_time = (
            standard_time + 4 * (longitude - lambda_standard) / 60 + e_param
        ) - 0.5

        # Hour angle
        # The angular displacement of the sun east or west of the local meridian
        # due to rotation of the earth on its axis at 15 degrees per hour; morning
        # negative, afternoon positive
        # Confirm page 13
        omega = 360 / 24 * (solar_time - 12)
        # Ensure: -180 <= omega <= 180
        omega[omega < -180] = omega[omega < -180] + 360
        omega[omega > 180] = omega[omega > 180] - 360
        omega_r = np.radians(omega)

        # Declination
        # The angular position of the sun at solar noon (i.e., when the sun is on
        # the local meridian) with respect to the plane of the equator, north
        # positive; −23.45 <= delta <= 23.45
        # Equation 1.6.1a, page 13
        delta = 23.45 * np.sin((284 + number_day) / 365 * 2 * pi)
        delta_r = np.radians(delta)

        # Zenith angle
        # The angle between the vertical and the line to the sun, that is, the
        # angle of incidence of beam radiation on a horizontal surface;
        # 0 <= theta_z <= 90. If theta_z > 90, the sun is below the horizon.
        # Equation 1.6.5 on page 15

        # Introduce abbreviations to improve readability
        latitude_r = math.radians(latitude)
        cos_phi = math.cos(latitude_r)
        sin_phi = math.sin(latitude_r)
        cos_delta = np.cos(delta_r)
        sin_delta = np.sin(delta_r)
        cos_omega = np.cos(omega_r)
        costheta_z = np.maximum(
            0, cos_phi * cos_delta * cos_omega + sin_delta * sin_phi
        )
        theta_zr = np.arccos(costheta_z)
        theta_z = np.rad2deg(theta_zr)

        # Compute airmass
        # Footnote 3 on page 10
        airmass = math.exp(-0.000_118_4 * altitude) / (
            costheta_z + 0.5057 * np.power(96.08 - theta_z, -1.634)
        )

        # Compute extraterrestrial irradiance (gon)
        # Extraterrestrial radiation incident on the plane normal to the radiation
        # on the nth day of the year.
        # Solar constant. Page 6
        gsc = 1367  # W/m2
        # Equation 1.4.1b
        gon = gsc * (
            1.000_110
            + 0.034_221 * cos_b
            + 0.001_280 * sin_b
            + 0.000_719 * cos_b_2
            + 0.000_077 * sin_b_2
        )

        res_data = {
            "omega": omega,
            "delta": delta,
            "theta_z": theta_z,
            "airmass": airmass,
            "gon": gon,
        }

        # This doesn't work as i want yet
        res_idx = np.arange(0, self.stoptime, self.interval)
        res = pd.DataFrame(data=res_data, index=res_idx)

        # Return results
        return res

    def get_incidence_angle(self, beta, gamma, phi, omega, delta):
        """
        Compute the incidence angle on a tilted surface.

        All inputs/outputs are supposed to be in degrees!

        Parameters
        ----------
        beta : float
            Slope, the angle (in degree) between the plane of the surface in
            question and the horizontal. 0 <= beta <= 180. If beta > 90, the
            surface faces downwards.
        gamma : float
            Surface azimuth angle. The deviation of the projection on a horizontal
            plane of the normal to the surface from the local meridian, with zero
            due south, east negative, and west positive.
            -180 <= gamma <= 180
        phi : float
            Latitude. North is positive, south negative. -90 <= phi <= 90
        omega : array_like
            Hour angle. The angular displacement of the sun east or west of the
            local meridian due to rotation of the earth on its axis at 15 degrees
            per hour; morning negative, afternoon positive
        delta : array_like
            Declination. The angular position of the sun at solar noon (i.e., when
            the sun is on the local meridian) with respect to the plane of the
            equator, north positive; −23.45 <= delta <= 23.45

        Returns
        -------
        cos_theta
        theta
        """
        #  Todo: Add missing explanations to docstring

        # Compute incidence angle of beam radiation
        # Transform to radian
        beta_r = math.radians(beta)
        phi_r = math.radians(phi)
        gamma_r = math.radians(gamma)
        delta_r = np.radians(delta)
        omega_r = np.radians(omega)

        # Introduce required abbreviations
        sin_beta = math.sin(beta_r)
        cos_beta = math.cos(beta_r)
        sin_delta = np.sin(delta_r)
        cos_delta = np.cos(delta_r)
        sin_phi = math.sin(phi_r)
        cos_phi = math.cos(phi_r)
        sin_gamma = math.sin(gamma_r)
        cos_gamma = math.cos(gamma_r)
        sin_omega = np.sin(omega_r)
        cos_omega = np.cos(omega_r)

        # Equation 1.6.2, page 14
        cos_theta = np.maximum(
            sin_delta * sin_phi * cos_beta
            - sin_delta * cos_phi * sin_beta * cos_gamma
            + cos_delta * cos_phi * cos_beta * cos_omega
            + cos_delta * sin_phi * sin_beta * cos_gamma * cos_omega
            + cos_delta * sin_beta * sin_gamma * sin_omega,
            0,
        )
        theta_r = np.arccos(cos_theta)
        theta = np.rad2deg(theta_r)

        # Return incidence angle
        return (cos_theta, theta)

    def get_rad_on_tilted_surface(
        self,
        theta,
        theta_z,
        beam_rad,
        diffuse_rad,
        airmass,
        extra_terr_irr,
        beta,
        albedo,
    ):
        """
        Compute the total radiation on a tilted surface.

        Parameters
        ----------
        theta : array_like
            Incidence angle.
        theta_z : array_like
            Zenith angle. The angle between the vertical and the line to the sun,
            that is, the angle of incidence of beam radiation on a horizontal
            surface; 0 <= theta_z <= 90
        beam_rad : array_like
            The solar radiation received from the sun without having been
            scattered by the atmosphere (also often named direct radiation)
        diffuse_rad : array_like
            The solar radiation received from the sun after its direction has been
            changed by scattering by the atmosphere.
        airmass : array_like
            The ratio of the mass of atmosphere through which beam radiation
            passes to the mass it would pass through if the sun were at the zenith.
            Thus at sea level ``m=1`` when the sun is at the zenith and ``m=2``
            for a zenith angle ``theta_z=60`` degrees.
        extra_terr_irr : array_like
            Extraterrestrial radiation incident on the plane normal to the
            radiation on the nth day of the year.
        beta : float
            Slope, the angle (in degree) between the plane of the surface in
            question and the horizontal. 0 <= beta <= 180. If beta > 90, the
            surface faces downwards.
        albedo : float
            Ground reflectance. 0 <= albedo <= 1
        """
        # Model coefficients
        # Table 6, in Perez et al - 1990 - Modeling daylight availability and
        # irradiance components from direct and global irradiance.
        # Solar Energy, Vol. 44, No. 5, pp. 271-289
        # Values with increased accuracy can be found in the EnergyPlus
        # engineering reference (Table 22, Fij Factors as a Function of Sky
        # Clearness Range, page 147)

        f_coeff = np.array(
            [
                [
                    -0.008_311_7,
                    0.587_728_5,
                    -0.062_063_6,
                    -0.059_601_2,
                    0.072_124_9,
                    -0.022_021_6,
                ],
                [
                    0.129_945_7,
                    0.682_595_4,
                    -0.151_375_2,
                    -0.018_932_5,
                    0.065_965,
                    -0.028_874_8,
                ],
                [
                    0.329_695_8,
                    0.486_873_5,
                    -0.221_095_8,
                    0.055_414,
                    -0.063_958_8,
                    -0.026_054_2,
                ],
                [
                    0.568_205_3,
                    0.187_452_5,
                    -0.295_129,
                    0.108_863_1,
                    -0.151_922_9,
                    -0.013_975_4,
                ],
                [
                    0.873_028,
                    -0.392_040_3,
                    -0.361_614_9,
                    0.225_564_7,
                    -0.462_044_2,
                    0.001_244_8,
                ],
                [
                    1.132_607_7,
                    -1.236_728_4,
                    -0.411_849_4,
                    0.287_781_3,
                    -0.823_035_7,
                    0.055_865_1,
                ],
                [
                    1.060_159_1,
                    -1.599_913_7,
                    -0.358_922_1,
                    0.264_212_4,
                    -1.127_234,
                    0.131_069_4,
                ],
                [
                    0.677_747,
                    -0.327_258_8,
                    -0.250_428_6,
                    0.156_131_3,
                    -1.376_503_1,
                    0.250_621_2,
                ],
            ]
        )

        # Compute a and b (page 281, below equation 9)
        theta_r = np.radians(theta)
        theta_zr = np.radians(theta_z)
        costheta_z = np.cos(theta_zr)
        cos_theta = np.cos(theta_r)
        a = np.maximum(0, cos_theta)
        b = np.maximum(0.087, costheta_z)

        # Compute epsilon (the sky's clearness)
        # Introduce variables and compute third power of theta_zr
        kappa = 1.041
        theta_zrto3 = np.power(theta_zr, 3)

        # Compute normal incidence direct irradiance
        irr = beam_rad / b
        # Prevent division by zero
        temp = np.zeros_like(theta)  # All inputs should have this length!
        temp[diffuse_rad > 0] = (
            1.0 * irr[diffuse_rad > 0] / diffuse_rad[diffuse_rad > 0]
        )
        # equation 1 on p. 273 in Perez et al - 1990
        epsilon = (1 + temp + kappa * theta_zrto3) / (1 + kappa * theta_zrto3)

        # Determine clear sky category
        # table 1 on page 273 in Perez et al - 1990
        # Note: As this value is used to get data from f_coeff, the
        # implemented categories range from 0 to 7 instead from 1 to 8
        eps_category = np.zeros_like(epsilon, dtype=int)
        eps_category[(epsilon >= 1.065) & (epsilon < 1.23)] = 1
        eps_category[(epsilon >= 1.230) & (epsilon < 1.50)] = 2
        eps_category[(epsilon >= 1.500) & (epsilon < 1.95)] = 3
        eps_category[(epsilon >= 1.950) & (epsilon < 2.80)] = 4
        eps_category[(epsilon >= 2.800) & (epsilon < 4.50)] = 5
        eps_category[(epsilon >= 4.500) & (epsilon < 6.20)] = 6
        eps_category[epsilon >= 6.200] = 7

        # Compute delta (the sky's brightness)
        # equation 2 on page 273 in Perez et al - 1990
        delta = diffuse_rad * airmass / extra_terr_irr

        # Compute f1_par (circumsolar brightening coefficient) and f2_par (horizon
        # brightening coefficient)
        # Below table 6 on page 282 in Perez et al - 1990
        # According to Duffie and Beckman (4th edition, page 94, equation 2.16.12),
        # f1_par is supposed to be greater or equal to 0
        f1_par = np.maximum(
            f_coeff[eps_category, 0]
            + f_coeff[eps_category, 1] * delta
            + f_coeff[eps_category, 2] * theta_zr,
            0,
        )

        f2_par = (
            f_coeff[eps_category, 3]
            + f_coeff[eps_category, 4] * delta
            + f_coeff[eps_category, 5] * theta_zr
        )

        # Compute diffuse radiation on tilted surface
        # Equation 9 on page 281 in Perez et al - 1990
        beta_r = math.radians(beta)
        cos_beta = math.cos(beta_r)
        sin_beta = math.sin(beta_r)
        diff_rad_tilt_surface = diffuse_rad * (
            (1 - f1_par) * (1 + cos_beta) / 2 + f1_par * a / b + f2_par * sin_beta
        )

        # Compute the influence of beam radiation and reflected radiation
        # Equation 2.15.1 in Duffie and Beckman (4th edition, page 89)
        # Compute direct radiation on tilted surface
        # Equation 1.8.1 in Duffie and Beckman (4th edition, page 24)
        # We divide by b instead of costheta_z to prevent division by 0
        # Direct radiation on a tilted surface is always positive, therefore use
        # ``a`` instead of cos_theta
        dir_rad_tilt_surface = beam_rad * a / b

        # Compute reflected total radiation
        # Equation 2.15.1 in Duffie and Beckman (4th edition, page 89)
        # Notice: We changed the proposed nomenclature. rhoG is written as albedo.
        # Total solar radiation is computed as sum of beam and diffuse radiation.
        # See page 10 in Duffie and Beckman (4th edition)
        total_sol_rad = beam_rad + diffuse_rad
        refl_rad_tilt_surface = total_sol_rad * albedo * (1 - cos_beta) / 2

        total_rad_tilt_surface = (
            diff_rad_tilt_surface + dir_rad_tilt_surface + refl_rad_tilt_surface
        )

        # Return total radiation on a tilted surface
        return total_rad_tilt_surface

    def simulate(self):
        """Simulates VDI 6007 with hourly timestep for given thermal_zone

        corresponds to function: calc_reduced_order_model from
        simulation_vdi_6007

        Returns
        -------
        res_tuple : tuple (of np.arrays)
            Result tuple (t_indoor, q_heat_cool)
            First entry:
            t_indoor : np.array
                Indoor air temperature in degree Celsius per timestep
            Second entry:
            q_heat_cool : np.array
                Array with heating/cooling values in Watt (positiv: heating;
                negative: cooling)
            if self.debug is True, there is a third output:
            data_debug : pandas.DataFrame
                Additional result data that hopefully helps with debugging
        """

        #  Get building parameters
        r1_iw = self.thermal_zone.model_attr.r1_iw
        c1_iw = self.thermal_zone.model_attr.c1_iw
        area_iw = self.thermal_zone.model_attr.area_iw
        r_rest_ow = self.thermal_zone.model_attr.r_rest_ow
        r1_ow = self.thermal_zone.model_attr.r1_ow
        c1_ow = self.thermal_zone.model_attr.c1_ow
        area_ow = self.thermal_zone.model_attr.outer_wall_areas
        window_areas = self.thermal_zone.model_attr.window_areas
        transparent_areas = self.thermal_zone.model_attr.transparent_areas
        volume = self.thermal_zone.volume
        density_air = self.thermal_zone.density_air
        heat_capac_air = self.thermal_zone.heat_capac_air
        ratio_conv_rad_inner_win = self.thermal_zone.model_attr.ratio_conv_rad_inner_win
        weighted_g_value = self.thermal_zone.model_attr.weighted_g_value
        alpha_comb_inner_iw = self.thermal_zone.model_attr.alpha_comb_inner_iw
        alpha_comb_inner_ow = self.thermal_zone.model_attr.alpha_comb_inner_ow
        alpha_wall = (
            self.thermal_zone.model_attr.alpha_comb_outer_ow
            * self.thermal_zone.model_attr.area_ow
        )

        area_win_tot = sum(window_areas)
        area_o_tot = sum(area_ow)
        area_ar = [area_o_tot, area_win_tot, area_iw]

        r_rest_ow = r_rest_ow + 1 / alpha_wall

        #  Get weather temperature of weather in Kelvin
        self.sim_vars["outdoor_temp"] = self.weather_data.weather_df["air_temp"]

        # #  Get weather direct_radiation
        # direct_radiation = self.weather_data.direct_radiation
        # diffuse_ratiation = self.weather_data.diffuse_radiation

        #  Calculate solar_rad_in with weather
        #  Todo: Set further inputs for _solar_radiation()?
        #  e.g. albedo=0.2, time_zone=1, altitude=0, location=(49.5, 8.5)

        #  Calculate equal_air_temp
        # self.equal_air_temp = self._eq_air_temp(h_sol=self.solar_rad_in)

        #  Get ventilation rate
        #  Todo: Replace dummy ventilation rate value

        #  Get internal gains
        #  Todo: Replae dummy value for internal gains with bound. conditions
        # self.internal_gains = np.zeros(timesteps) + 200

        #  Radiative heat transfer coefficient between inner and outer walls
        #  in W/m2K
        self.sim_vars["alpha_rad"] = self.thermal_zone.model_attr.alpha_rad_inner_mean

        #  convective heat entry from solar irradiation
        for i in range(len(transparent_areas)):
            self.sim_vars[f"e_solar_conv_{i}"] = 0

        for i in range(len(transparent_areas)):
            self.sim_vars[f"e_solar_conv_{i}"] = (
                self.sim_vars[f"solar_rad_in_{i}"]
                * ratio_conv_rad_inner_win
                * weighted_g_value
                * transparent_areas[i]
            )

        e_solar_conv = []
        for i in range(len(transparent_areas)):
            e_solar_conv.append(f"e_solar_conv_{i}")
        self.sim_vars["q_solar_conv"] = self.sim_vars[e_solar_conv].sum(axis=1)

        # splitters:
        # on each splitter: one output goes to outer wall, one goes to inner
        # wall therefore dimension is 2 if inner walls exist => 2 outgoing
        # signals
        split_fac_solar = self.calc_splitfactors(
            len(area_ow), area_ar, area_ow, window_areas
        )

        # therm. splitter solar radiative:
        for i in range(len(transparent_areas)):
            self.sim_vars[f"e_solar_rad_{i}"] = 0

        for i in range(len(transparent_areas)):
            self.sim_vars[f"e_solar_rad_{i}"] = (
                self.sim_vars[f"solar_rad_in_{i}"]
                * (ratio_conv_rad_inner_win - 1)
                * weighted_g_value
                * transparent_areas[i]
            )

        for i in range(len(area_ow)):
            self.sim_vars[f"q_solar_rad_iw_{i}"] = 0
            self.sim_vars[f"q_solar_rad_ow_{i}"] = 0

        for i in range(len(area_ow)):
            self.sim_vars[f"q_solar_rad_iw_{i}"] = (
                -self.sim_vars[f"e_solar_rad_{i}"] * split_fac_solar[1, i]
            )
            self.sim_vars[f"q_solar_rad_ow_{i}"] = (
                -self.sim_vars[f"e_solar_rad_{i}"] * split_fac_solar[0, i]
            )

        q_solar_rad_ow = []
        q_solar_rad_iw = []
        for i in range(len(area_ow)):
            q_solar_rad_ow.append(f"q_solar_rad_ow_{i}")
            q_solar_rad_iw.append(f"q_solar_rad_iw_{i}")

        self.sim_vars["q_solar_rad_to_in_wall"] = self.sim_vars[q_solar_rad_iw].sum(
            axis=1
        )
        self.sim_vars["q_solar_rad_to_outer_wall"] = self.sim_vars[q_solar_rad_ow].sum(
            axis=1
        )

        # TODO: What is krad?
        krad = 1

        # therm. splitter loads radiative:
        self.sim_vars["q_loads_rad"] = krad * self.sim_vars["internal_gains_rad"]
        split_fac_loads = self.calc_splitfactors(1, area_ar, [0], [0])

        self.sim_vars["q_loads_to_inner_wall"] = (
            self.sim_vars["q_loads_rad"] * split_fac_loads[1, 0]
        )
        self.sim_vars["q_loads_to_outer_wall"] = (
            self.sim_vars["q_loads_rad"] * split_fac_loads[0, 0]
        )

        # -----------------------Attention revision neccessary!
        # -----------------------Attention revision neccessary!

        #  TODO: Calculate with function call (depending on occupancy)
        # t_set_heating = np.zeros(timesteps) + 273.15 + 21  # in Kelvin

        # whether as self or as

        # t_set_heat_day = \
        #     np.array([18, 18, 18, 18, 18, 18, 21, 21, 21, 21, 21, 21,
        #               21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21,
        #               18]) + 273.15
        # t_set_heating = np.tile(t_set_heat_day, 365)
        # heater_order = np.array([1, 2, 3])
        # cooler_order = np.array([1, 2, 3])

        #  Todo: Move set_temperature values to inputs
        # Define set points for cooling (cooling is disabled for high values)
        #  #-------------------------------------------------------
        # t_set_cooling = np.zeros(timesteps) + 273.15 + 1000  # in Kelvin

        # -----------------------Attention revision neccessary!
        # -----------------------Attention revision neccessary!

        # Initial temperatures
        t_ow_prev = self.initial_outer_wall_temp
        t_iw_prev = self.initial_inner_wall_temp
        t_air_prev = self.initial_air_temp

        dt = 60

        for t in range(0, self.stoptime, self.interval):
            # Common equations
            A = np.zeros((9, 9))
            rhs = np.zeros(A.shape[0])

            # Fill matrix coefficients
            A[0, 0] = c1_ow / dt + 1 / r_rest_ow + 1 / r1_ow
            A[0, 1] = -1 / r1_ow
            A[1, 0] = 1 / r1_ow
            A[1, 1] = (
                -min(area_o_tot, area_iw) * self.sim_vars.at[t, "alpha_rad"]
                - area_o_tot * alpha_comb_inner_ow
                - 1 / r1_ow
            )
            A[1, 3] = min(area_o_tot, area_iw) * self.sim_vars.at[t, "alpha_rad"]
            A[1, 4] = area_o_tot * alpha_comb_inner_ow
            A[1, 8] = 1
            A[2, 2] = c1_iw / dt + 1 / r1_iw
            A[2, 3] = -1 / r1_iw
            A[3, 1] = min(area_o_tot, area_iw) * self.sim_vars.at[t, "alpha_rad"]
            A[3, 2] = 1 / r1_iw
            A[3, 3] = (
                -min(area_o_tot, area_iw) * self.sim_vars.at[t, "alpha_rad"]
                - area_iw * alpha_comb_inner_iw
                - 1 / r1_iw
            )
            A[3, 4] = area_iw * alpha_comb_inner_iw
            A[3, 7] = 1
            A[4, 1] = area_o_tot * alpha_comb_inner_ow
            A[4, 3] = area_iw * alpha_comb_inner_iw
            A[4, 4] = (
                -area_o_tot * alpha_comb_inner_ow
                - area_iw * alpha_comb_inner_iw
                - self.sim_vars.at[t, "vent_rate"] * heat_capac_air * density_air
            )
            A[4, 5] = -1
            A[4, 6] = 1
            A[5, 4] = volume * heat_capac_air * density_air / dt
            A[5, 5] = -1

            # Fill right hand side
            rhs[0] = (
                self.sim_vars.at[t, "equal_air_temp"] / r_rest_ow
                + c1_ow * t_ow_prev / dt
            )
            rhs[1] = (
                -self.sim_vars.at[t, "q_solar_rad_to_outer_wall"]
                - self.sim_vars.at[t, "q_loads_to_outer_wall"]
            )
            rhs[2] = c1_iw * t_iw_prev / dt
            rhs[3] = (
                -self.sim_vars.at[t, "q_solar_rad_to_in_wall"]
                - self.sim_vars.at[t, "q_loads_to_inner_wall"]
            )
            rhs[4] = (
                -self.sim_vars.at[t, "vent_rate"]
                * heat_capac_air
                * density_air
                * self.sim_vars.at[t, "outdoor_temp"]
                - self.sim_vars.at[t, "q_solar_conv"]
                - self.sim_vars.at[t, "internal_gains"]
            )
            rhs[5] = density_air * heat_capac_air * volume * t_air_prev / dt

            # Calculate current time step
            n = int(t / self.interval)
            x = self.calc_timestep(
                A=A,
                rhs=rhs,
                t_set_heating=self.t_set_heating[n],
                t_set_cooling=self.t_set_cooling[n],
                heater_limit=self.heater_limit[n, :],
                cooler_limit=self.cooler_limit[n, :],
                heater_order=self.heater_order,
                cooler_order=self.cooler_order,
            )

            # Retrieve results
            self.sim_vars.at[t, "t_ow"] = x[0]
            self.sim_vars.at[t, "t_owi"] = x[1]
            self.sim_vars.at[t, "t_iw"] = x[2]
            self.sim_vars.at[t, "t_iwi"] = x[3]
            self.sim_vars.at[t, "t_air"] = x[4]
            self.sim_vars.at[t, "q_air"] = x[5]
            self.sim_vars.at[t, "q_air_hc"] = x[6]
            self.sim_vars.at[t, "q_iw_hc"] = x[7]
            self.sim_vars.at[t, "q_ow_hc"] = x[8]

            # Update initial temperatures
            t_ow_prev = x[0]
            t_iw_prev = x[2]
            t_air_prev = x[4]

        # self.indoor_air_temperature = np.array(t_air)
        # self.q_flow_heater_cooler = np.array(q_air_hc)

        data_sim = self.sim_vars

        if self.debug is False:
            return data_sim["t_air"], data_sim["q_air_hc"]
        elif self.debug is True:
            return data_sim

    def calc_splitfactors(self, cols, a_array, a_ext, a_win):
        """
        This function calculates the split factors

        Parameters
        ----------
        cols : int
            Number of orientations
        a_array : list
            [ATotExt, ATotWin]
        a_ext : list
            Vector of exterior wall areas
        a_win : list
            Vector of window areas

        Example
        -------
        >>> # Define areas
        >>> a_ext = [10.5]
        >>> a_win = [0]
        >>> A_int = 75.5
        >>> area_ar = [sum(a_ext), sum(a_win), A_int]
        >>> # Calculate split factors for inner walls and outside walls
        >>> splitFac_IW = _calc_splitfactors(dim, 1, area_ar, [0], [0])
        >>> splitFac_OW = _calc_splitfactors(dim, len(a_ext), area_ar, a_ext,
        a_win)
        """

        a_tot = sum(a_array)  # total area

        rows = sum([1 if a > 0 else 0 for a in a_array])
        rows = len(a_array)

        # Counters
        i = 0  # a_array
        j = 0  # Row
        k = 0  # Column

        result = np.zeros((rows, cols))

        for a in a_array:
            if a > 0:
                k = 0
                if i == 0:
                    for a_wall in a_ext:
                        result[j, k] = (a - a_wall) / (a_tot - a_wall - a_win[k])
                        k += 1
                elif i == 1:
                    for a_wall in a_ext:
                        result[j, k] = (a - a_win[k]) / (a_tot - a_wall - a_win[k])
                        k += 1
                else:
                    for a_wall in a_ext:
                        result[j, k] = a / (a_tot - a_wall - a_win[k])
                        k += 1
                j += 1
            i += 1

        # We suppose that the third row is always 0 (at least in the vdi test cases), so we cut it off
        result = result[:2]

        return result

    def calc_timestep(
        self,
        A,
        rhs,
        t_set_heating=291.15,
        t_set_cooling=300.15,
        heater_limit=[1e10, 1e10, 1e10],
        cooler_limit=[-1e10, -1e10, -1e10],
        heater_order=np.array([1, 2, 3]),
        cooler_order=np.array([1, 2, 3]),
    ):
        """
        Calculate the temperatures and heat flow rate for the current time step

        Parameters
        ----------
        A : 2d array of floats
            Coefficients describing the VDI model
        rhs : Array of floats
            Right hand side of these equations
        t_set_heating : Float (Move to Init?)
            Temperature below which heating demand is computed (in Kelvin)
        t_set_cooling : Float (Move to Init?)
            Temperature above which cooling demand is computed (in Kelvin)
        """
        #  Todo: Correct docstring

        # Calculate without further heat inputs to determine if heating
        # or cooling is needed
        x_noHeat = self._calc_temperature(A, rhs, q_air_fix=0, q_iw_fix=0, q_ow_fix=0)

        if x_noHeat[4] < t_set_heating:
            # Indoor air temperature below heating set temperature

            # Use primary heater
            if np.argmax(heater_order == 1) == 0 and heater_limit[0] > 0:
                result = self.calc_timestep_primary_heater(
                    A, heater_limit, heater_order, rhs, t_set_heating
                )
            # Use secondary heater
            elif np.argmax(heater_order == 1) == 1 and heater_limit[1] > 0:
                result = self.calc_timestep_secondary_heater(
                    A, heater_limit, heater_order, rhs, t_set_heating
                )
            elif np.argmax(heater_order == 1) == 2 and heater_limit[2] > 0:  # no else
                x_heating_1 = self._calc_heatflow(
                    A,
                    rhs,
                    t_air_set=t_set_heating,
                    q_air_fix=0,
                    q_iw_fix=0,
                    q_ow_fix=None,
                )

                if x_heating_1[8] > heater_limit[2]:
                    x_maxheat_1 = self._calc_temperature(
                        A, rhs, q_air_fix=0, q_iw_fix=0, q_ow_fix=heater_limit[2]
                    )

                    if x_maxheat_1[4] < t_set_heating:
                        if np.argmax(heater_order == 2) == 0 and heater_limit[0] > 0:
                            x_heating_2 = self._calc_heatflow(
                                A,
                                rhs,
                                t_air_set=t_set_heating,
                                q_air_fix=None,
                                q_iw_fix=0,
                                q_ow_fix=heater_limit[2],
                            )

                            if x_heating_2[6] > heater_limit[0]:
                                x_maxheat_2 = self._calc_temperature(
                                    A,
                                    rhs,
                                    q_air_fix=heater_limit[0],
                                    q_iw_fix=0,
                                    q_ow_fix=heater_limit[1],
                                )

                                if (
                                    x_maxheat_2[4] < t_set_heating
                                    and heater_limit[1] > 0
                                ):
                                    x_heating_3 = self._calc_heatflow(
                                        A,
                                        rhs,
                                        t_air_set=t_set_heating,
                                        q_air_fix=heater_limit[0],
                                        q_iw_fix=None,
                                        q_ow_fix=heater_limit[2],
                                    )

                                    if x_heating_3[7] > heater_limit[1]:
                                        result = self._calc_temperature(
                                            A,
                                            rhs,
                                            q_air_fix=heater_limit[0],
                                            q_iw_fix=heater_limit[1],
                                            q_ow_fix=heater_limit[2],
                                        )
                                    else:
                                        result = x_heating_3
                                else:
                                    result = x_maxheat_2
                            else:
                                result = x_heating_2
                        elif np.argmax(heater_order == 2) == 1 and heater_limit[1] > 0:
                            x_heating_2 = self._calc_heatflow(
                                A,
                                rhs,
                                t_air_set=t_set_heating,
                                q_air_fix=0,
                                q_iw_fix=None,
                                q_ow_fix=heater_limit[2],
                            )

                            if x_heating_2[7] > heater_limit[1]:
                                x_maxheat_2 = self._calc_temperature(
                                    A,
                                    rhs,
                                    q_air_fix=0,
                                    q_iw_fix=heater_limit[1],
                                    q_ow_fix=heater_limit[2],
                                )

                                if (
                                    x_maxheat_2[4] < t_set_heating
                                    and heater_limit[0] > 0
                                ):
                                    x_heating_3 = self._calc_heatflow(
                                        A,
                                        rhs,
                                        t_air_set=t_set_heating,
                                        q_air_fix=None,
                                        q_iw_fix=heater_limit[1],
                                        q_ow_fix=heater_limit[2],
                                    )

                                    if x_heating_3[6] > heater_limit[0]:
                                        result = self._calc_temperature(
                                            A,
                                            rhs,
                                            q_air_fix=heater_limit[0],
                                            q_iw_fix=heater_limit[1],
                                            q_ow_fix=heater_limit[2],
                                        )
                                    else:
                                        result = x_heating_3
                                else:
                                    result = x_maxheat_2
                            else:
                                result = x_heating_2
                        else:
                            result = x_maxheat_1
                else:
                    result = x_heating_1

        elif x_noHeat[4] > t_set_cooling:
            # Indoor air temperature above cooling set temperature

            verify_argmax = np.argmax(cooler_order == 1)

            if np.argmax(cooler_order == 1) == 0 and cooler_limit[0] < 0:
                x_cooling_1 = self._calc_heatflow(
                    A,
                    rhs,
                    t_air_set=t_set_cooling,
                    q_air_fix=None,
                    q_iw_fix=0,
                    q_ow_fix=0,
                )

                if x_cooling_1[6] < cooler_limit[0]:
                    x_maxcool_1 = self._calc_temperature(
                        A, rhs, q_air_fix=cooler_limit[0], q_iw_fix=0, q_ow_fix=0
                    )

                    if x_maxcool_1[4] > t_set_cooling:
                        if np.argmax(cooler_order == 2) == 1 and cooler_limit[1] < 0:
                            x_cooling_2 = self._calc_heatflow(
                                A,
                                rhs,
                                t_air_set=t_set_cooling,
                                q_air_fix=cooler_limit[0],
                                q_iw_fix=None,
                                q_ow_fix=0,
                            )

                            if x_cooling_2[7] < cooler_limit[1]:
                                x_maxcool_2 = self._calc_temperature(
                                    A,
                                    rhs,
                                    q_air_fix=cooler_limit[0],
                                    q_iw_fix=cooler_limit[1],
                                    q_ow_fix=0,
                                )

                                if (
                                    x_maxcool_2[4] > t_set_cooling
                                    and cooler_limit[2] < 0
                                ):
                                    x_cooling_3 = self._calc_heatflow(
                                        A,
                                        rhs,
                                        t_air_set=t_set_cooling,
                                        q_air_fix=cooler_limit[0],
                                        q_iw_fix=cooler_limit[1],
                                        q_ow_fix=None,
                                    )

                                    if x_cooling_3[8] < cooler_limit[2]:
                                        result = self._calc_temperature(
                                            A,
                                            rhs,
                                            q_air_fix=cooler_limit[0],
                                            q_iw_fix=cooler_limit[1],
                                            q_ow_fix=cooler_limit[2],
                                        )
                                    else:
                                        result = x_cooling_3
                                else:
                                    result = x_maxcool_2
                            else:
                                result = x_cooling_2
                        elif np.argmax(cooler_order == 2) == 2 and cooler_limit[2] < 0:
                            x_cooling_2 = self._calc_heatflow(
                                A,
                                rhs,
                                t_air_set=t_set_cooling,
                                q_air_fix=cooler_limit[0],
                                q_iw_fix=0,
                                q_ow_fix=None,
                            )

                            if x_cooling_2[8] < cooler_limit[2]:
                                x_maxcool_2 = self._calc_temperature(
                                    A,
                                    rhs,
                                    q_air_fix=cooler_limit[0],
                                    q_iw_fix=0,
                                    q_ow_fix=cooler_limit[2],
                                )

                                if (
                                    x_maxcool_2[4] > t_set_cooling
                                    and cooler_limit[1] < 0
                                ):
                                    x_cooling_3 = self._calc_heatflow(
                                        A,
                                        rhs,
                                        t_air_set=t_set_cooling,
                                        q_air_fix=cooler_limit[0],
                                        q_iw_fix=None,
                                        q_ow_fix=cooler_limit[2],
                                    )

                                    if x_cooling_3[7] < cooler_limit[1]:
                                        result = self._calc_temperature(
                                            A,
                                            rhs,
                                            q_air_fix=cooler_limit[0],
                                            q_iw_fix=cooler_limit[1],
                                            q_ow_fix=cooler_limit[2],
                                        )
                                    else:
                                        result = x_cooling_3
                                else:
                                    result = x_maxcool_2
                            else:
                                result = x_cooling_2
                        else:
                            result = x_maxcool_1
                else:
                    result = x_cooling_1

            elif np.argmax(cooler_order == 1) == 1 and cooler_limit[1] < 0:
                x_cooling_1 = self._calc_heatflow(
                    A,
                    rhs,
                    t_air_set=t_set_cooling,
                    q_air_fix=0,
                    q_iw_fix=None,
                    q_ow_fix=0,
                )

                if x_cooling_1[7] < cooler_limit[1]:
                    x_maxcool_1 = self._calc_temperature(
                        A, rhs, q_air_fix=0, q_iw_fix=cooler_limit[1], q_ow_fix=0
                    )

                    if x_maxcool_1[4] > t_set_cooling:
                        if np.argmax(cooler_order == 2) == 0 and cooler_limit[0] < 0:
                            x_cooling_2 = self._calc_heatflow(
                                A,
                                rhs,
                                t_air_set=t_set_cooling,
                                q_air_fix=None,
                                q_iw_fix=cooler_limit[1],
                                q_ow_fix=0,
                            )

                            if x_cooling_2[6] < cooler_limit[0]:
                                x_maxcool_2 = self._calc_temperature(
                                    A,
                                    rhs,
                                    q_air_fix=cooler_limit[0],
                                    q_iw_fix=cooler_limit[1],
                                    q_ow_fix=0,
                                )

                                if (
                                    x_maxcool_2[4] > t_set_cooling
                                    and cooler_limit[2] < 0
                                ):
                                    x_cooling_3 = self._calc_heatflow(
                                        A,
                                        rhs,
                                        t_air_set=t_set_cooling,
                                        q_air_fix=cooler_limit[0],
                                        q_iw_fix=cooler_limit[1],
                                        q_ow_fix=None,
                                    )

                                    if x_cooling_3[8] < cooler_limit[2]:
                                        result = self._calc_temperature(
                                            A,
                                            rhs,
                                            q_air_fix=cooler_limit[0],
                                            q_iw_fix=cooler_limit[1],
                                            q_ow_fix=cooler_limit[2],
                                        )
                                    else:
                                        result = x_cooling_3
                                else:
                                    result = x_maxcool_2
                            else:
                                result = x_cooling_2
                        elif np.argmax(cooler_order == 2) == 2 and cooler_limit[2] < 0:
                            x_cooling_2 = self._calc_heatflow(
                                A,
                                rhs,
                                t_air_set=t_set_cooling,
                                q_air_fix=0,
                                q_iw_fix=cooler_limit[1],
                                q_ow_fix=None,
                            )

                            if x_cooling_2[8] < cooler_limit[2]:
                                x_maxcool_2 = self._calc_temperature(
                                    A,
                                    rhs,
                                    q_air_fix=0,
                                    q_iw_fix=cooler_limit[1],
                                    q_ow_fix=cooler_limit[2],
                                )

                                if (
                                    x_maxcool_2[4] > t_set_cooling
                                    and cooler_limit[0] < 0
                                ):
                                    x_cooling_3 = self._calc_heatflow(
                                        A,
                                        rhs,
                                        t_air_set=t_set_cooling,
                                        q_air_fix=None,
                                        q_iw_fix=cooler_limit[1],
                                        q_ow_fix=cooler_limit[2],
                                    )

                                    if x_cooling_3[6] < cooler_limit[0]:
                                        result = self._calc_temperature(
                                            A,
                                            rhs,
                                            q_air_fix=cooler_limit[0],
                                            q_iw_fix=cooler_limit[1],
                                            q_ow_fix=cooler_limit[2],
                                        )
                                    else:
                                        result = x_cooling_3
                                else:
                                    result = x_maxcool_2
                            else:
                                result = x_cooling_2
                        else:
                            result = x_maxcool_1
                else:
                    result = x_cooling_1

            elif np.argmax(cooler_order == 1) == 2 and cooler_limit[2] < 0:
                x_cooling_1 = self._calc_heatflow(
                    A,
                    rhs,
                    t_air_set=t_set_cooling,
                    q_air_fix=0,
                    q_iw_fix=0,
                    q_ow_fix=None,
                )
                if x_cooling_1[8] < cooler_limit[2]:
                    x_maxcool_1 = self._calc_temperature(
                        A, rhs, q_air_fix=0, q_iw_fix=0, q_ow_fix=cooler_limit[2]
                    )

                    if x_maxcool_1[4] > t_set_cooling:
                        if np.argmax(cooler_order == 2) == 0 and cooler_limit[0] < 0:
                            x_cooling_2 = self._calc_heatflow(
                                A,
                                rhs,
                                t_air_set=t_set_cooling,
                                q_air_fix=None,
                                q_iw_fix=0,
                                q_ow_fix=cooler_limit[2],
                            )

                            if x_cooling_2[6] < cooler_limit[0]:
                                x_maxcool_2 = self._calc_temperature(
                                    A,
                                    rhs,
                                    q_air_fix=cooler_limit[0],
                                    q_iw_fix=0,
                                    q_ow_fix=cooler_limit[2],
                                )

                                if (
                                    x_maxcool_2[4] > t_set_cooling
                                    and cooler_limit[1] < 0
                                ):
                                    x_cooling_3 = self._calc_heatflow(
                                        A,
                                        rhs,
                                        t_air_set=t_set_cooling,
                                        q_air_fix=cooler_limit[0],
                                        q_iw_fix=None,
                                        q_ow_fix=cooler_limit[2],
                                    )

                                    if x_cooling_3[7] < cooler_limit[1]:
                                        result = self._calc_temperature(
                                            A,
                                            rhs,
                                            q_air_fix=cooler_limit[0],
                                            q_iw_fix=cooler_limit[1],
                                            q_ow_fix=cooler_limit[2],
                                        )
                                    else:
                                        result = x_cooling_3
                                else:
                                    result = x_maxcool_2
                            else:
                                result = x_cooling_2
                        elif np.argmax(cooler_order == 2) == 1 and cooler_limit[1] < 0:
                            x_cooling_2 = self._calc_heatflow(
                                A,
                                rhs,
                                t_air_set=t_set_cooling,
                                q_air_fix=0,
                                q_iw_fix=None,
                                q_ow_fix=cooler_limit[2],
                            )

                            if x_cooling_2[7] < cooler_limit[1]:
                                x_maxcool_2 = self._calc_temperature(
                                    A,
                                    rhs,
                                    q_air_fix=0,
                                    q_iw_fix=cooler_limit[1],
                                    q_ow_fix=cooler_limit[2],
                                )

                                if (
                                    x_maxcool_2[4] > t_set_cooling
                                    and cooler_limit[0] < 0
                                ):
                                    x_cooling_3 = self._calc_heatflow(
                                        A,
                                        rhs,
                                        t_air_set=t_set_cooling,
                                        q_air_fix=None,
                                        q_iw_fix=cooler_limit[1],
                                        q_ow_fix=cooler_limit[2],
                                    )

                                    if x_cooling_3[6] < cooler_limit[0]:
                                        result = self._calc_temperature(
                                            A,
                                            rhs,
                                            q_air_fix=cooler_limit[0],
                                            q_iw_fix=cooler_limit[1],
                                            q_ow_fix=cooler_limit[2],
                                        )
                                    else:
                                        result = x_cooling_3
                                else:
                                    result = x_maxcool_2
                            else:
                                result = x_cooling_2
                        else:
                            result = x_maxcool_1
                else:
                    result = x_cooling_1
        else:
            # Indoor air temperature between both set temperature -> no further
            # action required
            result = x_noHeat

        return result

    def calc_timestep_secondary_heater(
        self, A, heater_limit, heater_order, rhs, t_set_heating
    ):
        """Calculate the timestep using the primary heater

                This function is extracted from calc_timestep as an intermediate step during
                refactoring

                Parameters
                ----------
                A : 2d array of floats
                    Coefficients describing the VDI model
                heater_limit: list (of floats)
                    List with heater limit values in Watt
                heater_order : np.array (of int)
                    describes in which order the different heating devices are turned on
                rhs : Array of floats
                    Right hand side of these equations
                t_set_heating : Float
                    Temperature below which heating demand is computed (in Kelvin)

                Returns
                -------
                result : list
                    Result list of timestep calculation
                """

        x_heating_1 = self._calc_heatflow(
            A, rhs, t_air_set=t_set_heating, q_air_fix=0, q_iw_fix=None, q_ow_fix=0
        )
        if x_heating_1[7] > heater_limit[1]:
            x_maxheat_1 = self._calc_temperature(
                A, rhs, q_air_fix=0, q_iw_fix=heater_limit[1], q_ow_fix=0
            )

            if x_maxheat_1[4] < t_set_heating:
                if np.argmax(heater_order == 2) == 0 and heater_limit[0] > 0:
                    x_heating_2 = self._calc_heatflow(
                        A,
                        rhs,
                        t_air_set=t_set_heating,
                        q_air_fix=None,
                        q_iw_fix=heater_limit[1],
                        q_ow_fix=0,
                    )

                    if x_heating_2[6] > heater_limit[0]:
                        x_maxheat_2 = self._calc_temperature(
                            A,
                            rhs,
                            q_air_fix=heater_limit[0],
                            q_iw_fix=heater_limit[1],
                            q_ow_fix=0,
                        )

                        if x_maxheat_2[4] < t_set_heating and heater_limit[2] > 0:
                            x_heating_3 = self._calc_heatflow(
                                A,
                                rhs,
                                t_air_set=t_set_heating,
                                q_air_fix=heater_limit[0],
                                q_iw_fix=heater_limit[1],
                                q_ow_fix=None,
                            )

                            if x_heating_3[8] > heater_limit[2]:
                                result = self._calc_temperature(
                                    A,
                                    rhs,
                                    q_air_fix=heater_limit[0],
                                    q_iw_fix=heater_limit[1],
                                    q_ow_fix=heater_limit[2],
                                )
                            else:
                                result = x_heating_3
                        else:
                            result = x_maxheat_2
                    else:
                        result = x_heating_2
                elif np.argmax(heater_order == 2) == 2 and heater_limit[2] > 0:
                    x_heating_2 = self._calc_heatflow(
                        A,
                        rhs,
                        t_air_set=t_set_heating,
                        q_air_fix=0,
                        q_iw_fix=heater_limit[1],
                        q_ow_fix=None,
                    )

                    if x_heating_2[8] > heater_limit[2]:
                        x_maxheat_2 = self._calc_temperature(
                            A,
                            rhs,
                            q_air_fix=0,
                            q_iw_fix=heater_limit[1],
                            q_ow_fix=heater_limit[2],
                        )

                        if x_maxheat_2[4] < t_set_heating and heater_limit[0] > 0:
                            x_heating_3 = self._calc_heatflow(
                                A,
                                rhs,
                                t_air_set=t_set_heating,
                                q_air_fix=None,
                                q_iw_fix=heater_limit[1],
                                q_ow_fix=heater_limit[2],
                            )

                            if x_heating_3[6] > heater_limit[0]:
                                result = self._calc_temperature(
                                    A,
                                    rhs,
                                    q_air_fix=heater_limit[0],
                                    q_iw_fix=heater_limit[1],
                                    q_ow_fix=heater_limit[2],
                                )
                            else:
                                result = x_heating_3
                        else:
                            result = x_maxheat_2
                    else:
                        result = x_heating_2
                else:
                    result = x_maxheat_1
        else:
            result = x_heating_1
        return result

    def calc_timestep_primary_heater(
        self, A, heater_limit, heater_order, rhs, t_set_heating
    ):
        """Calculate the timestep using the primary heater

        This function is extracted from calc_timestep as an intermediate step during
        refactoring

        Parameters
        ----------
        A : 2d array of floats
            Coefficients describing the VDI model
        heater_limit: list (of floats)
            List with heater limit values in Watt
        heater_order : np.array (of int)
            describes in which order the different heating devices are turned on
        rhs : Array of floats
            Right hand side of these equations
        t_set_heating : Float
            Temperature below which heating demand is computed (in Kelvin)

        Returns
        -------
        result : list
            Result list of timestep calculation
        """

        x_heating_1 = self._calc_heatflow(
            A, rhs, t_air_set=t_set_heating, q_air_fix=None, q_iw_fix=0, q_ow_fix=0
        )
        if x_heating_1[6] > heater_limit[0]:
            x_maxheat_1 = self._calc_temperature(
                A, rhs, q_air_fix=heater_limit[0], q_iw_fix=0, q_ow_fix=0
            )

            if x_maxheat_1[4] < t_set_heating:
                if np.argmax(heater_order == 2) == 1 and heater_limit[1] > 0:
                    x_heating_2 = self._calc_heatflow(
                        A,
                        rhs,
                        t_air_set=t_set_heating,
                        q_air_fix=heater_limit[0],
                        q_iw_fix=None,
                        q_ow_fix=0,
                    )

                    if x_heating_2[7] > heater_limit[1]:
                        x_maxheat_2 = self._calc_temperature(
                            A,
                            rhs,
                            q_air_fix=heater_limit[0],
                            q_iw_fix=heater_limit[1],
                            q_ow_fix=0,
                        )

                        if x_maxheat_2[4] < t_set_heating and heater_limit[2] > 0:
                            x_heating_3 = self._calc_heatflow(
                                A,
                                rhs,
                                t_air_set=t_set_heating,
                                q_air_fix=heater_limit[0],
                                q_iw_fix=heater_limit[1],
                                q_ow_fix=None,
                            )

                            if x_heating_3[8] > heater_limit[2]:
                                result = self._calc_temperature(
                                    A,
                                    rhs,
                                    q_air_fix=heater_limit[0],
                                    q_iw_fix=heater_limit[1],
                                    q_ow_fix=heater_limit[2],
                                )
                            else:
                                result = x_heating_3
                        else:
                            result = x_maxheat_2
                    else:
                        result = x_heating_2
                elif np.argmax(heater_order == 2) == 2 and heater_limit[2] > 0:
                    x_heating_2 = self._calc_heatflow(
                        A,
                        rhs,
                        t_air_set=t_set_heating,
                        q_air_fix=heater_limit[0],
                        q_iw_fix=0,
                        q_ow_fix=None,
                    )

                    if x_heating_2[8] > heater_limit[2]:
                        x_maxheat_2 = self._calc_temperature(
                            A,
                            rhs,
                            q_air_fix=heater_limit[0],
                            q_iw_fix=0,
                            q_ow_fix=heater_limit[2],
                        )

                        if x_maxheat_2[4] < t_set_heating and heater_limit[1] > 0:
                            x_heating_3 = self._calc_heatflow(
                                A,
                                rhs,
                                t_air_set=t_set_heating,
                                q_air_fix=heater_limit[0],
                                q_iw_fix=None,
                                q_ow_fix=heater_limit[2],
                            )

                            if x_heating_3[7] > heater_limit[1]:
                                result = self._calc_temperature(
                                    A,
                                    rhs,
                                    q_air_fix=heater_limit[0],
                                    q_iw_fix=heater_limit[1],
                                    q_ow_fix=heater_limit[2],
                                )
                            else:
                                result = x_heating_3
                        else:
                            result = x_maxheat_2
                    else:
                        result = x_heating_2
                else:
                    result = x_maxheat_1
        else:
            result = x_heating_1

        return result

    def _calc_temperature(self, A, rhs, q_air_fix=0, q_iw_fix=0, q_ow_fix=0):
        """
        Run the model with a fixed convective heating/cooling gain

        Parameters
        ----------
        A : 2d array of floats
            Coefficients describing the VDI model
        rhs : Array of floats
            Right hand side of these equations
        q_hc_fix : Float
            Heating/cooling input into the zone in Watt

        Returns
        -------
        result : numpy.array
            NEEDS CLARIFICATION: In the calc_timestep method, the result was documented
            as
            x = [T_ow, T_owi, T_iw, T_iwi, T_air, Q_air, Q_HC]
            This has length 7
            But the result we get has length 9. My current guess is that in fact the
            result is
            x = [T_ow, T_owi, T_iw, T_iwi, T_air, Q_air, Q_HC_1, Q_HC_2, Q_HC_3]
            which could possibly be the same as
            x = [T_ow, T_owi, T_iw, T_iwi, T_air, Q_air, Q_HC_air, Q_HC_iw, Q_HC_ow]
        """

        # Delete all entries in the final three lines of A:
        A[6, :] = 0
        A[7, :] = 0
        A[8, :] = 0

        # Add Q_HC = q_hc_fix
        A[6, 6] = 1
        A[7, 7] = 1
        A[8, 8] = 1
        rhs[6] = q_air_fix
        rhs[7] = q_iw_fix
        rhs[8] = q_ow_fix

        # Solve updated model
        result = np.linalg.solve(A, rhs)

        # Return results
        return result

    def _calc_heatflow(
        self, A, rhs, t_air_set=293.15, q_air_fix=None, q_iw_fix=None, q_ow_fix=None
    ):
        """
        Run the model with a fixed convective heating/cooling gain

        Parameters
        ----------
        A : 2d array of floats
            Coefficients describing the VDI model
        rhs : Array of floats
            Right hand side of these equations
        t_air_set : Float
            Zone's set temperature in Kelvin

        Returns
        -------
        result : numpy.array
            NEEDS CLARIFICATION: In the calc_timestep method, the result was documented
            as
            x = [T_ow, T_owi, T_iw, T_iwi, T_air, Q_air, Q_HC]
            This has length 7
            But the result we get has length 9. My current guess is that in fact the
            result is
            x = [T_ow, T_owi, T_iw, T_iwi, T_air, Q_air, Q_HC_1, Q_HC_2, Q_HC_3]
            which could possibly be the same as
            x = [T_ow, T_owi, T_iw, T_iwi, T_air, Q_air, Q_HC_air, Q_HC_iw, Q_HC_ow]
        """

        # Delete all entries in the final three lines of A:
        A[6, :] = 0
        A[7, :] = 0
        A[8, :] = 0

        # Add T_air = t_air_set
        A[6, 4] = 1
        rhs[6] = t_air_set

        if q_air_fix == None:
            A[7, 7] = 1
            A[8, 8] = 1
            rhs[7] = q_iw_fix
            rhs[8] = q_ow_fix
        elif q_iw_fix == None:
            A[7, 6] = 1
            A[8, 8] = 1
            rhs[7] = q_air_fix
            rhs[8] = q_ow_fix
        elif q_ow_fix == None:
            A[7, 6] = 1
            A[8, 7] = 1
            rhs[7] = q_air_fix
            rhs[8] = q_iw_fix

        # Solve updated model
        result = np.linalg.solve(A, rhs)

        # Return results
        return result
