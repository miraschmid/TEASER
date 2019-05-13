"""Module contains a class to load and store weather data from TRY"""
import teaser.logic.utilities as utils
import os
import pandas as pd
import numpy as np


class WeatherDataDF(object):
    """Class for loading and storing weather data from TMY format. #TODO: TMY or TRY?

    This class loads all necessary weather data (e.g. air temperature and solar
    radiation) and stores them into one class attribute to be easy accessible.

    Parameters
    ----------
    path : str
        Path to the weather file.

    Attributes
    ----------
    weather_df: pandas.DataFrame
        Columns:
        Dry bulb air temperature in degree C at 2 m height [degree C]
        Direct horizontal radiation [W/m2]
        Diffuse horizontal radiation [W/m2]
        Radiation of the atmosphere downwards positive [W/m2]
        Radiation of the earth upwards negative [W/m2]

    """

    def __init__(
            self,
            path=None):

        self.path = path
        self.weather_df = None

        if self.path is None:
            index = np.arange(0, 31536000, 3600)
            self.weather_df = pd.DataFrame(index=index)
            self.weather_df["air_temp[degC]"] = ""
            self.weather_df["direct_radiation[W/m2]"] = ""
            self.weather_df["diffuse_radiation[W/m2]"] = ""
            self.weather_df["sky_radiation[W/m2]"] = ""
            self.weather_df["earth_radiation[W/m2]"] = ""
        else:
            self.load_weather(path=self.path)


    def load_weather(self, path):
        """This function loads weather data directly from TRY format.

        Sets class attributes with weather data as numpy array or pandas
        series.

        Parameters
        ----------
        path: string
            path of teaserXML file

        """

        weather_data = np.genfromtxt(
            path,
            skip_header=38,
            usecols=(8, 13, 14, 16, 17),
            encoding="ISO 8859-1")

        index = np.arange(0, 31536000, 3600)
        self.weather_df = pd.DataFrame(index=index)
        self.weather_df["air_temp[degC]"] = weather_data[:, 0]
        self.weather_df["direct_radiation[W/m2]"] = weather_data[:, 1]
        self.weather_df["diffuse_radiation[W/m2]"] = weather_data[:, 2]
        self.weather_df["sky_radiation[W/m2]"] = weather_data[:, 3]
        self.weather_df["earth_radiation[W/m2]"] = weather_data[:, 4]
