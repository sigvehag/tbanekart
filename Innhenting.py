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

# TODO: No need to get value for every parse. Can parse value every 30 seconds, and only update every 2 minutes?


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
lowestRGBSum = 20
lowestRGBValue = 6
frames = int(secondsBetweenCalls * stepsPerSecond * 1.1)

lightValue = np.array([(60, 200, 255), (255, 60, 0), (255, 45, 255), (0, 0, 255), (0, 255, 0), (0,0,0)])

### Matrixes
fadeMatrix = np.zeros((103,3,30))
lightValueMatrix = np.zeros((103,3))
stationDataMatrix = np.zeros((103,4))

### Variables
frameCounter = 0
startTime = 0
root = 0

### Timing
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
def ImportData():
    global root
    response = requests.get("https://api.entur.org/anshar/1.0/rest/et?datasetId=RUT")
    root = ET.fromstring(response.content)

### Parser
def ReadAndParse():
    dataMatrix = np.zeros((103,4))   # Line (dir 1), time (dir 1), Line (dir 2), time (dir 2)
    trips = root[0][3][1]
    for trip in trips.iter('{http://www.siri.org.uk/siri}EstimatedVehicleJourney'):
        line = "Kunne ikke finne linje"
        willLeaveIn = 0
        direction = 1
        vehicleJourneyRef = 0

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
                expectedDeparture = data.text[:19]		
                try:
                    willLeaveIn = (datetime.strptime(expectedDeparture, '%Y-%m-%dT%H:%M:%S') - datetime.now()).total_seconds()
                    willLeaveIn = int(round(willLeaveIn))
                except ValueError:
                    print("Failed parsing time")
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
                        print(stopID)
                        break

                if (direction == 1):
                    if (dataMatrix[stopID,1] == 0): 
                        dataMatrix[stopID,0] = line[9]
                        dataMatrix[stopID,1] = willLeaveIn
                    elif (dataMatrix[stopID,1] > willLeaveIn):
                            dataMatrix[stopID,0] = line[9]
                            dataMatrix[stopID,1] = willLeaveIn
                else:
                    if (dataMatrix[stopID,3] == 0): 
                        dataMatrix[stopID,2] = line[9]
                        dataMatrix[stopID,3] = willLeaveIn
                    elif (dataMatrix[stopID,3] > willLeaveIn):
                        dataMatrix[stopID,2] = line[9]
                        dataMatrix[stopID,3] = willLeaveIn

                break
    return dataMatrix

def ChangeLight():
    global stationDataMatrix
    global fadeMatrix
    global lightValueMatrix
    global frameCounter

    if int(time.time() - startTime) % 300 == 0:
        ImportData()
        print("Imported Data")
        time.sleep(2)

    
    if frameCounter == secondsBetweenCalls * stepsPerSecond:
        CreateMatrix(lightValueMatrix)
    frameCounter += 1
    
    lightValueMatrix = fadeMatrix[frameCounter,:,:]
    i = 0

    while(i<103):
        pixels[i] = (lightValueMatrix[i, 0], lightValueMatrix[i, 1], lightValueMatrix[i, 2])
        i+=1

    pixels.show()


def CreateMatrix(oldColor):
    global stationDataMatrix
    global fadeMatrix
    global frameCounter
    stationDataMatrix = ReadAndParse()
    newColors = CreateColor(stationDataMatrix)
    fadeMatrix = GenerateFadeMatrix(oldColor, newColors)
    frameCounter = 0
    

def CreateColor(dataMatrix):
    percentageValue1 = maxBrightness - ((maxBrightness-minBrightness)/timeToLight) * (dataMatrix[:,1] - secondsBetweenCalls)
    percentageValue2 = maxBrightness - ((maxBrightness-minBrightness)/timeToLight) * (dataMatrix[:,3] - secondsBetweenCalls)
    color1 = lightValue[dataMatrix[:,0].astype(int)-1] * percentageValue1[:, None]
    color2 = lightValue[dataMatrix[:,2].astype(int)-1] * percentageValue2[:, None]
    return np.concatenate((color1.astype(int), color2.astype(int)), axis=1)


