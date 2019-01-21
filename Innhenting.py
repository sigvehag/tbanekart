# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
import numpy as np
from datetime import datetime
from functools import partial
from threading import Timer
import requests
import sched  # Probably redundant
import time
import csv
import ast
import neopixel
import board

### NeoPixel
pixel_pin = board.D18
num_pixels = 150
ORDER = neopixel.RGB
pixels = neopixel.NeoPixel(pixel_pin,num_pixels,brightness=1,auto_write=False,pixel_order=ORDER)

### Edit these to change light properties
timeToLight = 90
minBrightness = 0.2
maxBrightness = 1
secondsBetweenCalls = 30
stepsPerSecond = 2
frames = secondsBetweenCalls * stepsPerSecond

lightValue = np.array([(50, 200, 255), (200, 95, 25), (125, 25, 200), (0, 60, 150), (10, 230, 70), (0,0,0)])

### Matrixes
fadeMatrix = np.zeros((101,3,30))
lightValueMatrix = np.zeros((101,3))
stationDataMatrix = np.zeros((101,4))

### Timing
# scheduler = sched.scheduler(time.time, time.sleep)
class Interval(object):

    def __init__(self, interval, function, args=[], kwargs={}):
        """
        Runs the function at a specified interval with given arguments.
        """
        self.interval = interval
        self.function = partial(function, *args, **kwargs)
        self.running  = False 
        self._timer   = None 

    def __call__(self):
        """
        Handler function for calling the partial and continuting. 
        """
        self.running = False  # mark not running
        self.start()          # reset the timer for the next go 
        self.function()       # call the partial function 

    def start(self):
        """
        Starts the interval and lets it run. 
        """
        if self.running:
            # Don't start if we're running! 
            return 
            
        # Create the timer object, start and set state. 
        self._timer = Timer(self.interval, self)
        self._timer.start() 
        self.running = True

    def stop(self):
        """
        Cancel the interval (no more function calls).
        """
        if self._timer:
            self._timer.cancel() 
        self.running = False 
        self._timer  = None


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
            quayDict.update(dict.fromkeys(quay, intID))
        except SyntaxError:
            pass
        
        try:
            fork = ast.literal_eval(fork)
            forkDict.update(dict.fromkeys(fork, intID))
        except SyntaxError:
            pass

### Data Import
response = requests.get("https://api.entur.org/anshar/1.0/rest/et?datasetId=RUT")
root = ET.fromstring(response.content)

### Parser
def parseAndReturn():
    dataMatrix = np.zeros((101,4))   # Line (dir 1), time (dir 1), Line (dir 2), time (dir 2)
    #print("--------------------", datetime.now(), "--------------------")
    trips = root[0][3][1]
    for trip in trips.iter('{http://www.siri.org.uk/siri}EstimatedVehicleJourney'):
        line = "Kunne ikke finne linje"
        willLeaveIn = 0
        direction = 1

        try:
            line = trip.find('{http://www.siri.org.uk/siri}LineRef').text
        except AttributeError:
            pass
        
        try:
            direction = int(trip.find('{http://www.siri.org.uk/siri}DirectionRef').text)
        except AttributeError:
            pass
        
        ### All of one lines stops
        stops = trip.find('{http://www.siri.org.uk/siri}EstimatedCalls')
        for stop in stops.iter('{http://www.siri.org.uk/siri}EstimatedCall'):
            stopID = stop.find('{http://www.siri.org.uk/siri}StopPointRef').text 
                   
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
            if willLeaveIn > 0 and willLeaveIn < timeToLight:
                try:
                    stopID = int(quayDict[stopID[9:]])
                except KeyError:
                    try:
                        stopID = int(forkDict[stopID])
                    except KeyError:
                        stopID = "!!!!!" + stopID + "!!!!!"
                        pass

                print("STOPIDDDD", stopID)

                #if (direction == 1):
                if (dataMatrix[stopID][1] == 0): 
                    dataMatrix[stopID][0] = line[9]
                    dataMatrix[stopID][1] = willLeaveIn
                elif (dataMatrix[stopID][1] > willLeaveIn):
                        dataMatrix[stopID][0] = line[9]
                        dataMatrix[stopID][1] = willLeaveIn
                """
                else:
                    if (dataMatrix[stopID][2:4] == [0, 0]): 
                        dataMatrix[stopID][2:4] = [line[9], willLeaveIn]
                    else:
                        if (dataMatrix[stopID][3] > willLeaveIn):
                            dataMatrix[stopID][2:4] = [line[9], willLeaveIn]
                """

                break
    return dataMatrix
            

def changeLight():
    global stationDataMatrix

    print("ran", time.time())
    if (int(round(time.time())) % 1 ==0): #secondsBetweenCalls == 0):
        stationDataMatrix = parseAndReturn()
        newColors = CreateColor(stationDataMatrix[:, 0], stationDataMatrix[:, 1])
        
        i = 0
        while(i<101):
            pixels[i] = newColors[i]
            i+=1
        pixels.show()
        print("-------- Matrix Updated ---------", frames)

"""
    if (int(round(time.time())) % 10 == 0):
        for value in newMatrix:
            print(value[0], "leaves in", value[1], "from", value[2])
"""

def CreateColor(line, stationTime):
    percentageValue = maxBrightness - ((maxBrightness-minBrightness)/timeToLight) * stationTime
    return lightValue[line.astype(int)-1] * percentageValue[:, None]


def findLightStep(oldColor, newColor):
    stepArray = np.array((frames, 3))
    i = 0
    red_diff = newColor[0] - oldColor[0]
    green_diff = newColor[1] - oldColor[1]
    blue_diff  = newColor[2] - oldColor[2]

    while i < frames:
        stepArray[i][0] = oldColor[0] + i * red_diff / frames
        stepArray[i][1] = oldColor[1] + i * green_diff / frames
        stepArray[i][2] = oldColor[2] + i * blue_diff / frames
        i+=1
    
    return stepArray
    


    if (newColor[3]):
        step = (maxBrightness * 255 - minBrightness * 255) / (timeToLight)
        newHalfColor = lightValue[newData[0]-1] * step * (timeToLight - newData[1] / 2)
        newMax = step * (timeToLight - newData[1])
        
        newcolor * (min  + newpercentage)

if __name__ == "__main__":
    # Create an interval. 
    interval = Interval(1, changeLight, args=[])
    print ("Starting Interval, press CTRL+C to stop.")
    interval.start() 

    while True:
        try:
            time.sleep(0.1)
        except KeyboardInterrupt:
            print ("Shutting down interval ...")
            interval.stop()
            break



#scheduler.enter(1, 1, parseAndReturn, (scheduler,))
#scheduler.run()