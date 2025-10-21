The text below contains pre-extracted entities, denoted in the following format within the text:

<entity text>[<entity id>:<entity label>]

From the text below, extract the following relations between entities:
LivesIn Visits Murders ChangeOfLocation Supervises

The extraction has to use the following format, with one line for each detected relation:

{"dep": <entity id>, "dest": <entity id>, "relation": <relation label>}

Make sure that only relevant relations are listed, and that each line is a valid JSON object.

Below are definitions of each label to help aid you in what kinds of relationship to extract for each label.
Assume these definitions are written by an expert and follow them closely.

LivesIn: relation between a person and a location where they live.
Visits: relation between a person and a location they visit.
Murders: relation between a person and a person they murder.
ChangeOfLocation: relation between a person and a location that they move to.
Supervises: relation between a supervisor and the person they supervise.

Here is the text that needs labeling:

Text:
'''
Another <American>[1:GPE] climber, <Gina Marie Rzucidlo>[2:PERSON], supervised by <Tenjen Sherpa>[3:PERSON] is missing
'''
