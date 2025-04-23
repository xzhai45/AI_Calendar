from openai import OpenAI
from datetime import datetime
from dateutil import tz
from pydantic import BaseModel
from pypdf import PdfReader


# Class that describes the variables of a calender event
class Event(BaseModel):
    title: str
    start: str  # RFC3339 frmat
    end: str
    location: str
    description: str

class EventTime(BaseModel):
    start: str  # RFC3339 frmat
    end: str

class EventLocation(BaseModel):
    start: str  # RFC3339 frmat
    end: str
    location: str

class EventDescription(BaseModel):
    start: str  # RFC3339 frmat
    end: str
    location: str
    description: str
    


# Root object schema
class EventWrapper(BaseModel):
    events: list[Event]

class EventTimeWrapper(BaseModel):
    events: list[EventTime]

class EventLocationWrapper(BaseModel):
    events: list[EventLocation]

class EventDescriptionWrapper(BaseModel):
    events: list[EventDescription]



# Class to call the ChatGPT API
class APICaller:
    def __init__(self):
        f = open("hehe.txt", "r")
        api_key = f.read()
        self.__client = OpenAI(api_key=api_key)

    
    # Function to extract events
    def get_events(self, instruction: str, text: str, response_format, mini_model: bool = True):
        if mini_model:
            model = "gpt-4o-mini-2024-07-18"
        else:
            model = "gpt-4o-2024-08-06"

        messages = [
            {
                "role": "system",
                "content": instruction
            },
            {   
                "role": "user",
                "content": text
            }
        ]

        completion = self.__client.beta.chat.completions.parse(
            model = model,
            messages = messages,
            temperature = 0,
            response_format = response_format
        )

        return completion.choices[0].message.parsed
    
    

class ExtractInfo:
    @staticmethod
    def get_time(text: str, api_caller: APICaller) -> list[EventTime]:
        now = datetime.now(tz=tz.gettz("America/New_York")).isoformat()
        weekday = datetime.now(tz=tz.gettz("America/New_York")).strftime("%A")

        instruction = (
            f"You extract calendar events from natural language. Today is {now}, {weekday}. "
            "Return structured JSON as: {\"events\": [ ... ]}. "
            "Return all times in yyyy-mm-ddThh:mm:ss format."
            "If nothing can be parsed, return an empty list inside: {\"events\": []}."
        )

        result = api_caller.get_events(instruction, text, EventTimeWrapper, False)

        return result.events

    @staticmethod
    def get_location(text: str, event_str: str, api_caller: APICaller) -> EventLocation:
        now = datetime.now(tz=tz.gettz("America/New_York")).isoformat()
        weekday = datetime.now(tz=tz.gettz("America/New_York")).strftime("%A")

        instruction = (
            f"Add location information to the following event:\n{event_str} \nToday is {now}, {weekday}. "
            "Return structured JSON as: {\"start\": ... , \"end\": ... , \"location\": ... }. "
            "Return all times in yyyy-mm-ddThh:mm:ss format."
            "If location information cannot be found, return an empty string for the \"location\" field."
        )

        result = api_caller.get_events(instruction, text, EventLocation)

        return result

    @staticmethod
    def get_description(text: str, event_str: str, api_caller: APICaller) -> EventDescription:
        now = datetime.now(tz=tz.gettz("America/New_York")).isoformat()
        weekday = datetime.now(tz=tz.gettz("America/New_York")).strftime("%A")

        instruction = (
            f"Add description information to the following event:\n{event_str} \nToday is {now}, {weekday}. "
            "Return structured JSON as: {\"start\": ... , \"end\": ... , \"location\": ... , \"description\": ... }. "
            "Return all times in yyyy-mm-ddThh:mm:ss format."
            "If description information cannot be found, return an empty string for the \"description\" field."
        )

        result = api_caller.get_events(instruction, text, EventDescription)

        return result

    @staticmethod
    def get_title(text: str, event_str: str, api_caller: APICaller) -> Event:
        now = datetime.now(tz=tz.gettz("America/New_York")).isoformat()
        weekday = datetime.now(tz=tz.gettz("America/New_York")).strftime("%A")

        instruction = (
            f"Add title information to the following event:\n{event_str} \nToday is {now}, {weekday}. "
            "Return structured JSON as: {\"title\": ... , \"start\": ... , \"end\": ... , \"location\": ... , \"description\": ... }. "
            "Return all times in yyyy-mm-ddThh:mm:ss format."
            "If title information cannot be found, create a title based on start time, end time, location and description."
        )

        result = api_caller.get_events(instruction, text, Event)

        return result
    
    @staticmethod
    def filter_event(user_instruction: str, event_str: str, api_caller: APICaller) -> list[Event]:
        instruction = (
            f"Filter events according to the following instruction: {user_instruction} "
            "Return structured JSON as: {\"events\": [ ... ]}. "
        )

        result = api_caller.get_events(instruction, event_str, EventWrapper, False)

        return result.events
    
    @staticmethod
    def remove_duplicate_event(event_str: str, api_caller: APICaller) -> list[Event]:
        instruction = (
            f"Remove duplicated events."
            "Return structured JSON as: {\"events\": [ ... ]}. "
        )

        result = api_caller.get_events(instruction, event_str, EventWrapper, False)

        return result.events
    
    


