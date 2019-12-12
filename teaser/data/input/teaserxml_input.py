"""OLD! Will be deleted in future version.

This module contains function to load Projects in the proprietary
TEASER file format .tXML
"""

import xml.etree.ElementTree as element_tree
import warnings
from teaser.logic.buildingobjects.building import Building
from teaser.logic.archetypebuildings.bmvbs.office import Office
from teaser.logic.archetypebuildings.bmvbs.singlefamilydwelling import \
    SingleFamilyDwelling
from teaser.logic.archetypebuildings.bmvbs.custom.institute import Institute
from teaser.logic.archetypebuildings.bmvbs.custom.institute4 import Institute4
from teaser.logic.archetypebuildings.bmvbs.custom.institute8 import Institute8
from teaser.logic.buildingobjects.thermalzone import ThermalZone
from teaser.logic.buildingobjects.buildingsystems.buildingahu import\
    BuildingAHU
from teaser.logic.buildingobjects.useconditions import UseConditions
from teaser.logic.buildingobjects.buildingphysics.outerwall import OuterWall
from teaser.logic.buildingobjects.buildingphysics.layer import Layer
from teaser.logic.buildingobjects.buildingphysics.material import Material
from teaser.logic.buildingobjects.buildingphysics.rooftop import Rooftop
from teaser.logic.buildingobjects.buildingphysics.groundfloor import \
    GroundFloor
from teaser.logic.buildingobjects.buildingphysics.innerwall import InnerWall
from teaser.logic.buildingobjects.buildingphysics.ceiling import Ceiling
from teaser.logic.buildingobjects.buildingphysics.floor import Floor
from teaser.logic.buildingobjects.buildingphysics.window import Window
from teaser.logic.buildingobjects.buildingphysics.door import Door


def load_teaser_xml(path, prj):
    """Function to load old XML files into new TEASER classes.

    ATTENTION: This function should only be used to load old .teaserXML files.

    TEASERs internal file format to store information.

    Parameters
    ----------
    path: string
        path of teaserXML file

    prj: Project()
        Teaser instance of Project()


    """

    warnings.warn(
        "This function should only be used to transform old XML files"
        "and will be deleted within the next versions of TEASER")

    version_parse = element_tree.parse(path)
    xml_file = open(path, 'r')
    if bool(version_parse.getroot().attrib) is False:
        warnings.warn("You are using an old version of project XML file")
        import teaser.data.bindings.v_0_3_9.project_bind as pb
        project_bind = pb.CreateFromDocument(xml_file.read())
    elif version_parse.getroot().attrib['version'] == "0.3.9":
        warnings.warn("You are using an old version of project XML file")
        import teaser.data.bindings.v_0_3_9.project_bind as pb
        project_bind = pb.CreateFromDocument(xml_file.read())
    elif version_parse.getroot().attrib['version'] == "0.4":
        warnings.warn("You are using an old version of project XML file")
        import teaser.data.bindings.v_0_4.project_bind as pb
        project_bind = pb.CreateFromDocument(xml_file.read())
    elif version_parse.getroot().attrib['version'] == "0.5":
        warnings.warn("You are using an old version of project XML file")
        import teaser.data.bindings.v_0_5.project_bind as pb
        project_bind = pb.CreateFromDocument(xml_file.read())
    elif version_parse.getroot().attrib['version'] == "0.6":
        import teaser.data.bindings.v_0_6.project_bind as pb
        project_bind = pb.CreateFromDocument(xml_file.read())

    for pyxb_bld in project_bind.Building:
        _load_building(prj=prj, pyxb_bld=pyxb_bld, type="Building",
                       project_bind=project_bind)

    for pyxb_bld in project_bind.Office:
        _load_building(prj=prj, pyxb_bld=pyxb_bld, type="Office",
                       project_bind=project_bind)

    for pyxb_bld in project_bind.Institute:
        _load_building(prj=prj, pyxb_bld=pyxb_bld, type="Institute",
                       project_bind=project_bind)

    for pyxb_bld in project_bind.Institute4:
        _load_building(prj=prj, pyxb_bld=pyxb_bld, type="Institute4",
                       project_bind=project_bind)

    for pyxb_bld in project_bind.Institute8:
        _load_building(prj=prj, pyxb_bld=pyxb_bld, type="Institute8",
                       project_bind=project_bind)

    for pyxb_bld in project_bind.Residential:
        _load_building(prj=prj, pyxb_bld=pyxb_bld, type="Residential",
                       project_bind=project_bind)


