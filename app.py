from typing import List, Tuple, Dict
import gradio as gr

from utils.song_utils import generate_song_seed, get_starting_messages, messages_to_history, update_song_details, get_sections
from chat import model_chat
from openai import OpenAI

History = List[Tuple[str, str]] # a type: pairs of (query, response), where query is user input and response is system output
Messages = List[Dict[str, str]] # a type: list of messages with role and content

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

            
            def clean_song_seed(song_seed):
                if "Suggested Song Concept:" in song_seed:
                    song_seed = song_seed.split("Suggested Song Concept:")[1].strip()
                return song_seed
            generate_seed_button.click(generate_song_seed, inputs=[feeling_input], outputs=[instrumental_output]).then(clean_song_seed, inputs=[instrumental_output], outputs=[instrumental_output])
            
            def make_row_visible(x):
                return gr.Row(visible=True), gr.Markdown("""<center><font size=4>Here it is! Hit 'Approve' to confirm this concept. Edit the concept directly or hit 'Try Again' to get another suggestion.</font></center>""", visible=True)
            def enable_button(x):
                return gr.Button("Continue to Next Step", interactive=True)
            generate_seed_button.click(make_row_visible, inputs=[generate_seed_button], outputs=[concept_row, concept_desc])
            approve_button.click(enable_button, inputs=[approve_button], outputs=[continue_btn])
            
            try_again_button.click(generate_song_seed, inputs=[feeling_input], outputs=[instrumental_output])
            
            def change_tab(id):
                return gr.Tabs(selected=id)
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

            section_meanings = gr.State(value="")
            approve_button.click(update_song_details, inputs=[instrumental_output], outputs=[genre_input, title_input, blurb_input]).then(get_sections, inputs=[blurb_input, instrumental_output], outputs=[section_meanings])
            continue_btn.click(get_starting_messages, inputs=[instrumental_textbox, title_input, blurb_input, genre_input, section_meanings], outputs=[messages, chatbot_history])
            
            with gr.Row():
                textbox = gr.Textbox(lines=1, label='Send a message', show_label=False, placeholder='Send a message', scale=4)
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
            

            with gr.Row():
                song_link = gr.State(value="")
                song = gr.HTML()
            
            # download_btn = gr.Button("Download Conversation")

            # def download_conversation(messages):
            #     #get time
            #     now = get_current_time()
            #     # write messages to JSON file
            #     with open(f'conversation_{now}.json', 'w') as f:
            #         json.dump(messages, f)

            
            # with gr.Accordion("Advanced", open=False):
            #     suno_tags = gr.Textbox(value="ballad, male, dramatic, emotional, strings", label="Gen input tags")
            #     story_textbox = gr.TextArea(label="Story to provide context to songwriter", value="", max_lines=3)


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

            done.click(set_finish_query, inputs=[textbox], outputs=[textbox]).then(model_chat,
                        inputs=[genre_input, textbox, chatbot_history, messages],
                        outputs=[textbox, chatbot_history, messages, lyrics_display]).then(
                            set_lyrics_song_displays, inputs=[messages], outputs=[lyrics_display, song]).then(reset_textbox, inputs=[textbox], outputs=[textbox])


demo.queue(api_open=False)
demo.launch(max_threads=30)
