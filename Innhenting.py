import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime

response = requests.get("https://api.entur.org/anshar/1.0/rest/et?datasetId=RUT")
root = ET.fromstring(response.content)

quayDict= {
    **dict.fromkeys(["11117", "11115"] , "Storo"),
    "11135" : "Helsfyr",
    "10421" : "Mortensrud",
    "11411" : "Sognsvann",
    "7257" : "Stortinget"
}


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
            if willLeaveIn.total_seconds() > 0:
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