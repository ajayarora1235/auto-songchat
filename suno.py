import requests
import time
import os
import asyncio
import httpx

base_url = "https://sss-api-blond.vercel.app"
api_endpoint_submit = f"{base_url}/generate/"
api_endpoint_concat = f"{base_url}/generate/concat"
api_endpoint_info = f"{base_url}/feed/"
api_key = "xZ1PhKexmwTR3dDskMvIGRlx137K40Il"
headers = {"api-key": api_key}

# tags = "lofi, chill, happy"
# prompt = "I'm a fish swimming in the ocean\nI'm a bird flying in the sky\nI'm a flower blooming in the garden\nI'm a tree standing tall and high"

def make_song(snippet_lyrics, inst_tags, continue_from_clip=None, continue_at=None):
    """
    Generates a song based on provided lyrics and instrumental tags.

    Args:
        snippet_lyrics (str): The lyrics for the song snippet.
        inst_tags (str): The instrumental tags for the song.
        continue_from_clip (str, optional): The clip ID to continue from, if any. Defaults to None.
        continue_at (int, optional): The position to continue at in the clip. Defaults to None.

    Returns:
        str: The link to the generated song.
    """
    os.makedirs("audio_clips", exist_ok=True)
    song_name = f"SG_{int(time.time())}"
    suno_song_path = f"./audio_clips/suno_{song_name}.wav"
    print("Passing to generate_song:", inst_tags, snippet_lyrics, suno_song_path)

    song_link = generate_song(inst_tags, snippet_lyrics, suno_song_path, continue_from_clip, continue_at) \
        if continue_from_clip else generate_song(inst_tags, snippet_lyrics, suno_song_path)

    return song_link

# Takes about 30 seconds
def generate_song(tags, prompt, save_path, clip_id=None, continue_at=30):
  # print("Generating song with tags", tags, "and prompt", prompt)

  data = {
    "title": "Songchat " + str(int(time.time())),
    "tags": tags,
    "prompt": prompt,
    "mv": "chirp-v3-5"
  }

  if clip_id is not None:
      data["continue_clip_id"] = clip_id
      if continue_at is not None:
          data["continue_at"] = continue_at
      else:
          data["continue_at"] = 30
      
      feed_url = api_endpoint_info + clip_id
      response = requests.get(feed_url, headers=headers)
      response_data = response.json()
      while True:
        if response.status_code != 200:
          print("No data in response, retrying", response_data)
          time.sleep(2)
          continue
        
        # Check if response_data is a list or a dictionary
        elif isinstance(response_data, list):
            if len(response_data) == 0 or "status" not in response_data[0]:
                print("Invalid response data,  no clip with that ID found")
                return "no clip with that ID found to continue from"
                # time.sleep(2)
                # continue
            status = response_data[0]["status"]
        elif isinstance(response_data, dict):
            if "status" not in response_data:
                print("Invalid response data, no clip with that ID found")
                return "no clip with that ID found to continue from"
                time.sleep(2)
                continue
            status = response_data["status"]
        else:
            print("Unexpected response format, no clip with that ID found")
            return "no clip with that ID found to continue from"
            time.sleep(2)
            continue

        if status != 'complete': 
          return "Snippet to extend is still streaming, please wait to request later."
        else:
          break

  response = requests.post(api_endpoint_submit, json=data) #,headers=headers)
  response_data = response.json()

  # print(response_data)
  
  if response.status_code != 200:
    print("Failure while submitting song req, retrying", response_data)
    time.sleep(5)
    song_link = generate_song(tags, prompt, save_path, clip_id)
    return song_link
    
  print(response_data)
  if "clips" in response_data:
      song_ids = [d["id"] for d in response_data["clips"]]
  else:
      print('something went wrong, retrying')
      time.sleep(5)
      song_link = generate_song(tags, prompt, save_path, clip_id)
      return song_link

  print("got song ids", song_ids)
  if song_ids == []:
    print("No song ids returned, retrying with shorter prompt")
    print("Response data was", response_data)
    time.sleep(5)
    # take off 30 words from the prompt
    new_prompt = " ".join(prompt.split(" ")[:-30])
    generate_song(tags, new_prompt, save_path)
    return

  song_id = song_ids[0] # Generally two song ids are returned

  startTime = time.time()
  while True:
    response = requests.get(api_endpoint_info + song_id, headers=headers)
    response_data = response.json()
    status = ""
    if response.status_code != 200:
      print("No data in response, retrying", response_data)
      time.sleep(2)
      continue
      # print("Got response", response_data)
        # Check if response_data is a list or a dictionary
    if isinstance(response_data, list):
        if len(response_data) == 0 or "status" not in response_data[0]:
            print("Invalid response data, update later")
            time.sleep(2)
            continue
        status = response_data[0]["status"]
        audio_url = response_data[0].get("audio_url", "")
    elif isinstance(response_data, dict):
        if "status" not in response_data:
            print("Invalid response data, update later")
            time.sleep(2)
            continue
        status = response_data["status"]
        audio_url = response_data.get("audio_url", "")
    else:
        print("Unexpected response format, update later")
        time.sleep(2)
        continue

    if status == 'streaming':
      break
    else:
      time.sleep(2)
      continue
    # if time.time() - startTime > 300:
    #   raise Exception("Timeout while waiting for song completion")
  
  print("Got song", audio_url)
  url = audio_url

  return url

