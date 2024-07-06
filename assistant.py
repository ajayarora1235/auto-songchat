import requests
import json
import time
import os
from typing import Optional, Tuple, List, Dict
from typing_extensions import override
from openai import AssistantEventHandler, OpenAI
from openai.types.beta.threads import Text, TextDelta

client = OpenAI(
    api_key=os.getenv("OPEN_AI_KEY"),
)

class EventHandler(AssistantEventHandler):
    def __init__(self):
        self.current_response = ""
        self.text_deltas = []

    @override
    def on_event(self, event):
        if event.event == 'thread.run.requires_action':
            run_id = event.data.id
            self.handle_requires_action(event.data, run_id)
        elif event.event == "thread.message.delta" and event.data.delta.content:
            self.on_text_delta(event.data.delta, event.data.snapshot)

    def handle_requires_action(self, data, run_id):
        tool_outputs = []
        for tool in data.required_action.submit_tool_outputs.tool_calls:
            if tool.function.name == "get_current_temperature":
                tool_outputs.append({"tool_call_id": tool.id, "output": "57"})
            elif tool.function.name == "get_rain_probability":
                tool_outputs.append({"tool_call_id": tool.id, "output": "0.06"})
        self.submit_tool_outputs(tool_outputs, run_id)

    def submit_tool_outputs(self, tool_outputs, run_id):
        with client.beta.threads.runs.submit_tool_outputs_stream(
            thread_id=self.current_run.thread_id,
            run_id=self.current_run.id,
            tool_outputs=tool_outputs,
            event_handler=EventHandler(),
        ) as stream:
            for text in stream.text_deltas:
                print(text, end="", flush=True)
            print()

    @override
    def on_text_delta(self, delta: TextDelta, snapshot: Text):
        if delta.value:
            self.current_response += delta.value
            self.text_deltas.append(delta.value)
            print(delta.value, end="", flush=True)

