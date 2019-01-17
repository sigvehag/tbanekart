import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import sched, time

### Timing
scheduler = sched.scheduler(time.time, time.sleep)

### Data Import
response = requests.get("https://api.entur.org/anshar/1.0/rest/et?datasetId=RUT")
root = ET.fromstring(response.content)


### Stops Dictionary
quayDict= {
    **dict.fromkeys(["11117", "11115"] , "Storo"),
    **dict.fromkeys(["10681", "10682"], "Bergkrystallen"),
    **dict.fromkeys(["6658", "6659"], "Østerås"),
    **dict.fromkeys(["10421", "10423"], "Mortensrud"),
    **dict.fromkeys(["10330", "10331"], "Ellingsrudåsen"),
    "11135" : "Helsfyr",
    "11411" : "Sognsvann",
    "7257" : "Stortinget",
    "10508" : "Vestli",
    "7319" : "Kolsås",
    "12150" : "Frognerseteren",
    "102017": "Løren"
}

### Parser
def parseAndPrint(sch):
    print("--------------------", datetime.now(), "--------------------")
    trips = root[0][3][1]
    for trip in trips.iter('{http://www.siri.org.uk/siri}EstimatedVehicleJourney'):
        for stop in trip.iter('{http://www.siri.org.uk/siri}EstimatedCall'):        
            for data in stop.iter('{http://www.siri.org.uk/siri}ExpectedDepartureTime'):
                expectedDeparture = data.text
                
                willLeaveIn = 0
                for fmt in ("%Y-%m-%dT%H:%M:%S+01:00", "%Y-%m-%dT%H:%M:%S.%f+01:00"):
                    try:
                        willLeaveIn = datetime.strptime(expectedDeparture, fmt) - datetime.now()
                    except ValueError:
                        pass
                if willLeaveIn.total_seconds() > 0 and willLeaveIn.total_seconds() < 300:
                    line ="Kunne ikke finne linje"
                    stopName ="Kunne ikke finne stopp"
                    try:
                        line = trip.find('{http://www.siri.org.uk/siri}LineRef').text
                        stopName = stop.find('{http://www.siri.org.uk/siri}StopPointRef').text
                    except AttributeError:
                        pass
                    
                    try:
                        stopName = quayDict[stopName[9:]]
                    except KeyError:
                        pass
                    print(line[9], "will leave", stopName,  "in", willLeaveIn)
                    break
            break
    scheduler.enter(30, 1, parseAndPrint, (sch,))


scheduler.enter(30, 1, parseAndPrint, (scheduler,))
scheduler.run()