def concat_snippets(clip_id):
  concat_url = f"{api_endpoint_concat}?clip_id={clip_id}"
  feed_url = api_endpoint_info + clip_id

  while True:
    status = ""
    response = requests.get(feed_url, headers=headers)
    response_data = response.json()
    if response.status_code != 200:
      print("No data in response, retrying", response_data)
      time.sleep(2)
      continue
    if isinstance(response_data, list):
        if len(response_data) == 0 or "status" not in response_data[0]:
            print("Invalid list response data, update later")
            continue
        status = response_data[0]["status"]
    elif isinstance(response_data, dict):
        if "status" not in response_data:
            print("Invalid dictionary response data, update later")
            continue
        status = response_data["status"]
    else:
        print("Unexpected response format, update later")
        continue

    if status == 'streaming':
        return "Song is still streaming, please wait to request later.", None, None, []
    if status == 'complete':
        break
    else:
      print("Streaming status couldn't be retrieved, response_data was ", response_data)
      time.sleep(8)
      continue


  response = requests.post(concat_url)
  response_data = response.json()
  print(response_data)

  if response.status_code != 200:
    print("Failure while submitting merge, retrying", response_data)
    time.sleep(5)
    url, lyrics, concatenated_clips = concat_snippets(clip_id)
    return url, lyrics, concatenated_clips

  lyrics = response_data["metadata"]["prompt"]
  tags = response_data["metadata"]["tags"]
  concatenated_clips = [x["id"] for x in response_data["metadata"]["concat_history"]]
  song_id = response_data["id"]

  startTime = time.time()
  while True:
    response = requests.get(api_endpoint_info + song_id, headers=headers)
    response_data = response.json()
    print("feed response for concatenated song", response_data)
    if response.status_code != 200:
      print("No data in response, retrying", response_data)
      time.sleep(2)
      continue
    print("Got concat snippet response", response_data)
    
    # Check if response_data is a list or a dictionary
    if isinstance(response_data, list):
        if len(response_data) == 0 or "status" not in response_data[0]:
            print("Invalid response data, update later")
            time.sleep(2)
            continue
        status = response_data[0]["status"]
        audio_url = response_data[0].get("audio_url", "")
    elif isinstance(response_data, dict):
        if "status" not in response_data:
            print("Invalid response data, update later")
            time.sleep(2)
            continue
        status = response_data["status"]
        audio_url = response_data.get("audio_url", "")
    else:
        print("Unexpected response format, update later")
        time.sleep(2)
        continue

    if status == 'streaming' or audio_url != "" or status == 'complete':
      break
    else:
      time.sleep(2)
      continue
    # if time.time() - startTime > 300:
    #   raise Exception("Timeout while waiting for song completion")
  
  print("Got song", audio_url)
  url = audio_url

  return url, lyrics, tags, concatenated_clips

def update_song_links(generated_audios):
  updated_generated_audios = generated_audios.copy()
  for i, song_info in enumerate(generated_audios):
    clip_path, lyrics, instrumental, title, status = song_info
    if "audiopipe.suno.ai" in clip_path or status == "streaming":
        clip_id = clip_path.split("?item_id=")[-1]
        feed_url = api_endpoint_info + clip_id

        response = requests.get(feed_url, headers=headers)
        response_data = response.json()
        if response.status_code != 200:
          print("No data in response, retrying", response_data)
          continue
        
        # Check if response_data is a list or a dictionary
        status = ""
        audio_url = ""
        if isinstance(response_data, list):
            if len(response_data) == 0 or "status" not in response_data[0]:
                print("Invalid list response data, update later")
                continue
            status = response_data[0]["status"]
            audio_url = response_data[0].get("audio_url", "")
        elif isinstance(response_data, dict):
            if "status" not in response_data:
                print("Invalid dictionary response data, update later")
                continue
            status = response_data["status"]
            audio_url = response_data.get("audio_url", "")
        else:
            print("Unexpected response format, update later")
            continue

        if status == 'streaming':
          print("still streaming, update later")
          continue
        if status == 'complete' and audio_url != "":
          updated_clip_path = audio_url
          print(updated_clip_path)
          updated_generated_audios[i] = (updated_clip_path, lyrics, instrumental, title, "complete")

  return updated_generated_audios



  


  