from typing import List, Tuple, Dict
import gradio as gr
import os
import json

from utils.song_utils import generate_song_seed, get_starting_messages, messages_to_history, update_song_details, get_sections
from chat import model_chat
from gradio_modal import Modal

History = List[Tuple[str, str]] # a type: pairs of (query, response), where query is user input and response is system output
Messages = List[Dict[str, str]] # a type: list of messages with role and content

css = """
#audio-group {
    max-height: 800px;
    overflow-y: scroll;
}
"""

textbox = gr.Textbox(lines=2, label='Send a message', show_label=False, placeholder='Send a message', scale=4, visible=True)
submit = gr.Button("Send", scale=2, visible=True)


with gr.Blocks(css=css) as demo:
    gr.Markdown("""<center><font size=8>AI Songwriter (alpha)</center>""")
    gr.Markdown("""<center><font size=4>Turning your stories into musical poetry. 2024 MIT Senior Thesis.</center>""")

    with gr.Tabs() as tabs:
        with gr.TabItem("Ideation", id=0): #index is 0
            gr.Markdown("""<center><font size=6>Let's write a song!</font></center>""")
            gr.Markdown("""<center><font size=4>But first, let's generate a song seed to provide context to the AI Songwriter.</font></center>""")
            gr.Markdown("""<center><font size=3>If you're stuck thinking of a song idea, check out <a href="https://onestopforwriters.com/emotions" target="_blank">here</a>.</font></center>""")
            with gr.Row():
                feeling_input = gr.Textbox(label="How are you feeling today?", placeholder='Enter your emotions', scale=2)
                # audio_input = gr.Audio(sources=["upload"], type="numpy", label="Instrumental",
                #                 interactive=True, elem_id="instrumental-input")
                
            generate_seed_button = gr.Button("Click to Generate Song Seed")
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
                        songwriter_style = gr.Dropdown(label='Songwriter Style', value = "GPT 4o", choices=["GPT 4o", "d4vd (Indie Rock Ballad - Male)", "Lizzy McAlpine (Indie Pop Folk - Female)", "Phoebe Bridgers (Pop Sad Rock - Female)", "Daniel Caesar (R&B/Soul - Male)"], interactive=True)
                
                        instrumental_textbox = gr.TextArea(label="Song Structure", value="Verse 1: 4 measures\nChorus 1: 8 measures\nVerse 2: 8 measures\nChorus 2: 8 measures\nVerse 3: 8 measures\nChorus 3: 8 measures", visible=False, interactive=True, max_lines=3)
                    gr.Markdown("""<center><font size=4>Edit these to your liking and hit 'Continue to Next Step' to start creating!</font></center>""")
                
                def open_accordion(x):
                    return gr.Accordion("Generated Song Details", open=True)
                approve_button.click(open_accordion, inputs=[approve_button], outputs=[accordion])
                  
            with gr.Row():
                continue_btn = gr.Button("Ready to Create", interactive=False)

            
            def clean_song_seed(song_seed):
                if "Suggested Song Concept:" in song_seed:
                    song_seed = song_seed.split("Suggested Song Concept:")[1].strip()
                return song_seed
            generate_seed_button.click(generate_song_seed, inputs=[feeling_input], outputs=[instrumental_output]).then(clean_song_seed, inputs=[instrumental_output], outputs=[instrumental_output])
            feeling_input.submit(generate_song_seed, inputs=[feeling_input], outputs=[instrumental_output]).then(clean_song_seed, inputs=[instrumental_output], outputs=[instrumental_output])
            
            def make_row_visible(x):
                return gr.Row(visible=True), gr.Markdown("""<center><font size=4>Here it is! Hit 'Approve' to confirm this concept. Edit the concept directly or hit 'Try Again' to get another suggestion.</font></center>""", visible=False)
            def enable_button(x):
                return gr.Button("Ready to Create", interactive=True)
            generate_seed_button.click(make_row_visible, inputs=[generate_seed_button], outputs=[concept_row, concept_desc])
            feeling_input.submit(make_row_visible, inputs=[generate_seed_button], outputs=[concept_row, concept_desc])
            approve_button.click(enable_button, inputs=[approve_button], outputs=[continue_btn])
            
            try_again_button.click(generate_song_seed, inputs=[feeling_input], outputs=[instrumental_output])
            
            def change_tab(id):
                return gr.Tabs(selected=id)
            continue_btn.click(change_tab, gr.Number(1, visible=False), tabs)            
                
        
        with gr.TabItem("Generation", id=1): #index is 1
            start_song_gen = gr.State(value=False)
            gr.Markdown("""<center><font size=4>Now, chat with an AI songwriter to make your song!</font></center>""")        

            character = gr.State(value="A 18-year old boy who dreams of being a pop star that uplifts people going through the difficulties of life")

            starting_messages, starting_history = get_starting_messages("", "Home", "Missing home", "Ballad", instrumental_textbox.value)
            print(starting_history, "STARTING HISTORY")
            messages = gr.State(value=starting_messages)
            # messages += [{"role": "assistant", "content": "You are a songwriter. You write songs."}]
            # journal_messages = gr.State(value=[journal_starting_message])
            # journal_response = gr.State(value="")

            generated_audios = gr.State(value=[])
            tutorial_step = gr.Number(value=0, visible=False)

            with gr.Row():
                with gr.Column(scale=2):
                    chatbot_history = gr.Chatbot(type="messages", value=starting_history, label='SongChat', placeholder=None, layout='bubble', bubble_full_width=False, height=500)
                    with gr.Row():
                        typical_responses = [textbox, submit]
                        
                        def update_response_options(buttons, button_dict):
                            return [gr.Textbox(visible=len(buttons)==0, scale=4), gr.Button(visible=len(buttons)==0, scale=2)] + [gr.Button(visible=(x in buttons)) for x in button_dict.keys()]

                        button_options = gr.State([])
                        button_dict = gr.State({
                            "revise lyrics": "Can we revise the lyrics together?",
                            "re-revise lyrics": "Can we revise the lyrics together?", 
                            "edit lyrics directly": "Can I edit the lyrics directly for the whole section?",
                            "generate audio snippet": "Can you generate an audio snippet?", 
                            "continue revising" : "Can we continue revising this section?", 
                            "generate audio snippet with new lyrics": "Can you generate an audio snippet with these new lyrics?", 
                            "return to original instrumental": "Can you use the original clip for this section instead?", 
                            "revise genre": "Can we revise the instrumental tags together?",
                            "re-revise genre": "Can we revise the instrumental tags together?", 
                            "revise genre directly": "Can I edit the genre directly for the whole song?",
                            "continue to next section": "Looks good! Let's move on to the next section.",
                            "merge snippets": "Can you merge this snippet into its full song?"
                        })

                        for button in button_dict.value.keys():
                            btn = gr.Button(button, visible=(button in button_options.value))
                            typical_responses.append(btn)


                with gr.Column(elem_id="audio-group", scale=1, visible=False):
                    # songwriter_creativity = gr.Slider(label="Songwriter LLM Temperature", minimum=0, maximum=1, step=0.01, value=1)

                    with gr.Group():
                        # loop thru all audio in audio_clips
                        gr.Markdown("""<center><font size=4>All Generations</font></center>""")

                        @gr.render(inputs=generated_audios, triggers=[demo.load, generated_audios.change, textbox.submit, submit.click] + [btn.click for btn in typical_responses[2:]])
                        def render_audio_group(generated_audios):
                            # audio_group = gr.Group()
                            for audio in generated_audios:
                                clip_path, lyrics, instrumental, title, status = audio
                                with gr.Accordion(title, open=False):
                                    if status == 'complete':
                                        gr.Audio(value=clip_path, label=title, interactive=False, show_label=False, waveform_options={"show_controls": False})
                                    else:
                                        gr.HTML(f'<audio controls><source src="{clip_path}" type="audio/mp3"></audio>')
                                    gr.TextArea(label="Lyrics", value=lyrics, interactive=False, show_label=False)
                                    gr.TextArea(label="Instrumental", value=instrumental, interactive=False, show_label=False, max_lines=1)

                        gr.Markdown("""<center><font size=4>Edit Current Generation</font></center>""")
                        current_section = gr.Textbox(label="Current section", value="Verse 1", interactive=False, show_label=True)
                        current_lyrics = gr.Textbox(label="Lyrics", value="", interactive=True, show_label=True)
                        with gr.Row():
                            curr_tags = gr.Textbox(label="Instrumental Tags", value="", interactive=True, show_label=True)
                            # @gr.render(inputs=generated_audios, triggers=[demo.load])
                            # def render_clip_to_continue(generated_audios):
                            audio_clips = [x[3] for x in generated_audios.value]
                            clip_to_continue = gr.Dropdown(label='Clip to continue', value = "", choices=audio_clips+[""], interactive=True)
                        #clip_to_continue = gr.Dropdown(label='Clip to continue', value = "", choices=audio_clips+[""], interactive=True)
                        songwriter_style = gr.Dropdown(label='Songwriter Style', value= "GPT 4o", choices=["GPT 4o", "d4vd (Indie Rock Ballad - Male)", "Lizzy McAlpine (Indie Pop Folk - Female)", "Phoebe Bridgers (Pop Sad Rock - Female)", "Daniel Caesar (R&B/Soul - Male)"], interactive=True)
                        with gr.Row():
                            #curr_audio = gr.State("")
                            curr_audio = gr.HTML(label="Generated section")
                            regen = gr.Button("Submit edits")
                        
            
            section_meanings = gr.State(value="")
            approve_button.click(update_song_details, inputs=[instrumental_output], outputs=[genre_input, title_input, blurb_input]).then(get_sections, inputs=[blurb_input, instrumental_output], outputs=[section_meanings])
            continue_btn.click(get_starting_messages, inputs=[instrumental_textbox, title_input, blurb_input, genre_input, section_meanings], outputs=[messages, chatbot_history])

            with Modal(visible=False) as modal_0:
                gr.Markdown("Welcome to the AI songwriter! The AI songwriter is a chatbot that will help you write a song. You can chat with the AI and guide it however you'd like. Let's start by chatting with the AI.")
            with Modal(visible=False) as modal:
                gr.Markdown("The AI songwriter can respond to your stories and requests, generate lyrics and audio, and edit prior generations.\n\nNow, continue and respond to this second question from the AI songwriter to get to know you.")
            with Modal(visible=False) as modal_1:
                gr.Markdown("The AI songwriter has now proposed a first verse! After each generation from the AI, you'll receive a list of buttons to guide it further. Select the 'get audio snippet' button to continue to the next step.")
            with Modal(visible=False) as modal_2:
                gr.Markdown("Awesome! You generated your first audio snippet. The songwriter will continue for the each section for the rest of the song, revising and iterating with you. \n"
                            "As the song gets generated, feel free to ask the songwriter any questions or guide it in any direction. \n"
                            "You're ready to start your study with the AI Songwriter! Hit the 'Start' button to start.")
                start_button = gr.Button("Start")
            
            continue_btn.click(lambda: Modal(visible=True), None, modal_0)
            start_button.click(lambda: Modal(visible=False), None, modal_2)

            def make_modal_visible(step_number):
                new_step_number = step_number + 1 if step_number in [0, 1, 2] else step_number
                modals = [Modal(visible=i == step_number) for i in range(3)]
                return new_step_number, *modals
            
            def update_textbox(textbox, step_number):
                print("on step number", step_number)
                if step_number == 0:
                    return textbox + "\nAsk me another question to inform the verse"
                elif step_number == 1:
                    return textbox + "\nUse this info to write a verse"
                else:
                    return textbox
            
            def set_response_buttons(button_dict, button_name):
                print(button_name)
                return button_dict[button_name]

            def set_regenerate_query(textbox, current_section, current_lyrics, curr_tags, clip_to_continue):
                return f"Can you revise this section so it uses these lyrics and instrumentals and then generate an audio snippet using it?\nLyrics:\n{current_lyrics}Instrumental tags: {curr_tags}"
            def set_snippet_query(textbox):
                return "Can I have an audio snippet of what we have now?"
            def set_finish_query(textbox):
                return "I'm ready for the full song now! Can you finish it up?"
            def reset_textbox(textbox):
                return ""
            
            with gr.Row():
                textbox.render()
                submit.render()

                for btn in typical_responses[2:]:
                    btn.click(set_response_buttons, inputs=[button_dict, btn], outputs=[textbox]).then(model_chat, 
                                    inputs=[genre_input, textbox, chatbot_history, messages, generated_audios], 
                                    outputs=[textbox, chatbot_history, messages, current_section, current_lyrics, curr_tags, clip_to_continue, curr_audio, generated_audios, button_options]).then(
                                    update_response_options, [button_options, button_dict], typical_responses
                            ).then(
                            make_modal_visible, [tutorial_step], [tutorial_step, modal, modal_1, modal_2]
                        )

    


            submit.click(update_textbox, [textbox, tutorial_step], [textbox]).then(model_chat,
                inputs=[genre_input, textbox, chatbot_history, messages, generated_audios],
                outputs=[textbox, chatbot_history, messages, current_section, current_lyrics, curr_tags, clip_to_continue, curr_audio, generated_audios, button_options]).then(
                        update_response_options, [button_options, button_dict], typical_responses
                ).then(
                            make_modal_visible, [tutorial_step], [tutorial_step, modal, modal_1, modal_2]
                        )
            textbox.submit(update_textbox, [textbox, tutorial_step], [textbox]).then(model_chat, 
                inputs=[genre_input, textbox, chatbot_history, messages, generated_audios], 
                outputs=[textbox, chatbot_history, messages, current_section, current_lyrics, curr_tags, clip_to_continue, curr_audio, generated_audios, button_options]).then(
                        update_response_options, [button_options, button_dict], typical_responses
                ).then(
                            make_modal_visible, [tutorial_step], [tutorial_step, modal, modal_1, modal_2]
                        )
            
            
            regen.click(set_regenerate_query, inputs=[textbox, current_section, current_lyrics, curr_tags, clip_to_continue], outputs=[textbox]).then(model_chat,
                inputs=[genre_input, textbox, chatbot_history, messages, generated_audios],
                outputs=[textbox, chatbot_history, messages, current_section, current_lyrics, curr_tags, clip_to_continue, curr_audio, generated_audios, button_options]).then(
                        update_response_options, [button_options, button_dict], typical_responses
                ).then(
                            make_modal_visible, [tutorial_step], [tutorial_step, modal, modal_1, modal_2]
                        )

            with gr.Row(visible=True):
                # get_snippet_button = gr.Button("Get Audio Snippet", scale=2)
                done = gr.Button("Complete User Study 🎶", scale=4)
                #autoGPT_checkbox = gr.Checkbox(label="AutoGPT", value=True, info="Auto-generate responses from journal entry", interactive=True, scale=2)
                #journal_llm_creativity = gr.Slider(label="Journal LLM Temperature", minimum=0, maximum=1, step=0.01, value=1, interactive=True, scale=2)
                reset_button = gr.Button("Reset", scale=2)
            
                def reset_chat(messages, chatbot_history):
                    messages = messages[:3]
                    chatbot_history = messages_to_history(messages[:3])
                    return messages, chatbot_history, '', '', '', '', gr.HTML('<center>generating...</center>'), [], []
                
                reset_button.click(reset_chat, inputs=[messages, chatbot_history], outputs=[messages, chatbot_history, current_section, current_lyrics, curr_tags, clip_to_continue, curr_audio, generated_audios, button_options]).then(
                        update_response_options, [button_options, button_dict], typical_responses
                )
            

            done.click(set_finish_query, inputs=[textbox], outputs=[textbox]).then(model_chat,
                inputs=[genre_input, textbox, chatbot_history, messages, generated_audios],
                outputs=[textbox, chatbot_history, messages, current_section, current_lyrics, curr_tags, clip_to_continue, curr_audio, generated_audios, button_options]).then(
                        update_response_options, [button_options, button_dict], typical_responses
                )

            demo.load(reset_chat, inputs=[messages, chatbot_history], outputs=[messages, chatbot_history, current_section, current_lyrics, curr_tags, clip_to_continue, curr_audio, generated_audios, button_options]).then(
                        update_response_options, [button_options, button_dict], typical_responses
                )
            
            
            # with gr.Row():
            #     song_link = gr.State(value="")
            #     song = gr.HTML()
            


            def download_conversation(messages):
                with open(f'data/conversation_history.json', 'w') as f:
                    json.dump(messages, f)

            
            with gr.Accordion("Admin", open=False):
                download_btn = gr.Button("Download Conversation")
                download_btn.click(download_conversation, [messages], None)
            #     story_textbox = gr.TextArea(label="Story to provide context to songwriter", value="", max_lines=3)

            
            # get_snippet_button.click(set_snippet_query, inputs=[textbox], outputs=[textbox]).then(model_chat,
            #             inputs=[genre_input, textbox, chatbot_history, messages, generated_audios],
            #             outputs=[textbox, chatbot_history, messages, current_section, current_lyrics, curr_tags, clip_to_continue, curr_audio, generated_audios]).then(reset_textbox, inputs=[textbox], outputs=[textbox])



demo.queue(api_open=False)
demo.launch(max_threads=30)
