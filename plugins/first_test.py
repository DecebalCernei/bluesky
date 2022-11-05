from math import radians, cos, sin, asin, sqrt, log10
from operator import is_
from queue import Empty
from random import random, uniform
from xmlrpc.client import FastMarshaller
import numpy as np
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf, navdb  #, settings, sim, scr, tools
import modules.configuration as configuration

conf = configuration.get_conf("plugins/config/communication.conf")

max_distance = int(conf['max_distance'])
mode = str(conf['mode'])


### Initialization function of your plugin. Do not change the name of this
### function, as it is the way BlueSky recognises this file as a plugin.
def init_plugin():
    ''' Plugin initialisation function. '''
    # Instantiate our example entity
    example = Example()



    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'DRONE_COMMUNICATIONS',

        # The type of this plugin. For now, only simulation plugins are possible.
        'plugin_type':     'sim',
        }

    # init_plugin() should always return a configuration dict.
    return config


### Entities in BlueSky are objects that are created only once (called singleton)
### which implement some traffic or other simulation functionality.
### To define an entity that ADDS functionality to BlueSky, create a class that
### inherits from bluesky.core.Entity.
### To replace existing functionality in BlueSky, inherit from the class that
### provides the original implementation (see for example the asas/eby plugin).
class Example(core.Entity):
    ''' Example new entity object for BlueSky. '''
    def __init__(self):
        super().__init__()


    @stack.command
    def scan(self, lat: 'lat', lon: 'lon'):
        # return number of drones near by (no other types of aircraft)
        ''' Scan for drones near by '''
        aircraft = is_aircraft(lat, lon)
        print(aircraft)
        
        # to-do: there could be a station at the same coordinates...
        if len(aircraft) > 0:
            acid = aircraft.pop()
            drones = reachable_drones(acid)
            flag = 'Drone'
        else:
            drones = from_tower(lat, lon)
            flag = 'Station'
        """
        print(f'The reachable drones are:')
        for drone in drones:
            print(traf.id[drone])
        """
        return True, f'Specified {flag} currently has {len(drones)} reachable drones near by.'


    @stack.command
    def ping(self, lat: 'lat', lon: 'lon', acid_receiver: 'acid'):
        # 'ping' a specific drone
        message = True, f'Could not reach {traf.id[acid_receiver]}'
        aircraft = is_aircraft(lat, lon)
        print(aircraft)
        if len(aircraft) > 0:
            acid_sender = aircraft.pop()
            available_drones = reachable_drones(acid_sender)
        else:
            available_drones = from_tower(lat, lon)
        
        if acid_receiver in available_drones:
            if is_drone(traf.type[acid_receiver]) is False:
                message = False, f'Aircraft {traf.id[acid_receiver]} is not a drone'
            else:
                if mode == 'hard_threshold':
                    if hard_threshold():
                        message = True, f'Successfully reached drone {traf.id[acid_receiver]}'
                    else:
                        print('packet loss in transit')
                elif mode == 'cellular':
                    distance = haversine(lon, lat, traf.lon[acid_receiver], traf.lat[acid_receiver])
                    if fspl(distance):
                        message = True, f'Successfully reached drone {traf.id[acid_receiver]}'
                    else:
                        print('packet loss in transit')
        return message


    @stack.command
    def distance(self, lat1:'lat', lon1: 'lon', lat2: 'lat', lon2: 'lon'):
        d = haversine(lon1, lat1, lon2, lat2)
        return True, f'The distance is {d} m'


    @stack.command
    def drone(self, lat:'lat', lon: 'lon'):
        aircrafts = is_aircraft(lat, lon)
        if len(aircrafts) > 0 :
            aircraft = is_aircraft(lat, lon).pop()
            return True, f'The coordinates {lat}, {lon} correspond to the {traf.id[aircraft]} drone!'
        else:
            return True, f'The coordinates {lat}, {lon} do not correspond to a drone'


    @stack.command
    def broadcast(self, lat:'lat', lon: 'lon'):
        aircraft = is_aircraft(lat, lon)
        acid = -1
        if len(aircraft) > 0:
            acid = aircraft.pop()
            first_group = reachable_drones(acid)
        else:
            first_group = from_tower(lat, lon)
        drones = []
        reached = set()
        if acid != -1:
            reached.add(acid)
        for drone in first_group:
            if mode == 'hard_threshold':
                if hard_threshold():
                    drones.append(drone)
                    reached.add(drone)
            elif mode == 'cellular':
                distance = haversine(lon, lat, traf.lon[drone], traf.lat[drone])
                if fspl(distance):
                    drones.append(drone)
                    reached.add(drone)
        while len(drones) != 0:
            drone = drones.pop(0)
            neighbours = reachable_drones(drone)
            for neighbour in neighbours:
                if mode == 'hard_threshold':
                    if hard_threshold():
                        if neighbour not in reached:
                            drones.append(neighbour)
                            reached.add(neighbour)
                elif mode == 'cellular':
                    distance = haversine(traf.lon[drone], traf.lat[drone], traf.lon[neighbour], traf.lat[neighbour])
                    print(f' calling fspl from {traf.id[drone]} to {traf.id[neighbour]}')
                    if fspl(distance):
                        if neighbour not in reached:
                            drones.append(neighbour)
                            reached.add(neighbour) 
        chain = 0
        for i in reached:
            current = haversine(lon, lat, traf.lon[i], traf.lat[i])
            if current > chain:
                chain = current
        return True, f'We arrived {chain} meters away with our message!'



