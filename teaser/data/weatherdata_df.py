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
            path=None,
            try_format="old"):

        self.path = path
        self.weather_df = None

        if self.path is None:
            index = np.arange(0, 31536000, 3600)
            self.weather_df = pd.DataFrame(index=index)
            self.weather_df["air_temp"] = ""
            self.weather_df["direct_radiation"] = ""
            self.weather_df["diffuse_radiation"] = ""
            self.weather_df["sky_radiation"] = ""
            self.weather_df["earth_radiation"] = ""
        else:
            self.load_weather(path=self.path, try_format=try_format)


    def load_weather(self, path, try_format):
        """This function loads weather data directly from TRY format.

        Sets class attributes with weather data as numpy array or pandas
        series.

        Parameters
        ----------
        path: str
            path of teaserXML file
        try_format: str
            Format of TRY file {"old", "new"}

        """

        if try_format == "old":
            skip = 35
        elif try_format == "new":
            skip = 33

        weather_data = pd.read_csv(
            path,
            comment="*",
            delim_whitespace=True,
            skiprows=skip,
            encoding="ISO 8859-1",
            usecols=["t", "B", "D", "A", "E"],
            )

        index = np.arange(0, 31536000, 3600)
        self.weather_df = pd.DataFrame(index=index)
        self.weather_df["air_temp"] = weather_data["t"]
        self.weather_df["direct_radiation"] = weather_data["B"]
        self.weather_df["diffuse_radiation"] = weather_data["D"]
        self.weather_df["sky_radiation"] = weather_data["A"]
        self.weather_df["earth_radiation"] = weather_data["E"]


    def reindex_weather_df(self, format):
        """Reindex weather_df DataFrame for given timestep
           and interpolate unknown values

        Parameters
        ----------
        timestep: str
            Desired timestep
            {"minutes", "seconds"}

        """

        if format == "minutes":
            timestep = 60
        elif format == "seconds":
            timestep = 1
        else:
            raise ValueError("The format can either be 'minutes' or 'seconds'")

        idx_new = np.arange(0, 31536000, timestep)

        empty = False
        if not np.any(self.weather_df):
            empty = True

        self.weather_df = self.weather_df.reindex(idx_new)
        if not empty:
            self.weather_df = self.weather_df.interpolate(method="linear")



