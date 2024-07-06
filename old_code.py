            # open_step_two = gr.Button("STEP 2: Pick a story (REQUIRED FOR AUTOGPT)")
            # journal_entries_visible = gr.State(value=False)


            # # Preset dropdown: Missing Home, Heartbroken, Getting Turnt, Childhood Nostalgia, (Custom) How are you?

            # story_choices = [
            #     "ENTER YOUR OWN", 
            #     "Missing Home after a lonely night",
            #     "Heartbroken after the fourth date",
            #     "Getting Turnt after making it big",
            #     "Childhood Nostalgia",
            #     "Falling in Love on the train",
            #     "Self-questioning after my first big song failure",
            #     "The night in Spain with the crazy Manchester girl",
            #     "Blacking out my last night in NOLA",
            #     "My first concert: the Off-Season tour",
            #     "The night I got my first tattoo",
            #     "The summer after high school (Kaylee)",
            #     "Deciding to take control of shit",
            #     "The DJ had us falling in love",
            #     "Why does drinking feel so good",
            #     "The camera girl from Royale",
            #     "St. Patty's with the boys",
            #     "Losing my VVVVV",
            #     "In love with the idea of success",
            #     "Summer nights in Washington Square Park",
            #     "All I'm asking for is just one night",
            #     "I don't think imma make it"
            # ]

            # with gr.Row(visible=journal_entries_visible):
            #     preset = gr.Dropdown(
            #         label="Journal entries",
            #         choices=story_choices,
            #         value="",
            #         interactive=True,
            #     )
            #     entry_text = {
            #         "The night in Spain with the crazy Manchester girl": "data/journals/manchester_girl.txt",
            #         "Missing Home after a lonely night": "data/journals/missing_home.txt",
            #         "Heartbroken after the fourth date": "data/journals/heartbroken.txt",
            #     }


            #     with gr.Column():
            #         journal_title = gr.Textbox(label="Journal Title")
            #         
            #         add_story_button = gr.Button("Add Story")

            #     def update_story_textbox(preset):
            #         return gr.TextArea(label="Full Story", value=open(entry_text[preset]).read(), max_lines=3)
                
            #     def save_journal_entry(journal_title_value, story_textbox_value):
            #         song_path = f"data/journals/{journal_title.value}.txt"
            #         with open("data/journals/custom_journal.txt", "w") as f:
            #             f.write(story_textbox_value)

            #     preset.change(update_story_textbox, inputs=[preset], outputs=[story_textbox])

                
            
            # # Toggle visibility when button is clicked
            # def toggle_journal_entries():
            #     return not journal_entries_visible.value

            # open_step_two.click(toggle_journal_entries, outputs=[journal_entries_visible])