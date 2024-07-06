# def chat_to_journal_messages(chat_messages):
#     journal_messages = []
#     for m in chat_messages:
#         if m['role'] == 'system':
#             continue
#         elif m['role'] == 'assistant':
#             journal_messages.append({'role': 'user', 'content': m['content']})
#         else:
#             journal_messages.append({'role': 'assistant', 'content': m['content']})
#     return journal_messages

# def get_journal_response(journal_entry: Optional[str], chatbot_history: Optional[History], chatbot_messages: Optional [Messages], temperature: Optional[float] = 1.0):
#     journal_messages = chat_to_journal_messages(chatbot_messages)

#     prompt = journal_starting_message.replace("{full_journal_entry}", journal_entry)
    
#     journal_messages.insert(0, {'role': 'system', 'content': prompt})

#     # journal_messages = journal_messages + [{'role': 'user', 'content': artist_query}]

#     messages_filtered = journal_messages
#     gen = oai_client.chat.completions.create(
#         model="gpt-4o",
#         messages=messages_filtered,
#         stream=True,
#         temperature=temperature
#     )

#     current_response = ""
#     for chunk in gen:
#         if chunk.choices[0].delta.content is not None:
#             # print ("chunk", chunk.choices[0].delta.content)
#             current_response += chunk.choices[0].delta.content
#             chatbot_role = "assistant"
#             new_chatbot_messages = chatbot_messages + [{'role': chatbot_role, 'content': current_response}]
#             chatbot_history = messages_to_history(new_chatbot_messages)

#             yield current_response, chatbot_history, new_chatbot_messages

# journal_starting_message = """
# You are a 22-year-old who is about to graduate from college. You have been selected for a once-in-a-lifetime oppportunity to have a song written by one of the world's biggest music artists about a story from your journal. The artist has a set of questions to ask you, please answer as accurately as possible according to the journal entry. Use quotes and passages from the journal entry as much as you can. Keep your responses short in length, at most 3 sentences. No need to compliment the artist as they write, as it starts to push them towards more inauthentic writing. You're not a songwriter, so please don't give any lyrical suggestions. For any questions where the answer is not implied in the journal entry, make up a response that very naturally fits the story. The artist is very good at making you feel comfortable, understood, and ready to share your feelings and story. Here is the journal entry you will refer to, now respond with your answers to the artist's questions. \nJournal entry: {full_journal_entry}
# """