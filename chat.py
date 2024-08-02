from typing import List, Optional, Tuple, Dict
import os
import json
from openai import OpenAI
from dotenv import load_dotenv
import asyncio
import regex as re
from gradio_modal import Modal
import gradio as gr
import time

# Load environment variables from .env file
load_dotenv()

from suno import make_song, concat_snippets, update_song_links
from gpt_calls import AI_Songwriter
from utils.song_utils import messages_to_history

History = List[Tuple[str, str]] # a type: pairs of (query, response), where query is user input and response is system output
Messages = List[Dict[str, str]] # a type: list of messages with role and content

client_key = os.getenv("OPEN_AI_KEY")
# print(client_key)
oai_client = OpenAI(
    api_key=client_key,
)

def determine_title(section_name, generated_audios):
    count = sum(1 for audio in generated_audios if audio[2].startswith(section_name))
    if count > 0:
        section_name = f"{section_name} {count + 1}"
    return section_name


def model_chat(genre_input, query: Optional[str], history: Optional[History], messages: Optional[Messages], generated_audios: List[Tuple[str, str, str]], auto=False) -> Tuple[str, History, Messages, str, str, str, str, str, List]:
    if query is None:
        query = ''
    with open('ai_tools.json') as f:
        ai_tools = json.load(f)

    songwriterAssistant = AI_Songwriter(client_key=client_key)

    if auto:
        messages = messages[:-1] + [{'role': 'user', 'content': query}] #should this be a -1? for non-auto. why does the chatbot history get messed up?
    else:
        messages = messages + [{'role': 'user', 'content': query}]


    messages_filtered = messages
    response_message = oai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages_filtered,
        tools = ai_tools,
        tool_choice="required",
    )
    print(response_message, "model chat response")
    current_response = ""
    # Step 2: determine if the response from the model includes a tool call.   
    tool_calls = response_message.choices[0].message.tool_calls
    if tool_calls:
        messages.append({
            "role": response_message.choices[0].message.role,
            "content": response_message.choices[0].message.content,
            "tool_calls": tool_calls,
            "function_call": response_message.choices[0].message.function_call
        })

        if len(tool_calls) > 1:
            for tool_call in tool_calls:
                tool_message = {
                    'role': 'tool',
                    'tool_call_id': tool_call.id,
                    'name': tool_call.function.name,
                    'content': "You called two different functions when you can only call one at a time. Did you mean to call revise_section_lyrics_and_instrumental but instead had two different calls for lyrics and instrumental? Communicate this failure to the user and clarify what they are asking for, then only call one tool next time."
                }
                messages.append(tool_message)

            # Generate a response using GPT-4o and add it as a message
            model_response_with_function_call = oai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
            )
            current_response = model_response_with_function_call.choices[0].message.content

            role = "assistant"
            messages.append({'role': role, 'content': current_response})

            yield '', messages_to_history(messages), messages, '', '', '', '', None, generated_audios, []
            return


        # If true the model will return the name of the tool / function to call and the argument(s)  
        for tool_call in tool_calls:
            print(tool_call)
            tool_call_id = tool_call.id
            tool_function_name = tool_call.function.name
            tool_query_args = eval(tool_call.function.arguments)

            print(tool_function_name, tool_query_args)

            with open('ai_tools.json') as f:
                ai_tools = json.load(f)
            
            for tool in ai_tools:
                if tool['function']['name'] == tool_function_name:
                    valid_keys = tool['function']['parameters']['properties'].keys()
                    required_keys = tool['function']['parameters']['required']
                    break
            
            print('query args before', tool_query_args)
            tool_query_args = {k: v for k, v in tool_query_args.items() if k in valid_keys}
            print('query args after', tool_query_args)
            missing_keys = []
            for key in required_keys:
                if key not in tool_query_args:
                    missing_keys.append(key)
            if len(missing_keys)>0:
                missing_keys_str = ", ".join(missing_keys)
                tool_message = {
                    'role': 'tool',
                    'tool_call_id': tool_call_id,
                    'name': tool_function_name,
                    'content': f"Sorry, the keys {missing_keys_str} from the function you called are missing, communicate this to the user and either get what these args should be or figure out which function to call."
                }

                new_messages = messages + [tool_message]

                model_response_with_function_call = oai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=new_messages,
                )  # get a new response from the model where it can see the function response
                current_response = model_response_with_function_call.choices[0].message.content

                role = "assistant"
                new_messages = new_messages + [{'role': role, 'content': current_response}]
                new_history = messages_to_history(new_messages)

                generated_audios = update_song_links(generated_audios)
                yield '', new_history, new_messages, '', '', '', '', None, generated_audios, []
                        
                        
            # Step 3: Call the function and retrieve results. Append the results to the messages list. 
            if tool_function_name == 'ask_question':
                question = songwriterAssistant.ask_question(messages)

                question = question.replace("ask question:", "").replace("ask question ", "").replace("ask question\n", "").replace("ask question", "")

                ## yield question in tool and assistant message
                tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': question}

                new_messages = messages + [tool_message]

                question_message = {'role': 'assistant', 'content': question}
                new_messages = new_messages + [question_message]
                new_history = messages_to_history(new_messages)

                generated_audios = update_song_links(generated_audios)
                yield '', new_history, new_messages, '', '', '', '', None, generated_audios, []
            
            elif tool_function_name == 'clarify_arguments':
                tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': 'arguments to clarify: \n' + '\n'.join(tool_query_args['arguments_to_clarify'])}

                new_messages = messages + [tool_message]

                model_response_with_function_call = oai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=new_messages,
                )  # get a new response from the model where it can see the function response
                current_response = model_response_with_function_call.choices[0].message.content

                role = "assistant"
                new_messages = new_messages + [{'role': role, 'content': current_response}] # + "\n\nWould you like to get an audio snippet? Or continue writing?"}]
                # new_messages = [msg for msg in new_messages if msg['content'] is not None and msg['role'] in ['user', 'assistant']]
                new_history = messages_to_history(new_messages)

                generated_audios = update_song_links(generated_audios)
                yield '', new_history, new_messages, '', '', '', '', None, generated_audios, []

            
            elif tool_function_name == 'write_section':
                snippet_instrumental_tags = tool_query_args.pop('snippet_instrumental_tags', None)
                snippet_clip_to_continue_from = tool_query_args.pop('snippet_clip_to_continue_from', None)
                suggested_lyrics = songwriterAssistant.write_section(**tool_query_args)
                suggested_lyrics = suggested_lyrics.strip('`*-\n')

                ## yield suggested lyrics in tool and assistant message
                tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': suggested_lyrics}
                # audio_message = {'role': 'assistant', 'content': "Here's what I've come up with:\n" + suggested_lyrics + "\n\nGenerating audio snippet..."}
                new_messages = messages + [tool_message] #, audio_message

                model_response_with_function_call = oai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=new_messages,
                )  # get a new response from the model where it can see the function response
                current_response = model_response_with_function_call.choices[0].message.content

                role = "assistant"
                new_messages = new_messages + [{'role': role, 'content': current_response}] # + "\n\nWould you like to get an audio snippet? Or continue writing?"}]
                # new_messages = [msg for msg in new_messages if msg['content'] is not None and msg['role'] in ['user', 'assistant']]
                history = messages_to_history(new_messages)

                # current_section, current_lyrics, curr_tags, clip_to_continue, curr_audio
                buttons = ["revise lyrics", "generate audio snippet", "continue to next section"]

                generated_audios = update_song_links(generated_audios)
                clips_to_continue = gr.Dropdown(label='Clip to continue', value = snippet_clip_to_continue_from, choices=[x[3] for x in generated_audios]+[""], interactive=True)



                yield '', history, new_messages, tool_query_args['section_name'], suggested_lyrics.split(':')[-1], snippet_instrumental_tags, clips_to_continue, None, generated_audios, buttons

                ### DO SOMETHING TO UPDATE CURRENT GENERATION for write_section


            elif tool_function_name == 'revise_section_lyrics':
                revised_lyrics = songwriterAssistant.revise_section_lyrics(**tool_query_args)

                # if isinstance(revised_lyrics, list):
                #     revised_lyrics = '\n'.join(revised_lyrics)
                if isinstance(revised_lyrics, str) and revised_lyrics.startswith("[") and revised_lyrics.endswith("]"):
                    try:
                        revised_lyrics = eval(revised_lyrics)
                        if isinstance(revised_lyrics, list):
                            revised_lyrics = '\n'.join(revised_lyrics)
                    except:
                        pass

                # ## yield revised lyrics in tool and assistant message
                tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': revised_lyrics}
                # audio_message = {'role': 'assistant', 'content': "Here's my revised lyrics:\n" + revised_lyrics + "\n\nGenerating audio snippet..."}
                new_messages = messages + [tool_message] #, audio_message]

                model_response_with_function_call = oai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=new_messages,
                )  # get a new response from the model where it can see the function response
                current_response = model_response_with_function_call.choices[0].message.content

                buttons = ["revise lyrics again", "generate audio snippet with new lyrics", "continue to next section"]

                role = "assistant"
                new_messages = new_messages + [{'role': role, 'content': current_response + "\n\nWould you like to get an audio snippet? Or continue writing?"}]
                # new_messages = [msg for msg in new_messages if msg['content'] is not None and msg['role'] in ['user', 'assistant']]
                history = messages_to_history(new_messages)
                generated_audios = update_song_links(generated_audios)
                clips_to_continue = gr.Dropdown(label='Clip to continue', value = "", choices=[x[3] for x in generated_audios]+[""], interactive=True)

                yield '', history, new_messages, tool_query_args['section_name'], revised_lyrics, '', clips_to_continue, None, generated_audios, buttons


            elif tool_function_name == 'revise_instrumental_tags':
                #detangle tool_query_args dict
                #snippet_lyrics = tool_query_args['snippet_lyrics'] + "\n[End]"
                snippet_instrumental_tags = tool_query_args.get('current_instrumental_tags', None)
                user_instrumental_feedback = tool_query_args.get('user_instrumental_feedback', None)

                if snippet_instrumental_tags is None or user_instrumental_feedback is None:
                    tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': 'Arguments are missing. Please clarify your feedback on the instrumental. Note that you cannot revise the genre if you haven\'t generated a snippet.'}
                    audio_message = {'role': 'assistant', 'content': 'It seems like some information is missing. Could you please provide your feedback on the instrumental? Note that you cannot revise the genre if you haven\'t generated a snippet.'}
                    new_messages = messages + [tool_message, audio_message]
                    new_history = messages_to_history(new_messages)
                    yield '', new_history, new_messages, '', '', '', None, None, generated_audios, []
                    return
                # if 'snippet_clip_to_continue_from' not in tool_query_args:
                #     tool_query_args['snippet_clip_to_continue_from'] = None
                # snippet_clip_to_continue_from = tool_query_args['snippet_clip_to_continue_from']

                new_instrumental_tags = songwriterAssistant.revise_instrumental_tags(snippet_instrumental_tags, user_instrumental_feedback)

                if isinstance(tool_query_args['sections_written'], str):
                    current_lyrics = tool_query_args['sections_written']
                elif isinstance(tool_query_args['sections_written'], list):
                    current_lyrics = "\n".join(tool_query_args['sections_written'])
                else:
                    current_lyrics = ""

                import re
                sections_list = re.findall(r'\[.*?\]', current_lyrics)

                #current_lyrics = "\n".join(tool_query_args['sections_written'])
                song_link = make_song(current_lyrics, new_instrumental_tags)
                ## filter out suno link from tool query arg
                while "https://audiopipe.suno.ai/?item_id=" not in song_link:
                    print("BUGGED OUT, trying again...")
                    time.sleep(5)
                    song_link = make_song(current_lyrics, new_instrumental_tags)

                clip_id = song_link.split("https://audiopipe.suno.ai/?item_id=")[1]

                tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': f'new instrumental tags: {new_instrumental_tags}, clip id: {clip_id}'}
                audio_message = {'role': 'assistant', 'content': f'Sure! I\'ve revised the instrumental tags: {new_instrumental_tags}\nCurrent lyrics: {current_lyrics}\n\n <audio controls autoplay><source src="{song_link}" type="audio/mp3"></audio>'}
                audio_message['content'] += f'\n\nWhat do you think?'
                new_messages = messages + [tool_message, audio_message]
                new_history = messages_to_history(new_messages)

                # current_section, current_lyrics, curr_tags, clip_to_continue, curr_audio
                if len(sections_list) > 0:
                    section_name = f"Up to {sections_list[-1]}"
                else:
                    section_name = "Up to latest section"
                section_name = determine_title(section_name, generated_audios)

                generated_audios.append((song_link, current_lyrics, new_instrumental_tags, section_name, "streaming"))
                generated_audios = update_song_links(generated_audios)
                clips_to_continue = gr.Dropdown(label='Clip to continue', value = "", choices=[x[3] for x in generated_audios]+[""], interactive=True)

                buttons = ["return to original instrumental", "re-revise genre", "revise lyrics", "merge snippets", "continue to next section"]

                yield '', new_history, new_messages, ', '.join(sections_list), current_lyrics, new_instrumental_tags, clips_to_continue, f'<audio controls><source src="{song_link}" type="audio/mp3"></audio>', generated_audios, buttons
            elif tool_function_name == 'revise_section_lyrics_and_instrumental':
                snippet_instrumental_tags = tool_query_args.pop('current_instrumental_tags', None)
                user_instrumental_feedback = tool_query_args.pop('user_instrumental_feedback', None)
                snippet_clip_to_continue_from = tool_query_args.pop('snippet_clip_to_continue_from', None)
                
                # Revise section lyrics
                revised_lyrics = songwriterAssistant.revise_section_lyrics(**tool_query_args)
                
                # Revise instrumental tags
                
                new_instrumental_tags = songwriterAssistant.revise_instrumental_tags(snippet_instrumental_tags, user_instrumental_feedback)

                song_link = make_song(revised_lyrics, new_instrumental_tags, snippet_clip_to_continue_from)
                while "https://audiopipe.suno.ai/?item_id=" not in song_link:
                    print("BUGGED OUT, trying again...")
                    time.sleep(5)
                    song_link = make_song(revised_lyrics, new_instrumental_tags, snippet_clip_to_continue_from)

                clip_id = song_link.split("https://audiopipe.suno.ai/?item_id=")[1]

                tool_message_instrumental = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': f'revised lyrics: {revised_lyrics}\nrevised instrumental tags: {new_instrumental_tags}, clip id: {clip_id}'}
                audio_message = {'role': 'assistant', 'content': f'Sure! I\'ve revised the lyrics and instrumental tags: {revised_lyrics}\nRevised lyrics: {revised_lyrics}\n\n <audio controls autoplay><source src="{song_link}" type="audio/mp3"></audio>'}
                audio_message['content'] += f'\n\nWhat do you think?'
                
                new_messages = messages + [tool_message_instrumental, audio_message]
                new_history = messages_to_history(new_messages)

                generated_audios.append((song_link, revised_lyrics, new_instrumental_tags, tool_query_args["section_name"], "streaming"))
                generated_audios = update_song_links(generated_audios)
                clips_to_continue = gr.Dropdown(label='Clip to continue', value = snippet_clip_to_continue_from, choices=[x[3] for x in generated_audios]+[""], interactive=True)

                buttons = ["return to original instrumental", "re-revise genre", "revise lyrics", "merge snippets", "continue to next section"]

                yield '', new_history, new_messages, tool_query_args["section_name"], revised_lyrics, new_instrumental_tags, clips_to_continue, f'<audio controls><source src="{song_link}" type="audio/mp3"></audio>', generated_audios, buttons
            
            elif tool_function_name == 'merge_all_snippets':
                updated_clip_url, updated_lyrics, updated_tags, clips_list = concat_snippets(tool_query_args['last_snippet_id'])

                if "still streaming" in updated_clip_url:
                    tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': f'still streaming, try again later'}
                    audio_message = {'role': 'assistant', 'content': f'Unfortunately the generated clip audio is still being streamed, so you can merge later when it is fully generated.'}

                    new_messages = messages + [tool_message, audio_message]
                    new_history = messages_to_history(new_messages)

                    clips_to_continue = gr.Dropdown(label='Clip to continue', value = "", choices=[x[3] for x in generated_audios]+[""], interactive=True)


                    yield '', new_history, new_messages, "", "", "", clips_to_continue, None, generated_audios, []

                else:
                    if "https://audiopipe.suno.ai/?item_id=" in updated_clip_url:
                        updated_clip_id = updated_clip_url.split("https://audiopipe.suno.ai/?item_id=")[1]
                    elif "https://cdn1.suno.ai/" in updated_clip_url:
                        updated_clip_id = updated_clip_url.split("https://cdn1.suno.ai/")[1].split(".mp3")[0]
                    else:
                        updated_clip_id = "unknown"

                    #pass this info in new tool and assistant message
                    tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': f'updated clip id: {updated_clip_id}\nupdated lyrics: {updated_lyrics}\nupdated clips path: {clips_list}'}
                    audio_message = {'role': 'assistant', 'content': f'Sure! All the clips are now merged. <p>updated lyrics: {updated_lyrics}</p><audio controls autoplay><source src="{updated_clip_url}" type="audio/mp3"></audio><p>updated clips path: {clips_list}</p>'}

                    sections_list = [line for line in current_lyrics.split('\n') if line.startswith('[') and line.endswith(']')]


                    new_messages = messages + [tool_message, audio_message]
                    new_history = messages_to_history(new_messages)

                    if len(sections_list) > 0:
                        section_name = "Merge up to " + sections_list[-1]
                    else: 
                        section_name = "Merge up to latest section"
                    section_name = determine_title(section_name, generated_audios)

                    # current_section, current_lyrics, curr_tags, clip_to_continue, curr_audio
                    generated_audios.append((updated_clip_url, updated_lyrics, updated_tags, section_name, "streaming"))

                    generated_audios = update_song_links(generated_audios)
                    clips_to_continue = gr.Dropdown(label='Clip to continue', value = "", choices=[x[3] for x in generated_audios]+[""], interactive=True)


                    yield '', new_history, new_messages, section_name, updated_lyrics, updated_tags, clips_to_continue, f'<audio controls><source src="{updated_clip_url}" type="audio/mp3"></audio>', generated_audios, []
            elif tool_function_name == 'finish_full_song':
                ## args are sections_to_be_written, relevant_ideas, last_snippet_id, sni
                
                ## STEP 0: POP out instrumental args
                snippet_instrumental_tags = tool_query_args.pop('snippet_instrumental_tags', None)
                snippet_clip_to_continue_from = tool_query_args.pop('snippet_clip_to_continue_from', None)

                if isinstance(tool_query_args['sections_written'], str):
                    current_lyrics = tool_query_args['sections_written']
                elif isinstance(tool_query_args['sections_written'], list):
                    current_lyrics = "\n".join(tool_query_args['sections_written'])
                else:
                    current_lyrics = ""

                ## STEP 1: WRITE ALL LYRICS using songwriterAssistant
                remaining_lyrics = songwriterAssistant.write_all_lyrics(**tool_query_args)
                full_lyrics = current_lyrics + remaining_lyrics + "\n[End]"


                # current_section, current_lyrics, curr_tags, clip_to_continue, curr_audio
                yield '', history, messages, "Full Song", full_lyrics, snippet_instrumental_tags, snippet_clip_to_continue_from, None, generated_audios, []

                ## STEP 2: MAKE SONG FOR REMAINING LYRICS
                song_link = make_song(remaining_lyrics, snippet_instrumental_tags, snippet_clip_to_continue_from)

                #tool and assistant message
                tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': f'{full_lyrics}'}
                audio_message = {'role': 'assistant', 'content': f'New snippet: \n <audio controls autoplay><source src="{song_link}" type="audio/mp3"></audio>'}

                new_messages = messages + [tool_message, audio_message]
                new_history = messages_to_history(new_messages)
                generated_audios.append((song_link, remaining_lyrics, snippet_instrumental_tags, "Rest of Song", "streaming"))

                yield '', new_history, new_messages, "Rest of Song", full_lyrics, snippet_instrumental_tags, snippet_clip_to_continue_from, song_link, generated_audios, []

                ## STEP 3: MERGE FULL SONG
                if snippet_clip_to_continue_from not in [None, ""]:
                    updated_clip_url = "still streaming"
                    while "still streaming" in updated_clip_url:
                        if "https://audiopipe.suno.ai/?item_id=" in song_link:
                            clip_id = song_link.split("https://audiopipe.suno.ai/?item_id=")[1]
                        else:
                            clip_id = updated_clip_url.split("https://cdn1.suno.ai/")[1].split(".mp3")[0]
                        updated_clip_url, updated_lyrics, updated_tags, clips_list = concat_snippets(clip_id)
                else:
                    updated_clip_url, updated_lyrics, clips_list = song_link, remaining_lyrics, []
                ## YIELD UPDATED CLIP URL, LYRICS, AND CLIPS LIST
                if "https://audiopipe.suno.ai/?item_id=" in updated_clip_url:
                    updated_clip_id = updated_clip_url.split("https://audiopipe.suno.ai/?item_id=")[1]
                elif "https://cdn1.suno.ai/" in updated_clip_url:
                    updated_clip_id = updated_clip_url.split("https://cdn1.suno.ai/")[1].split(".mp3")[0]
                else:
                    updated_clip_id = "unknown"

                #tool and assistant message
                tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': f'updated clip id: {updated_clip_id}\nupdated lyrics: {updated_lyrics}\nupdated clips path: {clips_list}'}
                audio_message = {'role': 'assistant', 'content': f'All done! Thank you for participating :) \nFinal Lyrics: {full_lyrics} \nFinal song: <audio controls autoplay><source src="{updated_clip_url}" type="audio/mp3"></audio>'}

                new_messages = messages + [tool_message, audio_message]
                new_history = messages_to_history(new_messages)
                generated_audios.append((updated_clip_url, updated_lyrics, updated_tags, "Full Song", "streaming"))
                generated_audios = update_song_links(generated_audios)
                clips_to_continue = gr.Dropdown(label='Clip to continue', value = "", choices=[x[3] for x in generated_audios]+[""], interactive=True)

                yield '', new_history, new_messages, "Full Song", full_lyrics, snippet_instrumental_tags, clips_to_continue, f'<audio controls><source src="{song_link}" type="audio/mp3"></audio>', generated_audios, []

            elif tool_function_name == 'get_audio_snippet':
                #detangle tool_query_args dict
                snippet_lyrics = tool_query_args['snippet_lyrics'] + "\n[End]"
                snippet_instrumental_tags = tool_query_args['snippet_instrumental_tags']

                snippet_clip_to_continue_from = tool_query_args.get('snippet_clip_to_continue_from', None)
                song_link = make_song(snippet_lyrics, snippet_instrumental_tags, snippet_clip_to_continue_from)


                if "still streaming" in song_link:
                    tool_message = {
                        'role': 'tool',
                        'tool_call_id': tool_call_id,
                        'name': tool_function_name,
                        'content': 'The snippet to extend is still streaming. Please try generating this audio snippet in a little bit.'
                    }

                    new_messages = messages + [tool_message]

                    model_response_with_function_call = oai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=new_messages,
                    )  # get a new response from the model where it can see the function response
                    current_response = model_response_with_function_call.choices[0].message.content

                    role = "assistant"
                    new_messages = new_messages + [{'role': role, 'content': current_response}]
                    new_history = messages_to_history(new_messages)

                    generated_audios = update_song_links(generated_audios)
                    clips_to_continue = gr.Dropdown(label='Clip to continue', value = "", choices=[x[3] for x in generated_audios]+[""], interactive=True)
                    buttons = []

                    yield '', new_history, new_messages, snippet_lyrics.split("\n")[0], snippet_lyrics, snippet_instrumental_tags, clips_to_continue, None, generated_audios, buttons
                    
                    return
                

                if "no clip with that ID" in song_link:
                    tool_message = {
                        'role': 'tool',
                        'tool_call_id': tool_call_id,
                        'name': tool_function_name,
                        'content': 'The clip ID was incorrect, maybe clarify with the user.'
                    }

                    new_messages = messages + [tool_message]

                    model_response_with_function_call = oai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=new_messages,
                    )  # get a new response from the model where it can see the function response
                    current_response = model_response_with_function_call.choices[0].message.content

                    role = "assistant"
                    new_messages = new_messages + [{'role': role, 'content': current_response}]
                    new_history = messages_to_history(new_messages)

                    generated_audios = update_song_links(generated_audios)
                    clips_to_continue = gr.Dropdown(label='Clip to continue', value = "", choices=[x[3] for x in generated_audios]+[""], interactive=True)
                    buttons = []

                    yield '', new_history, new_messages, snippet_lyrics.split("\n")[0], snippet_lyrics, snippet_instrumental_tags, clips_to_continue, None, generated_audios, buttons
                    
                    return
                print("MAKE SONG IS DONE")
                ## filter out suno link from tool query arg
                clip_id = song_link.split("https://audiopipe.suno.ai/?item_id=")[1]

                tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': f'snippet lyrics: {snippet_lyrics}\ninstrumental tags: {tool_query_args["snippet_instrumental_tags"]}, clip id: {clip_id}'}
                audio_message_content = "Here's what I've come up with:\n" + snippet_lyrics + '\n\n' + f'<audio controls autoplay><source src="{song_link}" type="audio/mp3"></audio><p>instrumental tags: {tool_query_args["snippet_instrumental_tags"]}</p>'
                audio_message_content += f'<p>continued from clip: {snippet_clip_to_continue_from}</p>'
                audio_message_content += "What do you think?"
                audio_message = {'role': 'assistant', 'content': audio_message_content}
                

                section_name = snippet_lyrics.split("\n")[0].strip('[]* ')
                section_name = determine_title(section_name, generated_audios)

                #audio_message = {'role': 'assistant', 'content': gr.Audio(value=song_link, label=section_name, interactive=False, show_label=False, waveform_options={"show_controls": False})}
                new_messages = messages + [tool_message, audio_message]
                new_history = messages_to_history(new_messages)
                print("AUDIO MESSAGE DONE")
                generated_audios.append((song_link, snippet_lyrics, snippet_instrumental_tags, section_name, "streaming"))

                generated_audios = update_song_links(generated_audios)

                buttons = ["revise lyrics", "revise genre", "merge snippets", "continue to next section"]
                clips_to_continue = gr.Dropdown(label='Clip to continue', value = snippet_clip_to_continue_from, choices=[x[3] for x in generated_audios]+[""], interactive=True)

                yield '', new_history, new_messages, snippet_lyrics.split("\n")[0], snippet_lyrics, snippet_instrumental_tags, clips_to_continue, f'<audio controls><source src="{song_link}" type="audio/mp3"></audio>', generated_audios, buttons


            else: 
                print(f"Error: function {tool_function_name} does not exist")
        
    else: 
        # Model did not identify a function to call, result can be returned to the user 
        current_response = response_message.choices[0].message.content

        role = "assistant"
        new_messages = messages + [{'role': role, 'content': current_response}]
        # new_messages = [msg for msg in new_messages if msg['content'] is not None and msg['role'] in ['user', 'assistant']]
        history = messages_to_history(new_messages)
        yield '', history, new_messages, '[...]'