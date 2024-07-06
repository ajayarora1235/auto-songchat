import os
import gradio as gr
from typing import List, Optional, Tuple, Dict
import time
import datetime

def get_current_time() -> str:
    """
    Returns the current time as a formatted string.
    """
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


from gpt_calls import AI_Songwriter

from openai import OpenAI
oai_client = OpenAI(
    api_key=os.getenv("OPEN_AI_KEY"),
)
client_key = os.getenv("OPEN_AI_KEY")
client = OpenAI(
    api_key=os.getenv("OPEN_AI_KEY"),
)

import time
import os
import json
import random

from suno import generate_song, concat_snippets


History = List[Tuple[str, str]] # pairs of (query, response), where query is user input and response is system output
Messages = List[Dict[str, str]] # list of messages with role and content

'''
Genre list
Preset dropdown: Missing Home, Heartbroken, Getting Turnt, Childhood Nostalgia, (Custom) How are you?
- tags based on preset
Artist identity dropdown: A 15-year old boy who dreams of being a broadway actor, A 23-year old soft but bombastic woman who loves to rap, dance, and take over the streets, A 30-year old man who has plans to take over the world as a villain

male tenor, dramatic, emotional, strings

pass artist identity in starting prompt to gpt-4 conversation.
pass preset dropdown to gpt-4 conversation to inspire the questions that Lupe asks the user.

-Ask every 4 back-and-forths do you want to talk more? Or are you ready for your song? (add button for song in assistant's message)

-Mention lyrics
-Mention every 4 back-and-forths lyrics that you’ll include in the song [calling gpt-4 to generate the lyrics and identify one line that's most relevant to the last message]
'''


def clear_session() -> History:
    return '', []

def remove_quotes(s):
    if s[0] == '"' and s[-1] == '"' or s[0] == "'" and s[-1] == "'":
        return s[1:-1]
    return s



def generate_song_seed(baseline_seed):
    song_details_prompt = "Analyze this description of how someone is feeling and provide a suggestion of a interesting song concept to base a song off of. Here are three examples, now provide a song concept for this fourth:\n\n"

    song_seed_prompt ='prompt_song_seed.txt'
    with open(song_seed_prompt, 'r', encoding='utf-8') as file:
        content_2 = file.read() 

    song_details_prompt += "\n\n" + content_2 + baseline_seed + "\nSuggested Song Concept: "

    convo = [
    {
        "role": "user",
        "content": song_details_prompt,
    },
]

    gen = oai_client.chat.completions.create(
        model="gpt-4o",
        messages=convo,
        stream=True
    )

    current_response = ""
    for chunk in gen:
        if chunk.choices[0].delta.content is not None:
            # print ("chunk", chunk.choices[0].delta.content)
            current_response += chunk.choices[0].delta.content
            yield current_response

def clean_song_seed(song_seed):
    if "Suggested Song Concept:" in song_seed:
        song_seed = song_seed.split("Suggested Song Concept:")[1].strip()
    return song_seed

def make_song(snippet_lyrics, snippet_instrumental_tags, snippet_clip_to_continue_from=None, continue_at=None):
    os.makedirs("audio_clips", exist_ok=True)
    song_name = f"SG_{int(time.time())}"
    suno_song_path = f"./audio_clips/suno_{song_name}.wav"
    full_tags = f"{snippet_instrumental_tags}"
    print("Passing to generate_song:", full_tags, snippet_lyrics, suno_song_path)

    if snippet_clip_to_continue_from is not None and snippet_clip_to_continue_from != "":
        song_link = generate_song(full_tags, snippet_lyrics, suno_song_path, snippet_clip_to_continue_from, continue_at)
    else:
        song_link = generate_song(full_tags, snippet_lyrics, suno_song_path)

    return song_link