def _load_building(prj, pyxb_bld, type, project_bind):
    if type == "Building":
        bldg = Building(prj)

    elif type == "Office":
        bldg = Office(prj)

    elif type == "Institute":

        bldg = Institute(prj)

    elif type == "Institute4":
        bldg = Institute4(prj)

    elif type == "Institute8":
        bldg = Institute8(prj)

    elif type == "Residential":
        bldg = SingleFamilyDwelling(prj)

    bldg.name = pyxb_bld.name
    bldg.street_name = pyxb_bld.street_name
    bldg.city = pyxb_bld.city
    bldg.type_of_building = pyxb_bld.type_of_building
    bldg.year_of_construction = pyxb_bld.year_of_construction
    bldg.year_of_retrofit = pyxb_bld.year_of_retrofit
    bldg.number_of_floors = pyxb_bld.number_of_floors
    bldg.height_of_floors = pyxb_bld.height_of_floors

    if not pyxb_bld.ThermalZone:
        bldg.net_leased_area = pyxb_bld.net_leased_area

    if pyxb_bld.CentralAHU:
        pyxb_ahu = pyxb_bld.CentralAHU
        bldg.central_ahu = BuildingAHU(bldg)

        bldg.central_ahu.heating = pyxb_ahu.heating
        bldg.central_ahu.cooling = pyxb_ahu.cooling
        bldg.central_ahu.dehumidification = pyxb_ahu.dehumidification
        bldg.central_ahu.humidification = pyxb_ahu.humidification
        bldg.central_ahu.heat_recovery = pyxb_ahu.heat_recovery
        bldg.central_ahu.by_pass_dehumidification = \
            pyxb_ahu.by_pass_dehumidification
        bldg.central_ahu.efficiency_recovery = pyxb_ahu.efficiency_recovery

        try:
            if float(project_bind.version) >= 0.5:
                bldg.central_ahu.efficiency_recovery_false = \
                    pyxb_ahu.efficiency_recovery_false
            else:
                bldg.central_ahu.efficiency_recovery_false = \
                    pyxb_ahu.efficiency_revocery_false
        except AttributeError:
            bldg.central_ahu.efficiency_recovery_false = \
                pyxb_ahu.efficiency_revocery_false

        bldg.central_ahu.min_relative_humidity_profile = \
            pyxb_ahu.profile_min_relative_humidity
        bldg.central_ahu.max_relative_humidity_profile = \
            pyxb_ahu.profile_max_relative_humidity
        bldg.central_ahu.v_flow_profile = \
            pyxb_ahu.profile_v_flow
        bldg.central_ahu.temperature_profile = \
            pyxb_ahu.profile_temperature

    for pyxb_zone in pyxb_bld.ThermalZone:

        zone = ThermalZone(bldg)

        zone.name = pyxb_zone.name
        zone.area = pyxb_zone.area
        zone.volume = pyxb_zone.volume
        zone.infiltration_rate = pyxb_zone.infiltration_rate

        zone.use_conditions = UseConditions(zone)

        pyxb_use = pyxb_zone.UseCondition.BoundaryConditions

        zone.use_conditions.typical_length = pyxb_zone.typical_length
        zone.use_conditions.typical_width = pyxb_zone.typical_width

        zone.use_conditions.usage = \
            pyxb_use.usage

        zone.use_conditions.ratio_conv_rad_lighting = \
            pyxb_use.Lighting.ratio_conv_rad_lighting

        zone.use_conditions.set_temp_heat = \
            [pyxb_use.RoomClimate.set_temp_heat, ]
        zone.use_conditions.set_temp_cool = \
            [pyxb_use.RoomClimate.set_temp_cool, ]

        zone.use_conditions.persons = \
            pyxb_use.InternalGains.persons
        zone.use_conditions.persons_profile = \
            pyxb_use.InternalGains.profile_persons
        zone.use_conditions.machines = \
            pyxb_use.InternalGains.machines
        zone.use_conditions.machines_profile = \
            pyxb_use.InternalGains.profile_machines
        zone.use_conditions.lighting_power = \
            pyxb_use.InternalGains.lighting_power
        zone.use_conditions.lighting_profile = \
            pyxb_use.InternalGains.profile_lighting

        zone.use_conditions.min_ahu = \
            pyxb_use.AHU.min_ahu
        zone.use_conditions.max_ahu = \
            pyxb_use.AHU.max_ahu
        zone.use_conditions.with_ahu = \
            pyxb_use.AHU.with_ahu
        zone.use_constant_infiltration = \
            pyxb_use.AHU.use_constant_ach_rate
        zone.base_infiltration = \
            pyxb_use.AHU.base_ach
        zone.max_user_infiltration = \
            pyxb_use.AHU.max_user_ach
        zone.max_overheating_infiltration = \
            pyxb_use.AHU.max_overheating_ach
        zone.max_summer_infiltration = \
            pyxb_use.AHU.max_summer_ach
        zone.winter_reduction_infiltration = \
            pyxb_use.AHU.winter_reduction

        for pyxb_wall in pyxb_zone.OuterWall:
            out_wall = OuterWall(zone)

            set_basic_data_teaser(pyxb_wall, out_wall)
            set_layer_data_teaser(pyxb_wall, out_wall)

        try:
            if float(project_bind.version) >= 0.6:
                for pyxb_wall in pyxb_zone.Door:
                    out_wall = Door(zone)

                    set_basic_data_teaser(pyxb_wall, out_wall)
                    set_layer_data_teaser(pyxb_wall, out_wall)

        except AttributeError:
            pass

        for pyxb_wall in pyxb_zone.Rooftop:
            roof = Rooftop(zone)

            set_basic_data_teaser(pyxb_wall, roof)
            set_layer_data_teaser(pyxb_wall, roof)

            # zone.outer_walls.append(roof)

        for pyxb_wall in pyxb_zone.GroundFloor:
            gr_floor = GroundFloor(zone)

            set_basic_data_teaser(pyxb_wall, gr_floor)
            set_layer_data_teaser(pyxb_wall, gr_floor)

            # zone.outer_walls.append(gr_floor)

        for pyxb_wall in pyxb_zone.InnerWall:
            in_wall = InnerWall(zone)

            set_basic_data_teaser(pyxb_wall, in_wall)
            set_layer_data_teaser(pyxb_wall, in_wall)

            # zone.inner_walls.append(in_wall)

        for pyxb_wall in pyxb_zone.Ceiling:
            ceiling = Ceiling(zone)

            set_basic_data_teaser(pyxb_wall, ceiling)
            set_layer_data_teaser(pyxb_wall, ceiling)

            # zone.inner_walls.append(ceiling)

        for pyxb_wall in pyxb_zone.Floor:
            floor = Floor(zone)

            set_basic_data_teaser(pyxb_wall, floor)
            set_layer_data_teaser(pyxb_wall, floor)

            # zone.inner_walls.append(floor)

        for pyxb_win in pyxb_zone.Window:
            win = Window(zone)

            set_basic_data_teaser(pyxb_win, win)
            set_layer_data_teaser(pyxb_win, win)


