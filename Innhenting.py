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


### NeoPixel
import neopixel
import board
pixel_pin = board.D18
num_pixels = 150
ORDER = neopixel.RGB
pixels = neopixel.NeoPixel(pixel_pin, num_pixels, brightness=1, auto_write=False,pixel_order=ORDER)


### Edit these to change light properties
timeToLight = 90
minBrightness = 0.2
maxBrightness = 1
secondsBetweenCalls = 30
stepsPerSecond = 2
frames = secondsBetweenCalls * stepsPerSecond

lightValue = np.array([(60, 200, 255), (255, 60, 0), (170, 30, 170), (0, 0, 255), (0, 255, 0), (0,0,0)])

### Matrixes
fadeMatrix = np.zeros((101,3,30))
lightValueMatrix = np.zeros((101,3))
stationDataMatrix = np.zeros((101,4))

### Variables
frameCounter = 0

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
def GetAndParse():
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

                if (direction == 1):
                    if (dataMatrix[stopID][1] == 0): 
                        dataMatrix[stopID][0] = line[9]
                        dataMatrix[stopID][1] = willLeaveIn
                    elif (dataMatrix[stopID][1] > willLeaveIn):
                            dataMatrix[stopID][0] = line[9]
                            dataMatrix[stopID][1] = willLeaveIn
                else:
                    if (dataMatrix[stopID][3] == 0): 
                        dataMatrix[stopID][2] = line[9]
                        dataMatrix[stopID][3] = willLeaveIn
                    elif (dataMatrix[stopID][3] > willLeaveIn):
                        dataMatrix[stopID][2] = line[9]
                        dataMatrix[stopID][3] = willLeaveIn

                break
    return dataMatrix
            

def changeLight():
    global stationDataMatrix
    global fadeMatrix
    global lightValueMatrix
    global frameCounter

    print("ran", time.time())
    if (int(round(time.time())) %secondsBetweenCalls == 0):
        frameCounter = 0
        stationDataMatrix = GetAndParse()
        newColors = CreateColor(stationDataMatrix)
        fadeMatrix = GenerateFadeMatrix(lightValueMatrix, newColors)
        print(fadeMatrix)
        print("-------- Matrix Updated ---------", frames)
        

    lightValueMatrix = fadeMatrix[:,:,frameCounter]
    i = 0
    
    while(i<101):
        pixels[i] = (int(lightValueMatrix[i, 0]), int(lightValueMatrix[i, 1]), int(lightValueMatrix[i, 2]))
        i+=1
    
    pixels.show()
    frameCounter += 1
        
    
    

"""
    if (int(round(time.time())) % 10 == 0):
        for value in newMatrix:
            print(value[0], "leaves in", value[1], "from", value[2])
"""

def CreateColor(dataMatrix):
    percentageValue1 = maxBrightness - ((maxBrightness-minBrightness)/timeToLight) * dataMatrix[:,1]
    percentageValue2 = maxBrightness - ((maxBrightness-minBrightness)/timeToLight) * dataMatrix[:,3]
    color1 = lightValue[dataMatrix[:,0].astype(int)-1] * percentageValue1[:, None]
    color2 = lightValue[dataMatrix[:,2].astype(int)-1] * percentageValue2[:, None]
    return np.concatenate((color1.astype(int), color2.astype(int)), axis=1)


def GenerateFadeMatrix(oldColor, newColor):
    ### TODO: Write two functions. One for only one metro approaching, one to blink between two
    # Make an if test. If odd number, choose one color, if even choose the other.

    # This is for one color
    stepArray = np.zeros((101, 3, frames))
    print(stepArray)
    
    red_diff = newColor[:,0] - oldColor[:,0]
    green_diff = newColor[:,1] - oldColor[:,1]
    blue_diff  = newColor[:,2] - oldColor[:,2]

    i = 0
    while i < frames:
        stepArray[:,0,i] = oldColor[:,0] + i * red_diff / frames
        stepArray[:,1,i] = oldColor[:,1] + i * green_diff / frames
        stepArray[:,2,i] = oldColor[:,2] + i * blue_diff / frames
        i+=1
    
    return stepArray
    

    """
    if (newColor[3]):
        step = (maxBrightness * 255 - minBrightness * 255) / (timeToLight)
        newHalfColor = lightValue[newData[0]-1] * step * (timeToLight - newData[1] / 2)
        newMax = step * (timeToLight - newData[1])
        
        newcolor * (min  + newpercentage)
    """

if __name__ == "__main__":
    # Create an interval. 
    interval = Interval(0.5, changeLight, args=[])
    print ("Starting Interval, press CTRL+C to stop.")
    interval.start() 

    stationDataMatrix = GetAndParse()
    while True:
        try:
            time.sleep(0.1)
        except KeyboardInterrupt:
            print ("Shutting down interval ...")
            interval.stop()
            break