def messages_to_history(messages: Messages) -> Tuple[str, History]:
    assert messages[0]['role'] == 'system', messages[1]['role'] == 'user'
    messages_for_parsing = messages[:1] + [{'role': 'user', 'content': ''}] + messages[2:]
    print("OLD MESSAGES FOR PARSING", messages_for_parsing)
    messages_for_parsing = [x for x in messages_for_parsing if x['role'] != 'tool' and 'tool_calls' not in x]

    messages_for_parsing = [
        {'role': x['role'], 'content': x['content'].split(" Use write_section")[0]} if x['role'] == 'user' else x 
        for x in messages_for_parsing
    ]
    print("NEW MESSAGES FOR PARSING", messages_for_parsing)
    history = []
    for q, r in zip(messages_for_parsing[1::2], messages_for_parsing[2::2]):
        history.append([q['content'], r['content']])
    # print("made history:\n", history, "from messages\n", messages, "messages for parsing", messages_for_parsing)
    return history


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

                model_response_with_function_call = client.chat.completions.create(
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

                model_response_with_function_call = client.chat.completions.create(
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

def get_sections(overall_meaning, section_list):
    section_list = section_list.split("\n")
    filepath_2='prompt_section_writer.txt'
    with open(filepath_2, 'r', encoding='utf-8') as file:
        content_2 = file.read()

    response = oai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": content_2 + f"\n\nOverall meaning: {overall_meaning}\nSection list: {', '.join(section_list)}\nSection meanings:",
            },
        ],
    )

    text_response = response.choices[0].message.content
    return text_response


def get_starting_messages(song_lengths, song_title, song_blurb, song_genre, init_sections):
    system_prompt = "You are an expert at writing songs. You are with an everyday person, and you will write the lyrics of the song based on this person's life has by asking questions about a story of theirs. Design your questions on your own, without using your tools, to help you understand the user's story, so you can write a song about the user's experience that resonates with them.  We have equipped you with a set of tools to help you write this story; please use them. You are very good at making the user feel comfortable, understood, and ready to share their feelings and story. Occasionally (every 2 messages or so) you will suggest some lyrics, one section at a time, and see what the user thinks of them. Do not suggest or ask for thoughts on more than one section at a time. Be concise and youthful."

    user_prompt = f"I have a story that could make this concept work well. The title is {song_title}, its about {song_blurb} with a genre {song_genre} and I think this should be the structure: {init_sections}\n{song_lengths}"
    
    

    first_msg_res = oai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "The user has stated the following:\n " + user_prompt + "\n Introduce yourself and kick-off the songwriting process with a question."},
        ],
    )

    # if "Section meanings:\n" in init_sections:
    #     init_sections = init_sections.split("Section meanings:\n")[1]
    # else:
    #     if "[" in init_sections:
    #         init_sections = init_sections[init_sections.index("["):]

    # first_message = init_sections + "\n\n" + first_message

    first_message = first_msg_res.choices[0].message.content

    starting_messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt},
        {'role': 'assistant', 'content': first_message},
    ]

    return starting_messages, messages_to_history(starting_messages)
    
# def update_messages_with_lyrics(messages, lyrics):
#     text_to_append = "\n\nHere are the lyrics I came up with!\n\n" + lyrics
#     if messages[-1]['role'] == 'assistant':
#         messages[-1]['content'] += text_to_append
#     elif messages[-1]['role'] == 'user':
#         messages.append({'role': 'assistant', 'content': text_to_append})
#     return messages, messages_to_history(messages)

def change_tab(id):
    return gr.Tabs(selected=id)

