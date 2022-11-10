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

max_distance_drone = int(conf['max_distance_drone'])
max_distance_station = int(conf['max_distance_station'])
mode = str(conf['mode'])


# Ground stations as id: lat, lon
def load_ground_stations():
    ground_stations = {}
    ground_stations['GS01'] = [44.925955, 7.835697]
    ground_stations['GS02'] = [44.919209, 7.818958]
    ground_stations['GS03'] = [44.913314, 7.801235]
    return ground_stations


# Create a list of available ground stations... In future read from file and maybe integrate navdb
ground_stations = load_ground_stations()


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

    for gs in ground_stations:
        print(f'ground station {gs} has coordinates: {ground_stations.get(gs)[0]}, {ground_stations.get(gs)[1]}')


    @stack.command
    def scan(self, lat: 'lat', lon: 'lon'):
        # return number of drones near by (no other types of aircraft)
        ''' Scan for drones near by '''
        flag, acid = is_aircraft(lat, lon)
        
        drones = reachable_drones(lat, lon)
        ground_stations = reachable_gstations(lat, lon)

        """
        print(f'The reachable drones are:')
        for drone in drones:
            print(traf.id[drone])
        """
        return True, f'Currently has {len(drones)} reachable drones and {len(ground_stations)} ground stations near by.'


    @stack.command
    def ping(self, lat1: 'lat', lon1: 'lon', lat2: 'lat', lon2: 'lon'):
        # 'ping' a specific drone
        message = True, f'Could not reach destination'
        flag1, acid_sender = is_aircraft(lat1, lon1)
        flag2, acid_receiver = is_aircraft(lat2, lon2)
        is_sender_station, sender_station = is_gstation(lat1, lon1)
        is_receiver_station, receiver_station = is_gstation(lat2, lon2)
        available_drones = reachable_drones(lat1, lon1)
        available_gs = reachable_gstations(lat1, lon1)
        destination = 'wrong'
        source = 'wrong'
        if flag1:
            source = 'drone'
        elif is_sender_station:
            source = 'gstation'
        if source == 'wrong':
            message = True, f'Specified sender is neither a drone nor a ground station'
        else:
            if flag2 & (acid_receiver in available_drones):
                destination = 'drone'
            elif is_receiver_station:
                destination = 'gstation'
            if destination in ['drone', 'gstation']:
                if mode == 'hard_threshold':
                    if hard_threshold():
                        if destination == 'drone':
                            message = True, f'Successfully reached drone {traf.id[acid_receiver]}'
                        else:
                            message = True, f'Successfully reached ground station {receiver_station}'
                    else:
                        print('packet loss in transit')
                elif mode == 'free_space':
                    distance = haversine(lon1, lat1, lon2, lat2)
                    if fspl(distance):
                        if destination == 'drone':
                            message = True, f'Successfully reached drone {traf.id[acid_receiver]}'
                        else:
                            message = True, f'Successfully reached ground station {receiver_station}'
                    else:
                        print('packet loss in transit')
                elif mode == 'cellular':
                    distance = haversine(lon1, lat1, lon2, lat2)
                    if source == 'drone':
                        if fspl(distance):
                            if destination == 'drone':
                                message = True, f'Successfully reached drone {traf.id[acid_receiver]}'
                            else:
                                message = True, f'Successfully reached ground station {receiver_station}'
                        else:
                            print('packet loss in transit')
                    else:
                        if destination == 'drone':
                            if cpl(traf.alt[acid_receiver], distance):
                                message = True, f'Successfully reached drone {traf.id[acid_receiver]}'
                            else:
                                print('packet loss in transit')
                        else:
                            if cpl(0, distance):
                                message = True, f'Successfully reached ground station {receiver_station}'
                            else:
                                print('packet loss in transit')
            else:
                message = True, f'Specified destination is neither a drone nor a ground station'
        return message


    @stack.command
    def distance(self, lat1:'lat', lon1: 'lon', lat2: 'lat', lon2: 'lon'):
        d = haversine(lon1, lat1, lon2, lat2)
        return True, f'The distance is {d} m'


    @stack.command
    def drone(self, lat: 'lat', lon: 'lon'):
        flag, aircraft = is_aircraft(lat, lon)
        if flag == True & is_drone(traf.type[aircraft]):
            return True, f'The coordinates {lat}, {lon} correspond to the {traf.id[aircraft]} drone!'
        else:
            return True, f'The coordinates {lat}, {lon} do not correspond to a drone'


    @stack.command
    def altitud(self, acid:'acid'):
        return True, f'altitude of {traf.id[acid]} is {traf.alt[acid]}'


    @stack.command
    def stations(self, lat: 'lat', lon: 'lon'):
        gs = reachable_gstations(lat, lon)
        return True, f'reachable ground stations: {gs}'


    @stack.command
    def broadcast(self, lat:'lat', lon: 'lon'):
        flag, acid = is_aircraft(lat, lon)
        is_sender_station, sender_station = is_gstation(lat, lon)
        arrived_packets = 0
        sent_packets = 0
        if (not flag) and (not is_sender_station):
            return True, f'Specified sender can not communicate with drones \n(HINT: is it a drone or a ground station?)'
        else:
            first_group = reachable_drones(lat, lon) + reachable_gstations(lat, lon)
        nodes = [] 
        reached = set() # all reached nodes
        if acid != -1:
            reached.add(int(acid))
        for node in first_group:
            should_add = False
            # We are dealing with a drone
            print(f'type of node={node} is {type(node)}')
            if type(node) is int:
                 
                distance = haversine(lon, lat, traf.lon[node], traf.lat[node])
                altitude = traf.alt[node]
            # With a ground station
            else:
                lat_gstation, lon_gstation = get_gstation_pos(node)
                distance = haversine(lon, lat, lon_gstation, lat_gstation)
                altitude = 0
            if mode == 'hard_threshold':
                if hard_threshold():
                    should_add = True
                    arrived_packets += 1
                sent_packets += 1
            elif mode == 'cellular':
                if is_sender_station:
                    # The broadcast is launched by a station
                    if cpl(altitude, distance):
                        should_add = True
                else:
                    if fspl(distance):
                        should_add = True
            elif mode == 'free_space':
                # If mode is free_space we use fspl for both station and drones
                if fspl(distance):
                    should_add = True
                    arrived_packets += 1
                sent_packets += 1
            if should_add:
                nodes.append(node)
                reached.add(node)
        while len(nodes) != 0:
            node = nodes.pop(0)
            # Node is a drone
            print(f'type of node={node} is {type(node)}')
            if type(node) is int:
                 
                lat_node = traf.lat[node]
                lon_node = traf.lon[node]
                print(f'node is {traf.id[node]}')
            # Node is a ground station
            else:
                lat_node, lon_node = get_gstation_pos(node)
                print(f'node is {node}')
            neighbours = reachable_drones(lat_node, lon_node) + reachable_gstations(lat_node, lon_node)
            for neighbour in neighbours:
                print(f'neighbour is {neighbour}')
                should_add = False
                # Neighbour is a drone
                print(f'type of neighbour={neighbour} is {type(neighbour)}')
                if type(neighbour) is int:
                     
                    node_is = 'drone'
                    print(f'from {lon_node}, {lat_node} to {traf.lon[neighbour]}, {traf.lat[neighbour]}')
                    distance = haversine(lon_node, lat_node, traf.lon[neighbour], traf.lat[neighbour])
                    altitude = traf.alt[neighbour]
                # Neighbour is a ground station
                else:
                    node_is = 'gstation'
                    lat_neighbour, lon_neighbour = get_gstation_pos(neighbour)
                    distance = haversine(lon_node, lat_node, lon_neighbour, lat_neighbour)
                    altitude = 0
                if mode == 'hard_threshold':
                    if hard_threshold():
                        should_add = True
                        arrived_packets += 1
                    sent_packets += 1
                elif mode == 'cellular':
                    if node_is == 'drone':
                        if fspl(distance):
                            should_add = True
                            arrived_packets += 1
                    else:
                        if cpl(altitude, distance):
                            should_add = True
                            arrived_packets += 1
                    sent_packets += 1
                elif mode == 'free_space':
                    if fspl(distance):
                        should_add = True
                        arrived_packets += 1
                    sent_packets += 1
                
                if should_add:
                    if neighbour not in reached:
                            nodes.append(neighbour)
                            reached.add(neighbour)
        ##############################
        chain = 0
        for i in reached:
            # Node is a drone
            print(f'type of i={i} is {type(i)}')
            if type(i) is int:
                 
                lat_i = traf.lat[i]
                lon_i = traf.lon[i]
            # Node is a ground station
            else:
                print(f'--- STO CHIEDENDO LE COORDINATE DI: {i} ---')
                lat_i, lon_i = get_gstation_pos(i)
            current = haversine(lon, lat, lon_i, lat_i)
            if current > chain:
                chain = current
        print(f'arrived/sent packets: {arrived_packets}/{sent_packets}')
        return True, f'We arrived {chain} meters far with our message!'