def reachable_drones(drone):
    reachable_aircrafts = []
    reachable_drones = []
    i = 0
    for aircraft in traf.type:
        if traf.id[drone] != traf.id[i]: #don't append itself
            distance = haversine(traf.lon[drone], traf.lat[drone], traf.lon[i], traf.lat[i])
            if distance < max_distance:
                reachable_aircrafts.append(i)
                if is_drone(traf.type[i]):
                    reachable_drones.append(i)
        i += 1
    return reachable_drones


def from_tower(lat, lon):
    reachable_aircrafts = []
    reachable_drones = []
    i = 0
    for aircraft in traf.type:
        distance = haversine(lon, lat, traf.lon[i], traf.lat[i])
        if distance < max_distance:
            reachable_aircrafts.append(i)
            if is_drone(traf.type[i]):
                reachable_drones.append(i)
        i += 1
    return reachable_drones


def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance in meters between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # Radius of earth in kilometers. Use 3956 for miles. Determines return value units.
    return c * r * 1000


def is_drone(aircraft_type):
    """
    Check if specific aircraft is a drone
    """
    drone_types = ['HORSEFLY', 'MAVIC', 'M100', 'M200', 'M600', 'PHAN4', 'MNET', 'AMZN', 'EC35']
    if aircraft_type in drone_types:
        drone = True
    else:
        drone = False
    return drone


def hard_threshold():
    """
    return True if prob is > loss (hard threshold)
    """
    loss = float(conf['packet_loss_prob'])
    success = False
    prob = random()
    if prob > loss:
        success = True
    return success


def fspl(distance):
    """
    Free Space Path Loss

    Indicates The power loss for the radiated signal after it has travelled distance km
    """
    print(f'distance is {distance}')
    max_pathloss = float(conf['max_pathloss_fspl'])
    frequency = float(conf['frequency']) # expressed in GHz
    pathloss = 20 * log10(distance) + 20 * log10(frequency) + 92.45
    success = False
    print(f'pathloss is {pathloss}')
    if pathloss < max_pathloss:
        success = True
    return success


def cpl(altitude, distance):
    """
    Cellular Path Loss 

    As presented in https://ieeexplore.ieee.org/document/7936620 (800 MHz frequency band used)
    """
    max_pathloss = float(conf['max_pathloss_cpl'])
    cellular_frequency = float(conf['cellular_frequency']) #expressed in GHz
    mu = 20 * log10(distance) + 20 * log10(cellular_frequency)
    if altitude < 1.5:
        alpha = 3.7
        beta = -1.3
        sigma = 7.7
    elif altitude < 15:
        alpha = 2.9
        beta = 7.4
        sigma = 6.2
    elif altitude < 15:
        alpha = 2.5
        beta = 20.4
        sigma = 5.2
    elif altitude < 15:
        alpha = 2.1
        beta = 32.8
        sigma = 4.4
    elif altitude < 120:
        alpha = 2.0
        beta = 35.3
        sigma = 3.4
    else:
        """
        Free Space Path Loss for altitudes above 120 meters
        """
        alpha = 2.0
        beta = log10(cellular_frequency)
        sigma = 0

    minus_sigma = 0 - sigma
    pathloss = alpha * 10 * log10(distance) + beta + uniform(minus_sigma, sigma)
    success = False
    if pathloss < max_pathloss:
        success = True
    return success


def is_aircraft(lat, lon):
    result = set()
    x = np.where(traf.lat == lat)
    if len(x[0]) > 0:
        y = np.where(traf.lon == lon)
        result = set(x[0]).intersection(y[0])
    return result