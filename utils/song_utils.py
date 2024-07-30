import os
from openai import OpenAI
from typing import Optional, Tuple, List, Dict
from dotenv import load_dotenv
from gradio import ChatMessage
import gradio as gr

# Load environment variables from .env file
load_dotenv()

client_key = os.getenv("OPEN_AI_KEY")
print(client_key)
oai_client = OpenAI(
    api_key=client_key,
)

History = List[Tuple[str, str]] # a type: pairs of (query, response), where query is user input and response is system output
Messages = List[Dict[str, str]] # a type: list of messages with role and content

def generate_song_seed(baseline_seed):
    """
    Generates a song seed based on a baseline seed description.

    Args:
        baseline_seed (str): The baseline seed description to generate the song concept from.

    Yields:
        str: The generated song concept in chunks.
    """
    song_details_prompt = (
        "Analyze this description of how someone is feeling and provide a suggestion of an interesting song concept to base a song off of. "
        "Here are three examples, now provide a song concept for this fourth:\n\n"
    )

    song_seed_prompt_path = 'prompts/prompt_song_seed.txt'
    with open(song_seed_prompt_path, 'r', encoding='utf-8') as file:
        content_2 = file.read()

    song_details_prompt += f"\n\n{content_2}{baseline_seed}\nSuggested Song Concept: "

    response_generator = oai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": song_details_prompt}],
        stream=True
    )

    current_response = ""
    for chunk in response_generator:
        delta_content = chunk.choices[0].delta.content
        if delta_content:
            current_response += delta_content
            yield current_response

def get_sections(overall_meaning: str, section_list: str) -> str:
    """
    Generates section meanings based on the overall meaning and section list.

    Args:
        overall_meaning (str): The overall meaning of the song.
        section_list (str): A newline-separated string of section names.

    Returns:
        str: The generated section meanings.
    """
    section_list = section_list.split("\n")
    prompt_path = 'prompts/prompt_section_writer.txt'
    
    with open(prompt_path, 'r', encoding='utf-8') as file:
        prompt_content = file.read()

    user_message = {
        "role": "user",
        "content": f"{prompt_content}\n\nOverall meaning: {overall_meaning}\nSection list: {', '.join(section_list)}\nSection meanings:"
    }

    response = oai_client.chat.completions.create(
        model="gpt-4o",
        messages=[user_message],
    )

    return response.choices[0].message.content

def messages_to_history(messages: Messages) -> Tuple[str, History]:
    """
    Converts a list of messages into a history of user-assistant interactions.

    Args:
        messages (Messages): A list of message dictionaries, where each dictionary contains
                                'role' (str) and 'content' (str) keys.

    Returns:
        Tuple[str, History]: A tuple containing a string (empty in this case) and a list of tuples,
                                where each tuple represents a user-assistant message pair.
    """
    assert messages[0]['role'] == 'system' and messages[1]['role'] == 'user'


    # Filter out 'tool' messages and those containing 'tool_calls'
    messages_for_parsing = [msg for msg in messages if msg['role'] != 'tool' and 'tool_calls' not in msg]

    # Remove " Use write_section" from user messages
    messages_for_parsing = [
        {'role': msg['role'], 'content': msg['content'].split(" Use write_section")[0]} if msg['role'] == 'user' else msg
        for msg in messages_for_parsing
    ]

    # Create history from user-assistant message pairs
    history = [
        ChatMessage(role = q['role'], content = q['content'])
        for q in messages_for_parsing[2:]
    ]

    return history

def get_starting_messages(song_lengths: str, song_title: str, song_blurb: str, song_genre: str, init_sections: str) -> Tuple[List[Dict[str, str]], History]:
    """
    Generates the initial messages for starting a songwriting session.

    Args:
        song_lengths (str): The lengths of the song sections.
        song_title (str): The title of the song.
        song_blurb (str): A brief description of the song.
        song_genre (str): The genre of the song.
        init_sections (str): The initial structure of the song sections.

    Returns:
        Tuple[List[Dict[str, str]], History]: A tuple containing the starting messages and the message history.
    """
    system_prompt = (
        "You are an expert at writing songs. You are with an everyday person, and you will write the lyrics of the song "
        "based on this person's life by asking questions about a story of theirs. Design your questions using ask_question "
        " to help you understand the user's story, so you can write a song about the user's experience that "
        "resonates with them. We have equipped you with a set of tools to help you write this story; please use them. You are "
        "very good at making the user feel comfortable, understood, and ready to share their feelings and story. Occasionally "
        "(every 2 messages or so) you will suggest some lyrics, one section at a time, and see what the user thinks of them. "
        "Do not suggest or ask for thoughts on more than one section at a time. Be concise and youthful."
    )

    user_prompt = (
        f"I have a story that could make this concept work well. The title is {song_title}, it's about {song_blurb} with a genre "
        f"{song_genre} and I think this should be the structure: {init_sections}\n{song_lengths}"
    )

    initial_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"The user has stated the following:\n {user_prompt}\n Introduce yourself and kick-off the songwriting process with a question."},
    ]

    first_msg_res = oai_client.chat.completions.create(
        model="gpt-4o",
        messages=initial_messages,
    )

    first_message = first_msg_res.choices[0].message.content
    starting_messages = initial_messages + [{'role': 'assistant', 'content': first_message}]

    history = [ChatMessage(role = x['role'], content = x['content']) for x in starting_messages]
    history = history[2:]

    return starting_messages, history

def update_song_details(instrumental_output: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Analyzes the given instrumental output to extract the genre, title, and blurb of a song.

    Args:
        instrumental_output (str): The assessment and suggestion of a song concept.

    Returns:
        Tuple[Optional[str], Optional[str], Optional[str]]: A tuple containing the genre, title, and blurb of the song.
    """
    song_details_prompt = (
        "Analyze this assessment and suggestion of a song concept to extract the genre, one sentence blurb of what the song is about. "
        "Based on this, also suggest a song title. Output exactly three lines, in the format of 'genre: [genre]', 'title: [title]', 'blurb: [blurb]'.\n\n"
        f"{instrumental_output}"
    )

    response = oai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": song_details_prompt}]
    )

    response_lines = response.choices[0].message.content.split('\n')
    genre = next((line.split(": ")[1] for line in response_lines if "genre: " in line.lower()), None)
    title = next((line.split(": ")[1] for line in response_lines if "title: " in line.lower()), None)
    blurb = next((line.split(": ")[1] for line in response_lines if "blurb: " in line.lower()), None)

    return genre, title, blurb