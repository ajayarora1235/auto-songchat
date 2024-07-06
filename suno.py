import requests
import time

base_url = "http://127.0.0.1:8000"
api_endpoint_submit = f"{base_url}/generate/"
api_endpoint_concat = f"{base_url}/generate/concat"
api_endpoint_info = f"{base_url}/feed/"
api_key = "xZ1PhKexmwTR3dDskMvIGRlx137K40Il"
headers = {"api-key": api_key}

# tags = "lofi, chill, happy"
# prompt = "I'm a fish swimming in the ocean\nI'm a bird flying in the sky\nI'm a flower blooming in the garden\nI'm a tree standing tall and high"

# Takes about 2.5 minutes
def generate_song(tags, prompt, save_path, clip_id=None, continue_at=30):
  # print("Generating song with tags", tags, "and prompt", prompt)

  # prompt_word_count = len(prompt.split(" "))
  # if prompt_word_count > 230:
  #   print("Prompt too long, truncating to 230 words")
  #   prompt = " ".join(prompt.split(" ")[:230])

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
    if response.status_code != 200:
      print("No data in response, retrying", response_data)
      time.sleep(2)
      continue
      # print("Got response", response_data)
    if response_data[0]["status"] == 'streaming':
      break
    else:
      time.sleep(2)
      continue
    # if time.time() - startTime > 300:
    #   raise Exception("Timeout while waiting for song completion")
  
  print("Got song", response_data[0]["audio_url"])
  url = response_data[0]["audio_url"]

  return url

  # response = requests.get(url) #, stream=True)
  # chunk_size = 8192
  # print(url)

  # i = 0

  # for chunk in response.iter_content(chunk_size):
  #   print("got chunk")
  #   i += 1
  #   if i % 20 == 0:
  #     print(chunk)
  #   yield chunk
  # with open(save_path, "wb") as f:
  #   f.write(response.content)
  # print("Saved song to", save_path)

def concat_snippets(clip_id):
  concat_url = f"{api_endpoint_concat}?clip_id={clip_id}"
  feed_url = api_endpoint_info + clip_id

  while True:
    response = requests.get(feed_url, headers=headers)
    response_data = response.json()
    if response.status_code != 200:
      print("No data in response, retrying", response_data)
      time.sleep(2)
      continue
    if response_data[0]["status"] == 'complete':
      break
    else:
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
  concatenated_clips = [x["id"] for x in response_data["metadata"]["concat_history"]]
  song_id = response_data["id"]

  startTime = time.time()
  while True:
    response = requests.get(api_endpoint_info + song_id, headers=headers)
    response_data = response.json()
    if response.status_code != 200:
      print("No data in response, retrying", response_data)
      time.sleep(2)
      continue
      # print("Got response", response_data)
    if response_data[0]["status"] == 'streaming':
      break
    else:
      time.sleep(2)
      continue
    # if time.time() - startTime > 300:
    #   raise Exception("Timeout while waiting for song completion")
  
  print("Got song", response_data[0]["audio_url"])
  url = response_data[0]["audio_url"]

  return url, lyrics, concatenated_clips

  