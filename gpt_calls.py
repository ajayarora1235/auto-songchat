from openai import OpenAI
# from unsloth import FastLanguageModel

class AI_Songwriter:
    def __init__(self, client_key):
        self.oai_client = OpenAI(api_key=client_key)

        # max_seq_length = 3072 # Choose any! We auto support RoPE Scaling internally!
        # dtype = None # None for auto detection. Float16 for Tesla T4, V100, Bfloat16 for Ampere+
        # load_in_4bit = True # Use 4bit quantization to reduce memory usage. Can be False.
            
        # model, tokenizer = FastLanguageModel.from_pretrained(
        #     model_name = "lora_model", # YOUR MODEL YOU USED FOR TRAINING
        #     max_seq_length = max_seq_length,
        #     dtype = dtype,
        #     load_in_4bit = load_in_4bit,
        # )
        # FastLanguageModel.for_inference(model) # Enable native 2x faster inference

        # self.model=model
        # self.tokenizer=tokenizer

        self.alpaca_prompt = """Below is an instruction that describes a songwriting task, paired with an input that provides further context. Write a response that appropriately completes the request.
        ### Instruction:
        {}

        ### Input:
        {}

        ### Response:
        {}"""


    
    def ask_question(self, messages):
        convo = messages[:-1]

        instruction = "Based on this conversation history, respond to the user acknowledging their most recent response and ask a concise question to further learn more about the user's story."

        ## iterate thru messages and format them into a single string where each message is separated by a newline (ie Assistant: ...\n User: ...\n)
        convo_str = ""
        for message in convo:
            convo_str += f"{message['role']}: {message['content']}\n"
        convo_str += "Assistant:"

        input = f"{instruction}\nConversation History:\n{convo_str}"
        
        response = self.oai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": input
                }
            ],
        )

        return response.choices[0].message.content

    
    def write_section(self, section_name, section_description, relevant_ideas, section_length, sections_written=None, overall_song_description=None):
        instruction = f"Write a {section_name} of length {section_length} that that incorporates the following ideas"
        if sections_written is not None:
            instruction += "and complements the sections provided."
        else:
            instruction += "."
        instruction += "You are also given a section description, genre, era, and overall description of the song. Please do not literally quote and incorporate the ideas - be poetic and incorporate them artistically to express the emotion. "

        ## read in prompt lyrics from convo .txt and add it to instruction
        with open("prompts/write_section_ex.txt", "r") as f:
            convo = f.read()
        instruction += "Here's an example:\n{convo}\nNow do it for this input:"
        
        input = f"""Ideas to use:
                  - {relevant_ideas}
                  Section Description: {section_description}
                  Genre: Songwriter Pop
                  Era: 2010s
                  Overall song description: {overall_song_description}
                  """
        if sections_written is not None:
          written_sections = "\n".join(sections_written)
          input += f"Sections provided:\n{written_sections}\nLyrics:"
        else:
            input += "\nLyrics:"

        prompt = self.alpaca_prompt.format(instruction, input, "")

        convo = [
            {
                "role": "user",
                "content": prompt,
            },
        ]
        response = self.oai_client.chat.completions.create(
            model="gpt-4o",
            messages=convo,
        ) 

        return "Pass this back to the user and ask if they would like to receive an audio snippet or make any revisions before moving to the next section: \n" + response.choices[0].message.content

    def revise_section_lyrics(self, section_name, current_section, lines_to_revise, relevant_ideas=None, relevant_words=None):
        lines_to_infill = ", ".join([str(x) for x in lines_to_revise])

        full_incomplete_verse = current_section.strip("\n ").split("\n")

        max_line_num = max(lines_to_revise)
        if max_line_num > len(full_incomplete_verse):
            full_incomplete_verse.extend([''] * (max_line_num - len(full_incomplete_verse)))

        for line_num in lines_to_revise:
            if line_num <= len(full_incomplete_verse):
                full_incomplete_verse[line_num-1] = '___'

        line_phrase = "lines" if len(lines_to_infill) > 1 else "line"
        line_phrase = str(len(lines_to_infill)) + " " + line_phrase

        instruction = f"Infill the remaining {line_phrase} into {section_name}"

        if relevant_ideas is not None or relevant_words is not None:
            instruction += " while incorporating the following "
            if relevant_ideas is not None:
                instruction += "ideas"
                if relevant_words is not None:
                    instruction += "and words."
                else:
                    instruction += "."
            else:
                instruction += "words."
        else:
            instruction += "."
        
        instruction += "You are also given a genre, era, and the rest of the section. Please do not literally quote and incorporate the ideas - be poetic and incorporate them artistically to express the emotion. "
        
        with open("prompts/revise_section_ex.txt", "r") as f:
            convo = f.read()
        instruction += "Here's an example:\n{convo}\nNow do it for this input:"
        
        
        input = ""
        if relevant_ideas is not None and isinstance(relevant_ideas, list):
            input += f"Ideas to use: {', '.join(relevant_ideas)}\n"
        if relevant_words is not None and isinstance(relevant_words, list):
            input += f"Words to use: {', '.join(relevant_words)}\n"
        input += f"Genre: Songwriter Pop\nEra: 2010s\nCurrent section:\n{full_incomplete_verse}\n\nLyrics:"

        prompt = self.alpaca_prompt.format(instruction, input, "")

        convo = [
            {
                "role": "user",
                "content": prompt,
            },
        ]
        response = self.oai_client.chat.completions.create(
            model="gpt-4o",
            messages=convo,
        ) 

        return response.choices[0].message.content

    def revise_instrumental_tags(self, current_instrumental_tags, user_instrumental_feedback):
        instruction = "Revise the current instrumental tags to better match the feedback provided:"
        input = f"""Current instrumental tags: {current_instrumental_tags}\ninstrumental feedback: {user_instrumental_feedback}\nNew tags:"""
        prompt = self.alpaca_prompt.format(instruction, input, "")

        convo = [
            {
                "role": "user",
                "content": prompt,
            },
        ]
        response = self.oai_client.chat.completions.create(
            model="gpt-4o",
            messages=convo,
        )

        return response.choices[0].message.content.split("New tags:")[-1].strip("\n ")

    def write_all_lyrics(self, sections_to_be_written, sections_written, overall_song_description):
        instruction = "Write the remainder of this full song given an overall description of the song, genre, era, and a description of the sections to complete:"
        
        with open("prompts/write_full_song_ex.txt", "r") as f:
            convo = f.read()
        instruction += "Here's an example:\n{convo}\nNow do it for this input:"
        
        
        sections_to_write = [x['section_name'] for x in sections_to_be_written]
        sections_to_write_str = ", ".join(sections_to_write)
        section_descriptions = [x['section_description'] for x in sections_to_be_written]
        full_meanings = "\n".join([f"{sections_to_write[i]}: {section_descriptions[i]}" for i in range(len(sections_to_write))])
        input = f"Sections to write: {sections_to_write_str}\nOverall song description: {overall_song_description}\nGenre: Songwriter Pop\nEra: 2010s\nSection Descriptions:\n{full_meanings}"

        if sections_written is not None:
          written_sections = "\n".join(sections_written)
          input += f"Sections provided:\n{written_sections}\n\nLyrics:"
        else:
            input += "\n\nLyrics:"

        prompt = self.alpaca_prompt.format(instruction, input, "")

        convo = [
            {
                "role": "user",
                "content": prompt,
            },
        ]
        response = self.oai_client.chat.completions.create(
            model="gpt-4o",
            messages=convo,
        )

        return response.choices[0].message.content