# Class to extract an event given a text field or a PDF
class EventExtraction:
    def __init__(self):
        self.__api_caller = APICaller()
        self.chunk_length = 500

    # for testing purposes
    def extract_from_pdf(self, instruction: str, file_name: str) -> list[Event]:
        reader = PdfReader(file_name)
        main_text = ""

        for page in reader.pages:
            page_text = page.extract_text()
            main_text += page_text + " "

        return self.extract(instruction, main_text)

    # TODO: If start time == end time, increment end time by 1s
    def extract(self, instruction: str, text: str) -> list[Event]:
        chunk_list = self.split_text_into_chunks(text, self.chunk_length)

        event_time_list = []
        for chunk in chunk_list:
            event_time_list.append(ExtractInfo.get_time(chunk, self.__api_caller))

        print(event_time_list)

        for i in range(len(event_time_list)):
            for j in range(len(event_time_list[i])):
                text = chunk_list[i]
                event_str = event_time_list[i][j].model_dump_json(indent=2)
                new_event = ExtractInfo.get_location(text, event_str, self.__api_caller)
                event_time_list[i][j] = new_event

        for i in range(len(event_time_list)):
            for j in range(len(event_time_list[i])):
                text = chunk_list[i]
                event_str = event_time_list[i][j].model_dump_json(indent=2)
                new_event = ExtractInfo.get_description(text, event_str, self.__api_caller)
                event_time_list[i][j] = new_event

        for i in range(len(event_time_list)):
            for j in range(len(event_time_list[i])):
                text = chunk_list[i]
                event_str = event_time_list[i][j].model_dump_json(indent=2)
                new_event = ExtractInfo.get_title(text, event_str, self.__api_caller)
                event_time_list[i][j] = new_event

        event_list = [event for row in event_time_list for event in row]
        #print(event_list)

        if instruction != None and len(instruction) != 0:
            event_str = ""
            for event in event_list:
                event_str += event.model_dump_json(indent=2)
            #print(event_str)

            event_list = ExtractInfo.filter_event(instruction, event_str, self.__api_caller)

        event_str = ""
        for event in event_list:
            event_str += event.model_dump_json(indent=2)
        #print(event_str)

        event_list = ExtractInfo.remove_duplicate_event(event_str, self.__api_caller)

        for i in range(len(event_list)):
            event_list[i] = vars(event_list[i])
        
        return event_list


    def split_text_into_chunks(self, text: str, length: int) -> list[str]:
        small_chunks = list(text[i: length + i] for i in range(0, len(text), length))

        if len(small_chunks) == 0:
            big_chunks = list()
        elif len(small_chunks) == 1:
            big_chunks = small_chunks
        else:
            big_chunks = list(small_chunks[i] + small_chunks[i+1] for i in range(len(small_chunks) - 1))
        
        return big_chunks
    

    def print_events(self, events: list[Event]) -> None:
        for event in events:
            print(event.model_dump_json(indent=2))



if __name__ == "__main__":
    event_extraction = EventExtraction()

    ########## Case 1: Text input only
    # text = "I have a meeting on 22 and 24 April at 2pm for 1 hour at Starbucks about the CS 2340 project."
    # event_list = event_extraction.extract(None, text)
    
    ########## Case 2: PDF input
    # event_list = event_extraction.extract_from_pdf(None, "test_case_main.pdf")
    # event_list = event_extraction.extract_from_pdf(None, "test_case_main_2.pdf")

    ########## Case 3: PDF input with addtional text instructions
    # event_list = event_extraction.extract_from_pdf("Get me event(s) on graph", "test_case_main.pdf")
    event_list = event_extraction.extract_from_pdf("Get me event(s) on dynamic programming", "test_case_main.pdf")

    print(event_list)