def GenerateFadeMatrix(oldColor, newColor):
    stepArray = np.zeros((frames, 103, 3))
    newColor = np.array(newColor)
    oldColor = np.array(oldColor)
    directionOne = np.unique(np.where((newColor[:,0:3]!=[0,0,0])&(newColor[:,3:6]==[0,0,0]))[0])
    directionTwo = np.unique(np.where((newColor[:,3:6]!=[0,0,0])&(newColor[:,0:3]==[0,0,0]))[0])
    directionBoth = np.unique(np.where((newColor[:,0:3]!=[0,0,0]) & (newColor[:,3:6]!=[0,0,0]))[0])
    directionNeither = np.unique(np.where((newColor[:,0:3]==[0,0,0]) & (newColor[:,3:6]==[0,0,0]))[0])

    for index in directionNeither:        
        red_diff = newColor[index,0] - oldColor[index,0]
        green_diff = newColor[index,1] - oldColor[index,1]
        blue_diff  = newColor[index,2] - oldColor[index,2]

        i = 0
        while i < frames:
            stepArray[i,index,0] = oldColor[index,0] + i * 3 * red_diff / frames
            stepArray[i,index,1] = oldColor[index,1] + i * 3 * green_diff / frames
            stepArray[i,index,2] = oldColor[index,2] + i * 3 * blue_diff / frames
            i+=1

    for index in directionOne:        
        red_diff = newColor[index,0] - oldColor[index,0]
        green_diff = newColor[index,1] - oldColor[index,1]
        blue_diff  = newColor[index,2] - oldColor[index,2]

        i = 0
        while i < frames:
            stepArray[i,index,0] = oldColor[index,0] + i * red_diff / frames
            stepArray[i,index,1] = oldColor[index,1] + i * green_diff / frames
            stepArray[i,index,2] = oldColor[index,2] + i * blue_diff / frames
            i+=1
            

    for index in directionTwo:
        red_diff = newColor[index,3] - oldColor[index,0]
        green_diff = newColor[index,4] - oldColor[index,1]
        blue_diff  = newColor[index,5] - oldColor[index,2]

        i = 0
        while i < frames:
            stepArray[i,index,0] = oldColor[index,0] + i * red_diff / frames
            stepArray[i,index,1] = oldColor[index,1] + i * green_diff / frames
            stepArray[i,index,2] = oldColor[index,2] + i * blue_diff / frames
            i+=1
            
    
    for index in directionBoth:    
        red_diffOne = newColor[index,0] - oldColor[index,0]
        green_diffOne = newColor[index,1] - oldColor[index,1]
        blue_diffOne  = newColor[index,2] - oldColor[index,2]
            
        red_diffTwo = newColor[index,3] - oldColor[index,0]
        green_diffTwo = newColor[index,4] - oldColor[index,1]
        blue_diffTwo  = newColor[index,5] - oldColor[index,2]
            
        i = 0
        switch = 0
        while i < frames:
            if switch == 0:
                stepArray[i,index,0] = oldColor[index,0] + i * red_diffOne / frames
                stepArray[i,index,1] = oldColor[index,1] + i * green_diffOne / frames
                stepArray[i,index,2] = oldColor[index,2] + i * blue_diffOne / frames
                if i % 3 == 0:
                    switch = 1
            elif switch == 1:
                stepArray[i,index,0] = oldColor[index,0] + i * red_diffTwo / frames
                stepArray[i,index,1] = oldColor[index,1] + i * green_diffTwo / frames
                stepArray[i,index,2] = oldColor[index,2] + i * blue_diffTwo / frames
                if i % 3 == 0:
                    switch = 0
            i += 1
            

    stepArray[stepArray > 255*maxBrightness] = 255*maxBrightness
    stepArray[stepArray.sum(axis=2) < lowestRGBSum] = [0,0,0]
    stepArray[stepArray < lowestRGBValue] = 0
    return stepArray.astype(int)


def startup():
    en = [94,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,97]
    to = [100,33,34,35,36,37,38,25,24,23,22,21,20,19,18,17,39,40,41,42,43,44,45,46,47,95]
    tre = [96,48,49,50,51,52,53,54,55,56,57,58,59,40,39,17,18,19,20,21,22,23,24,25,38,60,61,62,63,64,65,66,99]
    fire = [98,32,31,30,29,28,27,26,25,24,23,22,21,20,19,18,17,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,101]
    fem = [102,85,84,83,82,81,80,79,78,77,76,75,74,86,87,22,21,20,19,18,17,67,68,69,93,92,91,90,89,88]

    ut = [94,102,103,96,95,97,98,99,100,0,1,2,88,85,84,83,3,89,82,81,33,66,32,48,49,50,51,31,47,4,5,65,64,52,53,46,6,7,80,79,30,8,9,90,10,78,77,34,63,54,55,45,11,56,44,12,13,29,14,91,76,35,62,28,57,43,15,92,75,36,61,58,42,93,74,73,37,86,60,72,38,26,71,25,87,27,24,59,70,69,23,41,40,68,39,16,67,17,22,18,21,19,20]

    ut2 = [94,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,88,89,90,91,92,93,102,103,85,84,83,82,81,80,79,78,77,76,75,74,100,33,34,35,36,37,99,66,65,64,63,62,61,60,38,97,98,32,31,30,29,28,27,26,96,48,49,50,51,52,53,54,55,56,57,58,59,95,47,46,45,44,43,42,41,73,72,71,70,69,68,67,86,87,25,24,23,40,39,17,22,18,21,19,20]

    for i in en:
        pixels[i] = (lightValue[0, 0], lightValue[0, 1], lightValue[0, 2])
        lightValueMatrix[i] = lightValue[0]
        pixels.show()
        time.sleep(.02)

    for i in to:
        pixels[i] = (lightValue[1, 0], lightValue[1, 1], lightValue[1, 2])
        lightValueMatrix[i] = lightValue[1]
        pixels.show()
        time.sleep(.02)

    for i in tre:
        pixels[i] = (lightValue[2, 0], lightValue[2, 1], lightValue[2, 2])
        lightValueMatrix[i] = lightValue[2]
        pixels.show()
        time.sleep(.02)
        
    for i in fire:
        pixels[i] = (lightValue[3, 0], lightValue[3, 1], lightValue[3, 2])
        lightValueMatrix[i] = lightValue[3]
        pixels.show()
        time.sleep(.02)
        
    for i in fem:
        pixels[i] = (lightValue[4, 0], lightValue[4, 1], lightValue[4, 2])
        lightValueMatrix[i] = lightValue[4]
        pixels.show()
        time.sleep(.02)

if __name__ == "__main__":
    # Create Matrix
    ImportData()
    startup()
    CreateMatrix(lightValueMatrix)
    # Create an interval. 
    interval = Interval(1/stepsPerSecond, ChangeLight, args=[])
    print ("Starting Interval, press CTRL+C to stop.")
    interval.start()

    while True:
        try:
            time.sleep(0.1)
        except KeyboardInterrupt:
            print ("Shutting down interval ...")
            interval.stop()
            break

