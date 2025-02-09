from openai import AzureOpenAI
from openai import OpenAI, RateLimitError
import threading
from tenacity import (
    retry,
    wait_random_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)

from pydub import AudioSegment
from pydub.playback import play
import warnings
from io import BytesIO
import base64
import simpleaudio as sa

from utilities import setup_logging

logger = setup_logging()


class AIClient:
    def __init__(self, config, whisper_config):
        self.config = config
        self.whisper_config = whisper_config
        self.use_azure = config["use_azure_openai"]
        if self.use_azure:
            self.endpoint = config["azure_openai_endpoint"]
            self.api_key = config["azure_openai_api_key"]
            self.api_version = config["azure_openai_api_version"]
            self.deployment_name = config["azure_deployment_name"]
            if not all(
                [self.endpoint, self.api_key, self.api_version, self.deployment_name]
            ):
                raise ValueError("Azure OpenAI configuration is incomplete.")
            self.client = AzureOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                azure_endpoint=self.endpoint,
            )
            if whisper_config:
                self.whisperclient = AzureOpenAI(
                    api_key=self.api_key,
                    api_version=self.whisper_config.get(
                        "azure_openai_api_version", self.api_version
                    ),
                    azure_endpoint=self.endpoint,
                )
            logger.info(
                f"Successfully initialized Azure clients from endpoint {self.endpoint}"
            )
        else:
            self.api_key = config["openai_api_key"]
            if not self.api_key:
                raise ValueError("OpenAI API key is missing.")

            self.base_url = config.get("openai_base_url", None)
            if self.base_url:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            else:
                self.client = OpenAI(api_key=self.api_key)
            logger.info(
                f"Successfully initialized OpenAI client. Model will be used: {self.config['default_model']}"
            )

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
        retry=retry_if_exception_type(RateLimitError),
    )
    def create_chat_completion(self, messages, **kwargs):
        if self.use_azure:
            parameters = {
                "model": kwargs.get("deployment_name", self.deployment_name),
                "messages": messages,
                "max_tokens": int(
                    kwargs.get("max_tokens", self.config.get("max_tokens", 4000))
                ),
                "temperature": float(
                    kwargs.get("temperature", self.config.get("temperature", 0.7))
                ),
                "top_p": float(kwargs.get("top_p", self.config.get("top_p", 1.0))),
                "response_format": kwargs.get("response_format", None),
            }
            if kwargs.get("function_call", None):
                parameters["function_call"] = kwargs["function_call"]

            if kwargs.get("functions", None):
                parameters["functions"] = kwargs["functions"]

            return self.client.chat.completions.create(**parameters)

        else:

            parameters = {
                "model": kwargs.get("model", self.config["default_model"]),
                "messages": messages,
                "temperature": float(
                    kwargs.get("temperature", self.config.get("temperature", 0.7))
                ),
                "top_p": float(kwargs.get("top_p", self.config.get("top_p", 1.0))),
            }
            
            if kwargs.get("response_format", None):
                parameters["response_format"] = kwargs["response_format"]

            if kwargs.get("function_call", None):
                parameters["function_call"] = kwargs["function_call"]

            if kwargs.get("functions", None):
                parameters["functions"] = kwargs["functions"]

            if "max_completion_tokens" in self.config:
                parameters["max_completion_tokens"] = int(
                    self.config["max_completion_tokens"]
                )
            else:
                parameters["max_tokens"] = int(
                    kwargs.get("max_tokens", self.config.get("max_tokens", 4000))
                )

            return self.client.chat.completions.create(**parameters)

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
        retry=retry_if_exception_type(RateLimitError),
    )
    def transcribe_audio(self, audio_file, **kwargs):
        if self.use_azure:
            response = self.whisperclient.audio.transcriptions.create(
                file=audio_file, model=self.whisper_config["deployment_name"], **kwargs
            )
        else:
            response = self.client.audio.transcriptions.create(
                file=audio_file, model="whisper-1", **kwargs
            )

        return response

    @retry(
        wait=wait_random_exponential(min=1, max=20),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(RateLimitError),
    )
    def censor_text(self, text, output_beep=False):
        # Call OpenAI's Moderation API
        response = self.client.moderations.create(
            input=text, model="text-moderation-latest"
        )

        # Categories object from the API response
        categories = response.results[0].categories

        # List of categories considered as profane
        profane_categories = [
            "hate",
            "hate/threatening",
            "self-harm",
            "sexual",
            "sexual/minors",
            "violence",
            "violence/graphic",
            "harassment",
            "harassment/threatening",
            "self-harm/intent",
            "self-harm/instructions",
            "self-harm/graphic",
            "sexual/explicit",
            "sexual/erotica",
            "violence/intent",
            "violence/instructions",
        ]

        # Check if any profane category is flagged
        flagged_categories = [
            category
            for category in profane_categories
            if getattr(categories, category, False)
        ]
        if len(flagged_categories) > 0:
            # Split text into wordss
            words = text.split()
            censored_words = []
            logger.info(f"Text moderation results = [ {", ".join(flagged_categories)}]")
            if output_beep:
                return "Beep"
            else:
                return ""
        else:
            # If no profane content is detected, return the original text
            return text

    def text_to_speech(self, text, voice="echo"):
        response = self.client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="mp3",
        )

        audio_content = response.content
        audio_stream = BytesIO(audio_content)
        audio = AudioSegment.from_file(audio_stream, format="mp3")

        # Convert to numpy array format for sounddevice
        import numpy as np
        import sounddevice as sd

        samples = np.array(audio.get_array_of_samples())
        if audio.channels > 1:
            samples = samples.reshape((-1, audio.channels))

        def play_audio():
            try:
                sd.play(samples, audio.frame_rate)
                sd.wait()
            except Exception as e:
                logger.error(f"Audio playback failed: {e}")

        thread = threading.Thread(target=play_audio)
        thread.start()
