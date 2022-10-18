""" First test to display number of drones in an area of 200 meters """
from math import radians, cos, sin, asin, sqrt
from operator import is_
from random import randint
from xmlrpc.client import FastMarshaller
import numpy as np
# Import the global bluesky objects. Uncomment the ones you need
from bluesky import core, stack, traf  #, settings, navdb, sim, scr, tools
max_distance = 2
### Initialization function of your plugin. Do not change the name of this
### function, as it is the way BlueSky recognises this file as a plugin.
def init_plugin():
    ''' Plugin initialisation function. '''
    # Instantiate our example entity
    example = Example()



    # Configuration parameters
    config = {
        # The name of your plugin
        'plugin_name':     'FIRST_TEST',

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

    # You can create new stack commands with the stack.command decorator.
    # By default, the stack command name is set to the function name.
    # The default argument type is a case-sensitive word. You can indicate different
    # types using argument annotations. This is done in the below function:
    # - The acid argument is a BlueSky-specific argument with type 'acid'.
    #       This converts callsign to the corresponding index in the traffic arrays.
    # - The count argument is a regular int.
    @stack.command
    def passengers(self, acid: 'acid', count: int = -1):
        ''' Set the number of passengers on aircraft 'acid' to 'count'. '''
        if count < 0:
            return True, f'Aircraft {traf.id[acid]} currently has {self.npassengers[acid]} passengers on board.'

        self.npassengers[acid] = count
        return True, f'The number of passengers on board {traf.id[acid]} is set to {count}.'


    @stack.command
    def scan(self, acid: 'acid'):
        # return number of drones only near by (no other types of aircraft)
        ''' Scan for drones near by '''
        drones = []
        reachable_drones = []
        i = 0
        master = 0
        for aircraft in traf.type:
            if is_drone(aircraft):
                if traf.id[acid] == traf.id[i]:
                    master = i
                if master != i:
                    distance = haversine(traf.lon[master], traf.lat[master], traf.lon[i], traf.lat[i])
                    # print(f'The drone {traf.id[i]} has distance from ours {distance}')
                    drones.append(i)
                    if distance < max_distance:
                        reachable_drones.append(i)
            i += 1
        return True, f'Drone {traf.id[acid]} currently has {len(drones)} drones near by of which {len(reachable_drones)} are reachable.'


    @stack.command
    def ping(self, acid_sender: 'acid', acid_receiver: 'acid'):
        # 'ping' a specific drone
        message = True, f'Drone {traf.id[acid_sender]} could not reach {traf.id[acid_receiver]}'
        if is_drone(traf.type[acid_sender]) is False:
            message = False, f'Aircraft {traf.id[acid_sender]} is not a drone'
        elif is_drone(traf.type[acid_receiver]) is False:
            message = False, f'Aircraft {traf.id[acid_receiver]} is not a drone'
        else:
            if success_prob() > 0.1:
                message = True, f'Drone {traf.id[acid_sender]} successfully reached drone {traf.id[acid_receiver]}'
            else:
                print('packet loss in transit')
        return message


def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance in kilometers between two points 
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
    return c * r


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


def success_prob():
    """
    return a success probability rate, todo implementation of a smarter protocol
    """
    prob = randint(0, 100) / 100
    return prob