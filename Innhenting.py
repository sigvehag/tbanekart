# -*- coding: utf-8 -*-
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import sched, time
import csv
import ast

### Reading stops from csv
with open('stops.csv') as csvfile:
    reader = csv.reader(csvfile)
    next(reader)                                # Skips Header
    quayDict = {}
    forkDict = {}
    for row in reader:
        fork, name, intID, quay = row
        try:
            quay = ast.literal_eval(quay)       # Parses String to list
            quayDict.update(dict.fromkeys(quay, name))
        except SyntaxError:
            pass
        
        try:
            fork = ast.literal_eval(fork)
            forkDict.update(dict.fromkeys(fork, name))
        except SyntaxError:
            pass

### Timing
scheduler = sched.scheduler(time.time, time.sleep)

### Data Import
response = requests.get("https://api.entur.org/anshar/1.0/rest/et?datasetId=RUT")
root = ET.fromstring(response.content)

### Parser
def parseAndPrint(sch):
    print("--------------------", datetime.now(), "--------------------")
    trips = root[0][3][1]
    for trip in trips.iter('{http://www.siri.org.uk/siri}EstimatedVehicleJourney'):
        line = "Kunne ikke finne linje"
        willLeaveIn = 0

        try:
            line = trip.find('{http://www.siri.org.uk/siri}LineRef').text
        except AttributeError:
            pass
        
        ### All of one lines stops
        stops = trip.find('{http://www.siri.org.uk/siri}EstimatedCalls')
        for stop in stops.iter('{http://www.siri.org.uk/siri}EstimatedCall'):
            stopName = stop.find('{http://www.siri.org.uk/siri}StopPointRef').text 
                   
            for data in stop.iter('{http://www.siri.org.uk/siri}ExpectedDepartureTime'):
                willLeaveIn = 0
                expectedDeparture = data.text                
                for fmt in ("%Y-%m-%dT%H:%M:%S+01:00", "%Y-%m-%dT%H:%M:%S.%f+01:00"):
                    try:
                        willLeaveIn = (datetime.strptime(expectedDeparture, fmt) - datetime.now()).total_seconds()
                        willLeaveIn = int(round(willLeaveIn))
                    except ValueError:
                        pass
            
            ### When the next stop is found it prints the info 
            ### and breaks out of the current lines loop
            if willLeaveIn > 0 and willLeaveIn < 90:
                try:
                    stopName = quayDict[stopName[9:]]
                except KeyError:
                    try:
                        stopName = forkDict[stopName]
                    except KeyError:
                        stopName = "!!!!!" + stopName + "!!!!!"
                        pass

                print(line[9], "leaves from", stopName, "in", willLeaveIn)
                break
            
    
    scheduler.enter(30, 1, parseAndPrint, (sch,))


scheduler.enter(1, 1, parseAndPrint, (scheduler,))
scheduler.run()