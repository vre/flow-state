#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path

# Load JSON
with open('/Users/vre/work/flow-state/video_data.json', 'r') as f:
    data = json.load(f)

video_id = data['video_id']
base_name = f'youtube_{video_id}'

# Save title
title_file = f'/Users/vre/work/flow-state/{base_name}_title.txt'
with open(title_file, 'w') as f:
    f.write(data['title'])

# Create metadata file
upload_date = data.get('upload_date', 'Unknown')
if upload_date != 'Unknown' and len(str(upload_date)) == 8:
    upload_date = f'{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}'

extraction_date = datetime.now().strftime('%Y-%m-%d')

subscribers = data.get('channel_follower_count')
if isinstance(subscribers, int):
    sub_text = f'{subscribers:,} subscribers'
else:
    sub_text = 'N/A subscribers'

duration = data.get('duration', 0)
if duration:
    hours = duration // 3600
    minutes = (duration % 3600) // 60
    seconds = duration % 60
    if hours > 0:
        duration_text = f'{hours:02d}:{minutes:02d}:{seconds:02d}'
    else:
        duration_text = f'{minutes:02d}:{seconds:02d}'
else:
    duration_text = 'Unknown'

views_text = f"{data.get('view_count', 0):,}" if data.get('view_count') else '0'
likes_text = f"{data.get('like_count', 0):,}" if data.get('like_count') else '0'

metadata_content = f"""- **Title:** [{data['title']}]({data['webpage_url']})
- **Channel:** [{data['uploader']}]({data.get('channel_url', '')}) ({sub_text})
- **Views:** {views_text} | Likes: {likes_text} | Duration: {duration_text}
- **Published:** {upload_date} | Extracted: {extraction_date}"""

with open(f'/Users/vre/work/flow-state/{base_name}_metadata.md', 'w') as f:
    f.write(metadata_content)

# Create description file
with open(f'/Users/vre/work/flow-state/{base_name}_description.md', 'w') as f:
    f.write(data.get('description', 'No description'))

# Create chapters file
with open(f'/Users/vre/work/flow-state/{base_name}_chapters.json', 'w') as f:
    json.dump(data.get('chapters', []), f, indent=2)

print(f'SUCCESS: Created metadata, description, and chapters for {video_id}')
print(f'Title: {data["title"]}')
