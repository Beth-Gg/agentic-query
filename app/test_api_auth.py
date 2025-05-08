import os
import requests
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

def test_api_auth():
    """Test API authentication with the KFT Visualizer API"""
    
    # Get authentication credentials
    api_username = os.getenv("KFT_API_USERNAME")
    api_password = os.getenv("KFT_API_PASSWORD")
    
    if not api_username or not api_password:
        print("API credentials not found in environment variables!")
        print("Please set KFT_API_USERNAME and KFT_API_PASSWORD in your .env file.")
        return False
    
    # API endpoint - using a simple GET endpoint to test authentication
    api_url = "http://54.159.60.214/api/v1/kft-visualizer/user/users/"
    
    print(f"Testing API authentication with username: {api_username}")
    
    try:
        # Make authenticated request
        response = requests.get(
            api_url,
            auth=(api_username, api_password)
        )
        
        if response.status_code == 200:
            print("✅ Authentication successful!")
            print(f"Response status code: {response.status_code}")
            
            # Display the first few items from the response
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                print(f"\nFound {len(data)} user(s) in the response")
                print("First user data:")
                for key, value in list(data[0].items())[:5]:  # Show first 5 keys
                    print(f"  {key}: {value}")
            
            return True
        else:
            print(f"Authentication failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error testing API authentication: {str(e)}")
        return False

if __name__ == "__main__":
    print("API Authentication Test")
    print("======================")
    test_api_auth() 