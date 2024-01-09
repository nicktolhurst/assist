
# import system utils
import dotenv, os, time

# import engines & APIs
import openai, pygame, speech_recognition

# import async programming packages
import aiohttp, aiofiles, asyncio, threading

# import local modules / scripts
from log_helper import get_logger, log_chat_input, log_chat_output

log = get_logger();
dotenv.load_dotenv()

# Global variable for the client session
client_session = None

# Set your OpenAI API key
openai.api_key = os.environ.get('OPENAI_API_KEY')

async def get_client_session_async():
    global client_session
    if client_session is None:
        client_session = aiohttp.ClientSession()
    return client_session

def recognize_speech(timeout = None):
    # Initialize the recognizer
    r = speech_recognition.Recognizer()

    with speech_recognition.Microphone() as source:
        # Your existing speech recognition logic
        r.adjust_for_ambient_noise(source=source, duration = 1)
        audio = r.listen(source, timeout = timeout)
        try:
            text = r.recognize_google(audio)
            log_chat_input(text)
            return text
        except speech_recognition.UnknownValueError:
            log.debug("Picked up noise, but didn't recognize it as a human voice. Ignoring.")
            return None
        except speech_recognition.RequestError:
            log.error("Could not request results from Google Speech Recognition service")
            return None

async def listen_async(loop):
    # Run the blocking recognize_speech function in a separate thread
    return await loop.run_in_executor(None, recognize_speech)

async def chat_async(messages):
    # get global ClientSession
    session = await get_client_session_async()
    async with session.post(
        "https://api.openai.com/v1/chat/completions",
        json={
            "model": "gpt-4-vision-preview",
            "messages": messages,
            "max_tokens": 500,
            "n": 1,
            "temperature": 1.3
        },
        headers={"Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY')}"}
    ) as response:
        if response.status == 200:
            data = await response.json()
            message = data['choices'][0]['message']
            log_chat_output(message['content'])
            return message
        else:
            log.error(f"OpenAI API request failed with status {response.status}")
            return None

def play_audio(file_path):
    pygame.init()
    pygame.mixer.init()
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)
    pygame.mixer.music.unload()
    os.remove(file_path)

async def speak_async(text):
    # get global ClientSession
    session = await get_client_session_async()
    async with session.post(
            'https://api.openai.com/v1/audio/speech',
            headers={'Authorization': f'Bearer {os.environ.get("OPENAI_API_KEY")}'},
            json={
                "model": "tts-1",
                "input": text,
                "voice": "echo",
                "response_format": "mp3",
            }
        ) as response:
            if response.status == 200:
                speech_file_path = f'speech-{time.strftime("%Y%m%d-%H%M%S")}.mp3'

                # Download the speech file
                async with aiofiles.open(speech_file_path, 'wb') as f:
                    await f.write(await response.read())
                
                return speech_file_path
            else:
                log.error(f"STATUS: {response.status} - OpenAI API request failed with response {response}")
                return None
        
async def speak_and_play_async(text):
    speech_file = await speak_async(text)
    if speech_file:
        threading.Thread(target=play_audio, args=(speech_file,)).start()

def start_conversation_when(word_list, in_first, words_of):
    # Split the input string into words
    input_string = words_of
    words = input_string.lower().split()
    conversation_start_time = time.time()

    # Check if the string has at least one word
    if len(words) == 0:
        return False, conversation_start_time
    
    # Check if the 'n' word is in the list (if there is a n word..)
    for n in range(in_first - 1):
        if len(words) > n and words[n] in word_list:
            return True, conversation_start_time

    return False, conversation_start_time

def get_chat_context_preload():
    chat_context_preload = [
        {
            "role": "user", 
            "content": "You can call me Nick. \
                        I want to refer to you as the Atlas. \
                        Speak to me as if you were jarvis from iron man. \
                        Keep your answers short and on point."
        },
        {
            "role": "assistant", 
            "content": "Ok"
        }
    ]

    return chat_context_preload, len(chat_context_preload)

@log.catch
async def main_async():

    loop = asyncio.get_running_loop()

    chat_context, chat_context_preload_length = get_chat_context_preload()

    listening = True

    while listening:
        # listen and perform speech recognition
        question = await listen_async(loop)
        # if no discernible content was returned, continue with next loop iteration (back to top!)
        if question is None: continue
        # check if conversation starter prompt exists
        in_conversation, start_time = start_conversation_when(['atlas'], in_first=3, words_of=question)

        while in_conversation:

            if question:
                # add recognized text to the context store
                chat_context.append({"role": "user", "content": question}) # TODO: Create an external context store.

                if len(chat_context) > chat_context_preload_length: 
                    # send context to chat to get the latest response from the LLM.
                    response = await chat_async(chat_context)

                    if (response):
                        # add the response to the context
                        chat_context.append(response)
                        # play the context back to the user.
                        await speak_and_play_async(response['content'])
                        # reset the timer
                        start_time = time.time()

            if time.time() - start_time > 3:
                log.debug('Ending conversation after 3 seconds of awkward silence..')
                break
    
            # listen and perform speech recognition
            question = await listen_async(loop)
            # if no discernible content was returned, continue with next loop iteration (back to top!)
            if question is None: continue

    # outside of the main loop, close the session before exiting the program.
    session = await get_client_session_async()
    await session.close()

if __name__ == "__main__":
    asyncio.run(main_async())