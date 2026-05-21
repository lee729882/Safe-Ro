import urllib.request
import os
import shutil

dest = r"d:\Safe-Ro\frontend\public\dongs.json"
url = "https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2013/json/skorea_submunicipalities_geo_simple.json"

try:
    print(f"Downloading from {url} to {dest}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response, open(dest, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)
    print(f"Download complete! Size: {os.path.getsize(dest)} bytes")
except Exception as e:
    print(f"Error: {e}")