def reachable_drones(lat, lon):
    reachable_aircrafts = []
    reachable_drones = []
    i = 0
    flag, acid = is_aircraft(lat, lon)
    for aircraft in traf.type:
        if flag and (traf.id[acid] == traf.id[i]):
            #do not add itself
            pass
        else:
            distance = haversine(lon, lat, traf.lon[i], traf.lat[i])
            if flag:
                max_distance = max_distance_drone
            else:
                max_distance = max_distance_station
            if distance < max_distance:
                reachable_aircrafts.append(i)
                if is_drone(traf.type[i]):
                    reachable_drones.append(i)
        i += 1
    return reachable_drones


def reachable_gstations(lat, lon):
    reachable_gs = []
    for gs in ground_stations:
        should_add = False
        distance = haversine(lon, lat, ground_stations.get(gs)[1], ground_stations.get(gs)[0])
        print(f'distance is {distance}')
        flag, acid = is_aircraft(lat, lon)
        if flag:
            if is_drone(traf.type[acid]) & (distance < max_distance_drone):
                should_add = True
        else:
            if distance < max_distance_station:
                should_add = True
        if distance == 0:
            should_add = False # do not append itself
        if should_add:
            reachable_gs.append(gs)
    return reachable_gs


def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance in meters between two points 
    on the earth (specified in decimal degrees)
    ref: https://stackoverflow.com/questions/4913349/haversine-formula-in-python-bearing-and-distance-between-two-gps-points
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
    print(f'called cpl{altitude}, {distance}')
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
    elif altitude < 30:
        alpha = 2.5
        beta = 20.4
        sigma = 5.2
    elif altitude < 60:
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
    print(f'Pathloss is {pathloss}')
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
    if len(result)>0:
        # Means that is an aircraft, return True and the index
        return True, result.pop()
    else:
        # Not an aircraft
        return False, -1


def is_gstation(lat, lon):
    result = False
    gs = -1
    for gstation in ground_stations:
        if (ground_stations[gstation][0] == lat) & (ground_stations[gstation][1] == lon):
            result = True
            gs = gstation
    return result, gs


def get_gstation_pos(gstation):
    # lat, lon
    return ground_stations[gstation][0], ground_stations[gstation][1]