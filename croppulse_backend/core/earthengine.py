import ee

SERVICE_ACCOUNT = "croppulse-satellite@croppulseafrica.iam.gserviceaccount.com"
KEY_FILE = "/Users/koboko/CropPulseAfrica_v2/keys/croppulse-satellite.json"

# Authenticate and initialize
credentials = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, KEY_FILE)
ee.Initialize(credentials)
