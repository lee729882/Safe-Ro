import os
import shutil

src_file = r'C:\Users\lee72\.gemini\antigravity-ide\brain\e6bdb63d-eb01-4e30-aaaf-533429b08d8e\.system_generated\steps\1176\content.md'
dest_dir = r'D:\Safe-Ro\frontend\public'
dest_file = os.path.join(dest_dir, 'dongs.json')

os.makedirs(dest_dir, exist_ok=True)

# content.md has some markdown wrapping, let's read the raw text and extract just the JSON.
with open(src_file, 'r', encoding='utf-8') as f:
    text = f.read()

# find the first '{' and the last '}'
start_idx = text.find('{')
end_idx = text.rfind('}')

if start_idx != -1 and end_idx != -1:
    json_text = text[start_idx:end_idx+1]
    with open(dest_file, 'w', encoding='utf-8') as f:
        f.write(json_text)
    print("GeoJSON written successfully.")
else:
    print("Error: Could not find JSON block in content.md")
