from easy_trilateration.model import *  
from easy_trilateration.least_squares import easy_least_squares  
from easy_trilateration.graph import *  

def trilateration_three_nearest(anchor_locations, distances):
    # Sort anchor keys by their corresponding distance values
    sorted_anchors = sorted(distances.items(), key=lambda item: item[1])[:3]
    
    arr = []
    for anchor_selected, distance in sorted_anchors:
        anchors = anchor_locations[anchor_selected]
        arr.append(Circle(anchors[0], anchors[1], distance))
    
    result, meta = easy_least_squares(arr)
    return result
