from typing import List, Optional, Tuple, Dict
import os
import json
from openai import OpenAI

from suno import make_song, concat_snippets
from gpt_calls import AI_Songwriter
from utils.song_utils import messages_to_history

History = List[Tuple[str, str]] # a type: pairs of (query, response), where query is user input and response is system output
Messages = List[Dict[str, str]] # a type: list of messages with role and content

client_key = os.getenv("OPEN_AI_KEY")
oai_client = OpenAI(
    api_key=client_key,
)

def model_chat(genre_input, query: Optional[str], history: Optional[History], messages: Optional [Messages], auto=False) -> Tuple[str, str, History, Messages]:
    if query is None:
        query = ''

    if not query.endswith('?'):
        query += " Use write_section when you have a large amount of story to pull from to write the next section! Alternatively ask me a follow up before moving to write."

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
        tool_choice="auto",
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
        # If true the model will return the name of the tool / function to call and the argument(s)  
        for tool_call in tool_calls:
            print(tool_call)
            tool_call_id = tool_call.id
            tool_function_name = tool_call.function.name
            tool_query_args = eval(tool_call.function.arguments)
            
            # Step 3: Call the function and retrieve results. Append the results to the messages list.      
            if tool_function_name == 'write_section':
                snippet_instrumental_tags = tool_query_args.pop('snippet_instrumental_tags', None)
                snippet_clip_to_continue_from = tool_query_args.pop('snippet_clip_to_continue_from', None)
                suggested_lyrics = songwriterAssistant.write_section(**tool_query_args)

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
                new_messages = new_messages + [{'role': role, 'content': current_response}]
                # new_messages = [msg for msg in new_messages if msg['content'] is not None and msg['role'] in ['user', 'assistant']]
                history = messages_to_history(new_messages)
                yield '', history, new_messages, '[...]'


                # new_history = messages_to_history(new_messages)
                # yield '', new_history, new_messages, '[...]'

                # ### call make_song here with the snippet_lyrics, snippet_instrumental_tags, and snippet_clip_to_continue
                # song_link = make_song(suggested_lyrics, snippet_instrumental_tags, snippet_clip_to_continue)

                # ## filter out suno link from tool query arg
                # clip_id = song_link.split("https://audiopipe.suno.ai/?item_id=")[1]

                # ## add song link to tool and audio message
                # tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': suggested_lyrics + '\nclip id: ' + clip_id}
                # audio_message = {'role': 'assistant', 'content': "Here's what I've come up with:\n" + suggested_lyrics + '\n\n' + f'<audio controls autoplay><source src="{song_link}" type="audio/mp3"></audio><p>clip id: {clip_id}</p><p>instrumental tags: {snippet_instrumental_tags}</p>'}
                # audio_message['content'] += f'<p>continued from clip: {snippet_clip_to_continue}</p>'
                # audio_message['content'] += f'\n\nWhat do you think?'
                # new_messages = messages + [tool_message, audio_message]
                # new_history = messages_to_history(new_messages)
                # yield '', new_history, new_messages, '[...]'

            elif tool_function_name == 'revise_section_lyrics':
                snippet_instrumental_tags = tool_query_args.pop('snippet_instrumental_tags', None)
                snippet_clip_to_continue_from = tool_query_args.pop('snippet_clip_to_continue_from', None)
                revised_lyrics = songwriterAssistant.revise_section_lyrics(**tool_query_args)

                # ## yield revised lyrics in tool and assistant message
                tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': revised_lyrics}
                # audio_message = {'role': 'assistant', 'content': "Here's my revised lyrics:\n" + revised_lyrics + "\n\nGenerating audio snippet..."}
                new_messages = messages + [tool_message] #, audio_message]

                model_response_with_function_call = oai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=new_messages,
                )  # get a new response from the model where it can see the function response
                current_response = model_response_with_function_call.choices[0].message.content

                role = "assistant"
                new_messages = new_messages + [{'role': role, 'content': current_response}]
                # new_messages = [msg for msg in new_messages if msg['content'] is not None and msg['role'] in ['user', 'assistant']]
                history = messages_to_history(new_messages)
                yield '', history, new_messages, '[...]'
                # new_history = messages_to_history(new_messages)
                # yield '', new_history, new_messages, '[...]'

                # ### call make_song here with the snippet_lyrics, snippet_instrumental_tags, and snippet_clip_to_continue
                # song_link = make_song(revised_lyrics, snippet_instrumental_tags, snippet_clip_to_continue)

                # ## filter out suno link from tool query arg
                # clip_id = song_link.split("https://audiopipe.suno.ai/?item_id=")[1]

                # ## add song link to tool and audio message
                # tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': revised_lyrics + '\nclip id: ' + clip_id}
                # audio_message = {'role': 'assistant', 'content': "Here's what I've come up with:\n" + revised_lyrics + '\n\n' + f'<audio controls autoplay><source src="{song_link}" type="audio/mp3"></audio><p>clip id: {clip_id}</p><p>instrumental tags: {snippet_instrumental_tags}</p>'}
                # audio_message['content'] += f'<p>continued from clip: {snippet_clip_to_continue}</p>'
                # audio_message['content'] += f'\n\nWhat do you think?'
                # new_messages = messages + [tool_message, audio_message]
                # new_history = messages_to_history(new_messages)
                # yield '', new_history, new_messages, '[...]'

            elif tool_function_name == 'revise_instrumental_tags':
                #detangle tool_query_args dict
                #snippet_lyrics = tool_query_args['snippet_lyrics'] + "\n[End]"
                snippet_instrumental_tags = tool_query_args['current_instrumental_tags']
                user_instrumental_feedback = tool_query_args['user_instrumental_feedback']
                # if 'snippet_clip_to_continue_from' not in tool_query_args:
                #     tool_query_args['snippet_clip_to_continue_from'] = None
                # snippet_clip_to_continue_from = tool_query_args['snippet_clip_to_continue_from']

                new_instrumental_tags = songwriterAssistant.revise_instrumental_tags(snippet_instrumental_tags, user_instrumental_feedback)
                # yield new_instrumental_tags in tool and assistant message
                # tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': f'new instrumental tags: {new_instrumental_tags}'}
                # audio_message = {'role': 'assistant', 'content': f'Sure! I\'ve revised the instrumental tags: {new_instrumental_tags}\n\n Generating audio snippet...'}
                # new_messages = messages + [tool_message, audio_message]
                # new_history = messages_to_history(new_messages)
                # yield '', new_history, new_messages, '[...]'

                if isinstance(tool_query_args['sections_written'], str):
                    current_lyrics = tool_query_args['sections_written']
                elif isinstance(tool_query_args['sections_written'], list):
                    current_lyrics = "\n".join(tool_query_args['sections_written'])
                else:
                    current_lyrics = ""

                #current_lyrics = "\n".join(tool_query_args['sections_written'])
                song_link = make_song(current_lyrics, new_instrumental_tags)
                ## filter out suno link from tool query arg
                clip_id = song_link.split("https://audiopipe.suno.ai/?item_id=")[1]

                tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': f'new instrumental tags: {new_instrumental_tags}, clip id: {clip_id}'}
                audio_message = {'role': 'assistant', 'content': f'Sure! I\'ve revised the instrumental tags: {new_instrumental_tags}\nCurrent lyrics: {current_lyrics}\n\n <audio controls autoplay><source src="{song_link}" type="audio/mp3"></audio><p>clip id: {clip_id}</p>'}
                audio_message['content'] += f'\n\nWhat do you think?'
                new_messages = messages + [tool_message, audio_message]
                new_history = messages_to_history(new_messages)
                yield '', new_history, new_messages, '[...]'
            elif tool_function_name == 'merge_all_snippets':
                updated_clip_url, updated_lyrics, clips_list = concat_snippets(tool_query_args['last_snippet_id'])
                updated_clip_id = updated_clip_url.split("https://audiopipe.suno.ai/?item_id=")[1]

                #pass this info in new tool and assistant message
                tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': f'updated clip id: {updated_clip_id}\nupdated lyrics: {updated_lyrics}\nupdated clips path: {clips_list}'}
                audio_message = {'role': 'assistant', 'content': f'Sure! All the clips are now merged. <p>updated lyrics: {updated_lyrics}</p><audio controls autoplay><source src="{updated_clip_url}" type="audio/mp3"></audio><p>updated clip id: {updated_clip_id}</p><p>updated clips path: {clips_list}</p>'}

                new_messages = messages + [tool_message, audio_message]
                new_history = messages_to_history(new_messages)
                yield '', new_history, new_messages, '[...]'
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
                yield '', history, messages, full_lyrics 

                ## STEP 2: MAKE SONG FOR REMAINING LYRICS
                song_link = make_song(remaining_lyrics, snippet_instrumental_tags, snippet_clip_to_continue_from)

                #tool and assistant message
                tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': f'{full_lyrics}'}
                audio_message = {'role': 'assistant', 'content': f'New snippet: \n <audio controls autoplay><source src="{song_link}" type="audio/mp3"></audio>'}

                new_messages = messages + [tool_message, audio_message]
                new_history = messages_to_history(new_messages)
                yield '', new_history, new_messages, full_lyrics

                ## STEP 3: MERGE FULL SONG
                if snippet_clip_to_continue_from not in [None, ""]:
                    updated_clip_url, updated_lyrics, clips_list = concat_snippets(song_link.split("https://audiopipe.suno.ai/?item_id=")[1])
                else:
                    updated_clip_url, updated_lyrics, clips_list = song_link, remaining_lyrics, []
                ## YIELD UPDATED CLIP URL, LYRICS, AND CLIPS LIST
                updated_clip_id = updated_clip_url.split("https://audiopipe.suno.ai/?item_id=")[1]

                #tool and assistant message
                tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': f'updated clip id: {updated_clip_id}\nupdated lyrics: {updated_lyrics}\nupdated clips path: {clips_list}'}
                audio_message = {'role': 'assistant', 'content': f'All done! Thank you for participating :) \nFinal Lyrics: {full_lyrics} \nFinal song: <audio controls autoplay><source src="{updated_clip_url}" type="audio/mp3"></audio><p>clip id: {updated_clip_id}</p>'}

                new_messages = messages + [tool_message, audio_message]
                new_history = messages_to_history(new_messages)
                yield '', new_history, new_messages, '[...]'

            elif tool_function_name == 'get_audio_snippet':
                #detangle tool_query_args dict
                snippet_lyrics = tool_query_args['snippet_lyrics'] + "\n[End]"
                snippet_instrumental_tags = tool_query_args['snippet_instrumental_tags']
                if 'snippet_clip_to_continue_from' not in tool_query_args:
                    tool_query_args['snippet_clip_to_continue_from'] = None
                snippet_clip_to_continue_from = tool_query_args['snippet_clip_to_continue_from']
                song_link = make_song(snippet_lyrics, snippet_instrumental_tags, snippet_clip_to_continue_from)
                ## filter out suno link from tool query arg
                clip_id = song_link.split("https://audiopipe.suno.ai/?item_id=")[1]

                tool_message = {'role': 'tool', 'tool_call_id': tool_call_id, 'name': tool_function_name, 'content': f'instrumental tags: {tool_query_args["snippet_instrumental_tags"]}, clip id: {clip_id}'}
                audio_message_content = "Here's what I've come up with:\n" + snippet_lyrics + '\n\n' + f'<audio controls autoplay><source src="{song_link}" type="audio/mp3"></audio><p>instrumental tags: {tool_query_args["snippet_instrumental_tags"]}</p><p>clip id: {clip_id}</p>'
                audio_message_content += f'<p>continued from clip: {snippet_clip_to_continue_from}</p>'
                audio_message = {'role': 'assistant', 'content': audio_message_content}
                new_messages = messages + [tool_message, audio_message]
                new_history = messages_to_history(new_messages)
                yield '', new_history, new_messages
            else: 
                print(f"Error: function {tool_function_name} does not exist")
                
    #         messages.append({
    #             "role":"tool", 
    #             "tool_call_id":tool_call_id, 
    #             "name": tool_function_name, 
    #             "content":results
    #         })
            
        # Step 4: Invoke the chat completions API with the function response appended to the messages list
        # Note that messages with role 'tool' must be a response to a preceding message with 'tool_calls'
        
    else: 
        # Model did not identify a function to call, result can be returned to the user 
        current_response = response_message.choices[0].message.content

        role = "assistant"
        new_messages = messages + [{'role': role, 'content': current_response}]
        # new_messages = [msg for msg in new_messages if msg['content'] is not None and msg['role'] in ['user', 'assistant']]
        history = messages_to_history(new_messages)
        yield '', history, new_messages, '[...]'