import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime


# Make a get request to get the latest position of the international space station from the opennotify api.
response = requests.get("https://api.entur.org/anshar/1.0/rest/et?datasetId=RUT")
e = ET.fromstring(response.content)
# Print the status code of the response.
# print(e[0][0].tag)

name = ""
dest = ""
expTime = ""
reqTime = 0
shouldBreak = False

for data in e[0][3][1][1:]:
    for subdata in data:
        if subdata.tag == "{http://www.siri.org.uk/siri}EstimatedCalls":
            for estimatedCall in subdata:
                for metaData in estimatedCall:
                    shouldBreak = False
                    if (
                        metaData.tag
                        == "{http://www.siri.org.uk/siri}ExpectedDepartureTime"
                    ):
                        expTime = metaData.text
                        for fmt in (
                            "%Y-%m-%dT%H:%M:%S+01:00",
                            "%Y-%m-%dT%H:%M:%S.%f+01:00",
                        ):
                            try:
                                reqTime = (
                                    datetime.strptime(expTime, fmt) - datetime.now()
                                )

                                if reqTime.total_seconds() > 0:
                                    for metaData in estimatedCall:

                                        if (
                                            metaData.tag
                                            == "{http://www.siri.org.uk/siri}StopPointName"
                                        ):
                                            name = metaData.text
                                    for metaData in estimatedCall:
                                        if (
                                            metaData.tag
                                            == "{http://www.siri.org.uk/siri}DestinationDisplay"
                                        ):
                                            dest = metaData.text

                                    print(name, dest, reqTime)
                                    shouldBreak = True
                                    

                            except ValueError:
                                pass
                    if shouldBreak:
                        break
                if shouldBreak:
                    break        
        # if shouldBreak:
        #     break