with gr.Blocks() as demo:
    gr.Markdown("""<center><font size=8>AI Songwriter (alpha)</center>""")
    gr.Markdown("""<center><font size=4>Turning your stories into musical poetry. 2024 MIT Senior Thesis.</center>""")

    with gr.Tabs() as tabs:
        with gr.TabItem("Ideation", id=0): #index is 0
            gr.Markdown("""<center><font size=6>Let's write a song!</font></center>""")
            gr.Markdown("""<center><font size=4>First, let's try to find an interesting concept. Fill out the fields below and generate a song seed.</font></center>""")
            gr.Markdown("""<center><font size=3>If you're stuck, check out <a href="https://onestopforwriters.com/emotions" target="_blank">here</a>.</font></center>""")
            with gr.Row():
                feeling_input = gr.Textbox(label='How are you feeling today? More vulnerable you are, better the song will be.', placeholder='Enter your emotions', scale=2)
                songwriter_style = gr.Dropdown(label='Songwriter Style', value = "GPT 4o", choices=["GPT 4o", "d4vd (Indie Rock Ballad - Male)", "Lizzy McAlpine (Indie Pop Folk - Female)", "Phoebe Bridgers (Pop Sad Rock - Female)", "Daniel Caesar (R&B/Soul - Male)"], interactive=True)
                # audio_input = gr.Audio(sources=["upload"], type="numpy", label="Instrumental",
                #                 interactive=True, elem_id="instrumental-input")
                
            generate_seed_button = gr.Button("STEP 1: Generate Song Seed")
            concept_desc = gr.Markdown("""<center><font size=4>Here it is! Hit 'Approve' to confirm this concept. Edit the concept directly or hit 'Try Again' to get another suggestion.</font></center>""", visible=False)
            with gr.Row(visible=False) as concept_row:
                instrumental_output = gr.TextArea(label="Suggested Song Concept", value="", max_lines=3, scale=2)
                with gr.Column():
                    approve_button = gr.Button("Approve")
                    try_again_button = gr.Button("Try Again")
            with gr.Row():
                with gr.Accordion("Generated Song Details", open=False) as accordion:
                    with gr.Row():
                        title_input = gr.Textbox(label='Title', placeholder='Enter a song title')
                        genre_input = gr.Textbox(label='Genre', placeholder='Enter a genre')
                        blurb_input = gr.Textbox(label='Blurb', placeholder='Enter a one-sentence blurb')
                        instrumental_textbox = gr.TextArea(label="Song Structure", value="Verse 1: 4 measures\nChorus 1: 8 measures\nVerse 2: 8 measures\nChorus 2: 8 measures\nVerse 3: 8 measures\nChorus 3: 8 measures", interactive=True, max_lines=3)
                    gr.Markdown("""<center><font size=4>Edit these to your liking and hit 'Continue to Next Step' to start creating!</font></center>""")
                
                def open_accordion(x):
                    return gr.Accordion("Generated Song Details", open=True)
                approve_button.click(open_accordion, inputs=[approve_button], outputs=[accordion])
                  
            with gr.Row():
                continue_btn = gr.Button("Continue to Next Step", interactive=False)

            generate_seed_button.click(generate_song_seed, inputs=[feeling_input], outputs=[instrumental_output]).then(clean_song_seed, inputs=[instrumental_output], outputs=[instrumental_output])
            def make_row_visible(x):
                return gr.Row(visible=True), gr.Markdown("""<center><font size=4>Here it is! Hit 'Approve' to confirm this concept. Edit the concept directly or hit 'Try Again' to get another suggestion.</font></center>""", visible=True)
            def enable_button(x):
                return gr.Button("Continue to Next Step", interactive=True)
            generate_seed_button.click(make_row_visible, inputs=[generate_seed_button], outputs=[concept_row, concept_desc])
            approve_button.click(enable_button, inputs=[approve_button], outputs=[continue_btn])

            def update_song_details(instrumental_output):
                song_details_prompt = "Analyze this assessment and suggestion of a song concept to extract the genre, one sentence blurb of what the song is about. Based on this, also suggest a song title. Output exactly three lines, in the format of 'genre: [genre]', 'title: [title]', 'blurb: [blurb]'. "

                song_details_prompt += "\n\n" + instrumental_output

                convo = [
                {
                    "role": "user",
                    "content": song_details_prompt,
                },
            ]

                response = oai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=convo
                )
                response_lines = response.choices[0].message.content.split('\n')
                genre = next((line.split(": ")[1] for line in response_lines if "genre: " in line.lower()), None)
                title = next((line.split(": ")[1] for line in response_lines if "title: " in line.lower()), None)
                blurb = next((line.split(": ")[1] for line in response_lines if "blurb: " in line.lower()), None)
                return genre, title, blurb
            

            section_meanings = gr.State(value="")
            
            try_again_button.click(generate_song_seed, inputs=[feeling_input], outputs=[instrumental_output])
            continue_btn.click(change_tab, gr.Number(1, visible=False), tabs)



        with gr.TabItem("Generation", id=1): #index is 1
            start_song_gen = gr.State(value=False)
            gr.Markdown("""<center><font size=4>Now, chat with an AI songwriter to make your song! Tip: get and tune an audio snippet well first and then put effort into the story. Hit finish when ready to hear full song.</font></center>""")        
            generate_lyrics = gr.Button("STEP 2: Write a song with the AIs!")
            
            character = gr.State(value="A 18-year old boy who dreams of being a pop star that uplifts people going through the difficulties of life")

            starting_messages, starting_history = get_starting_messages("", "Home", "Missing home", "Ballad", instrumental_textbox.value)

            messages = gr.State(value=starting_messages)
            # journal_messages = gr.State(value=[journal_starting_message])
            # journal_response = gr.State(value="")

            with gr.Row():
                chatbot_history = gr.Chatbot(value=starting_history, label='SongChat', placeholder=None, layout='bubble', bubble_full_width=False, height=500, scale=2)
                with gr.Column():
                    songwriter_creativity = gr.Slider(label="Songwriter LLM Temperature", minimum=0, maximum=1, step=0.01, value=1)
                    lyrics_display = gr.TextArea("[...]", label="Generated Lyrics", show_copy_button=True, container=True)

            approve_button.click(update_song_details, inputs=[instrumental_output], outputs=[genre_input, title_input, blurb_input]).then(get_sections, inputs=[blurb_input, instrumental_output], outputs=[section_meanings])
            continue_btn.click(get_starting_messages, inputs=[instrumental_textbox, title_input, blurb_input, genre_input, section_meanings], outputs=[messages, chatbot_history])
            
            with gr.Row():
                textbox = gr.Textbox(lines=1, label='Send a message', show_label=False, placeholder='Send a message', scale=4)
                    # melody_recorder = gr.Audio(
                    #     sources=["microphone"],
                    #     label="Record Melody to suggest",
                    #     waveform_options=gr.WaveformOptions(
                    #         waveform_color="#01C6FF",
                    #         waveform_progress_color="#0066B4",
                    #         skip_length=2,
                    #         show_controls=False,
                    #     ),
                    # )
                # clear_history = gr.Button("🧹 Clear history", visible=False)
                submit = gr.Button("Send", scale=2)

            with gr.Row():
                get_snippet_button = gr.Button("Get Audio Snippet", scale=2)
                done = gr.Button("Finish Full Song 🎶", scale=2)
                #autoGPT_checkbox = gr.Checkbox(label="AutoGPT", value=True, info="Auto-generate responses from journal entry", interactive=True, scale=2)
                #journal_llm_creativity = gr.Slider(label="Journal LLM Temperature", minimum=0, maximum=1, step=0.01, value=1, interactive=True, scale=2)
                reset_button = gr.Button("Reset", scale=2)
            
                def reset_chat(messages, chatbot_history):
                    messages = messages[:2]
                    chatbot_history = messages_to_history(messages[:2])
                    return messages, chatbot_history, ''
                
                reset_button.click(reset_chat, inputs=[messages, chatbot_history], outputs=[messages, chatbot_history, lyrics_display])

            
            # generate_seed_button.click(get_starting_messages, inputs=[character, title_input, blurb_input, preset, genre_input, instrumental_textbox], outputs=[messages, chatbot_history])

            # def get_conversation(story_textbox, chatbot_history, messages):
            #     curr_chatbot_value = chatbot_history.copy()
            #     curr_messages_value = messages.copy()
            #     for i in range(3):
            #         for journal_response_value, chatbot_history_value, messages_value in get_journal_response(story_textbox, curr_chatbot_value, curr_messages_value):
            #             curr_chatbot_value = chatbot_history_value
            #             curr_messages_value = messages_value
            #             journal_response.value = journal_response_value
            #             yield chatbot_history_value, messages_value

            #         for _, chatbot_history_value, messages_value in model_chat(journal_response_value, curr_chatbot_value, curr_messages_value, auto=True):
            #             # Update the gr.State objects
            #             curr_chatbot_value = chatbot_history_value
            #             curr_messages_value = messages_value
            #             yield chatbot_history_value, messages_value
            

            with gr.Row():
                song_link = gr.State(value="")
                song = gr.HTML()
            
            download_btn = gr.Button("Download Conversation")

            def download_conversation(messages):
                #get time
                now = get_current_time()
                # write messages to JSON file
                with open(f'conversation_{now}.json', 'w') as f:
                    json.dump(messages, f)


            # with gr.Row():
            #   song = gr.Audio(label='Song', format="bytes", streaming=True) # type='filepath', sources=[])
            #   with gr.Accordion("Show Lyrics", open=True):
            #     lyrics_display = gr.Markdown("[...]")
                # song_tags = gr.Markdown("")
            
            # with gr.Accordion("Advanced", open=False):
            #     suno_tags = gr.Textbox(value="ballad, male, dramatic, emotional, strings", label="Gen input tags")
            #     story_textbox = gr.TextArea(label="Story to provide context to songwriter", value="", max_lines=3)

            # genre_input.blur(get_starting_messages, inputs=[character, preset, genre_input], outputs=[messages, chatbot_history])

            def lyrics_from_convo(self, messages, character_preset, section_list, temperature=1.0):
                conversation_text = ""
                for m in messages[1:]:
                    name = "Lupe" if m['role'] == 'assistant' else "User"
                    conversation_text += f"{name}: {m['content']}\n"

                section_list = [x[:x.index(':')] + " (" + x[x.index(':')+2:] + ")" for x in section_list.split("\n")]
                
                filepath='./prompt_lyrics_from_convo.txt'
                with open(filepath, 'r', encoding='utf-8') as file:
                    prompt = file.read()
                prompt  = prompt.replace("{conversation_text}", conversation_text).replace("{a songwriter from NYC}", character_preset)
                prompt += "\nSections: " + ", ".join(section_list)
                convo = [
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ]
                response = self.oai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=convo,
                    stream=True,
                    temperature=temperature
                ) 

                current_response = ""
                for chunk in response:
                    if chunk.choices[0].delta.content is not None:
                        # print ("chunk", chunk.choices[0].delta.content)
                        current_response += chunk.choices[0].delta.content
                        yield "\n".join(current_response.split("\n")[1:])

            # generate_lyrics.click(get_conversation, inputs=[story_textbox, chatbot_history, messages], outputs=[chatbot_history, messages]).then(lyrics_from_convo, inputs=[messages, character, instrumental_textbox, songwriter_creativity], outputs=[lyrics_display])
            
            def reset_textbox(textbox):
                return ""
            def set_snippet_query(textbox):
                return "Can I have an audio snippet of what we have now?"
            def set_finish_query(textbox):
                return "I'm ready for the full song now! Can you finish it up?"
            def set_lyrics_song_displays(messages):
                final_message = messages[-1]['content']
                final_lyrics = final_message.split("Final Lyrics:")[1].split("Final song:")[0].strip("\n ")
                song = final_message.split("Final song:")[1].strip("\n ")
                return final_lyrics, song

            submit.click(model_chat,
                        inputs=[genre_input, textbox, chatbot_history, messages],
                        outputs=[textbox, chatbot_history, messages, lyrics_display]).then(reset_textbox, inputs=[textbox], outputs=[textbox])
            textbox.submit(model_chat, 
                        inputs=[genre_input, textbox, chatbot_history, messages], 
                        outputs=[textbox, chatbot_history, messages, lyrics_display]).then(reset_textbox, inputs=[textbox], outputs=[textbox])
            
            get_snippet_button.click(set_snippet_query, inputs=[textbox], outputs=[textbox]).then(model_chat,
                        inputs=[genre_input, textbox, chatbot_history, messages],
                        outputs=[textbox, chatbot_history, messages]).then(reset_textbox, inputs=[textbox], outputs=[textbox])

            # start.click(make_song,
            #             inputs=[genre_input, lyrics_display, suno_tags], outputs=[song])
            
            done.click(set_finish_query, inputs=[textbox], outputs=[textbox]).then(model_chat,
                        inputs=[genre_input, textbox, chatbot_history, messages],
                        outputs=[textbox, chatbot_history, messages, lyrics_display]).then(
                            set_lyrics_song_displays, inputs=[messages], outputs=[lyrics_display, song]).then(reset_textbox, inputs=[textbox], outputs=[textbox])
                        



demo.queue(api_open=False)
demo.launch(max_threads=30)
