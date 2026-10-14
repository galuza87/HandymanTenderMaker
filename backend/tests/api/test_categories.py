def test_get_categories(client):
    """
    Test that the /api/categories endpoint returns a 200 status code 
    and a valid JSON response containing categories.
    """
    response = client.get("/api/categories")
    
    # Assert successful status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}. Details: {response.text}"
    
    # Assert the response body is either a list or a dict
    data = response.json()
    assert isinstance(data, (list, dict)), f"Expected a list or dict, but got {type(data)}"