def set_basic_data_teaser(pyxb_class, element):
    """Helper function for load_teaser_xml to set the basic data

    Parameters
    ----------
    pyxb_class : PyXBClass
        pyxb class representation of xml

    element : TEASERClass
        teaser class representation of a building element

    """

    if pyxb_class.year_of_construction is not None:
        element.year_of_construction = pyxb_class.year_of_construction
    if pyxb_class.year_of_retrofit is not None:
        element.year_of_retrofit = pyxb_class.year_of_retrofit
    if pyxb_class.construction_type is not None:
        element.construction_type = pyxb_class.construction_type

    element.name = pyxb_class.name
    element.area = pyxb_class.area
    element.tilt = pyxb_class.tilt
    element.orientation = pyxb_class.orientation

    if type(element).__name__ == 'OuterWall' or type(element).__name__ == \
            'Rooftop' or type(element).__name__ == 'Door':

        element.inner_radiation = pyxb_class.inner_radiation
        element.inner_convection = pyxb_class.inner_convection
        element.outer_radiation = pyxb_class.outer_radiation
        element.outer_convection = pyxb_class.outer_convection

    elif type(element).__name__ == 'InnerWall' or type(element).__name__ == \
            'Ceiling' or type(element).__name__ == 'Floor' or type(
                element).__name__ == 'GroundFloor':

        element.inner_radiation = pyxb_class.inner_radiation
        element.inner_convection = pyxb_class.inner_convection

    elif type(element).__name__ == 'Window':

        element.inner_radiation = pyxb_class.inner_radiation
        element.inner_convection = pyxb_class.inner_convection
        element.outer_radiation = pyxb_class.outer_radiation
        element.outer_convection = pyxb_class.outer_convection
        element.g_Value = pyxb_class.g_value
        element.a_conv = pyxb_class.a_conv
        element.shading_g_total = pyxb_class.shading_g_total
        element.shading_max_irr = pyxb_class.shading_max_irr


def set_layer_data_teaser(pyxb_class, element):
    """Helper function for load_teaser_xml to set the layer data

    Parameters
    ----------
    pyxb_class : PyXBClass
        pyxb class representation of xml

    element : TEASERClass
        teaser class representation of a building element

    """
    for pyxb_layer in pyxb_class.Layer:
        layer = Layer(element)

        layer.id = pyxb_layer.id
        layer.thickness = pyxb_layer.thickness

        Material(layer)

        layer.material.name = pyxb_layer.Material.name
        layer.material.density = pyxb_layer.Material.density
        layer.material.thermal_conduc = pyxb_layer.Material.thermal_conduc
        layer.material.heat_capac = pyxb_layer.Material.heat_capac
        layer.material.solar_absorp = pyxb_layer.Material.solar_absorp
        layer.material.ir_emissivity = pyxb_layer.Material.ir_emissivity
