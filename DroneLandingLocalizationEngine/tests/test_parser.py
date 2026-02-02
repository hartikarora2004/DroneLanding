from DroneLandingLocalizationEngine.localizationEngine.utils.parser import parse_anchor_locations

def test_parsing_logic1():
    # Test 1: All is correct

    str1 = "Node1 | Node2 | Node3 | Node4 : ---- | ---- | ---- | 43.0  (cm)"
    res1 = {"Node1" : None, "Node2" : None, "Node3" : None, "Node4" : 43.0}
    real_result = parse_anchor_locations(str1)
    print(real_result)
    assert res1 == real_result

    str1 = "Node1 | Node2 | Node3 | Node4 : 34.0 | 23.0 | ---- | 43.0  (cm)"
    res1 = {"Node1" : 34.0 , "Node2" : 23.0, "Node3" : None, "Node4" : 43.0}
    real_result = parse_anchor_locations(str1)
    assert res1 == real_result
