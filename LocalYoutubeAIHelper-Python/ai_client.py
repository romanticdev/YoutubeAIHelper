from openai import AzureOpenAI
from openai import OpenAI
from tenacity import retry, wait_random_exponential, stop_after_attempt
from utilities import setup_logging

logger = setup_logging()

class AIClient:
    def __init__(self, config, whisper_config):
        self.config = config
        self.whisper_config = whisper_config
        self.use_azure = config['use_azure_openai']
        if self.use_azure:
            self.endpoint = config['azure_openai_endpoint']
            self.api_key = config['azure_openai_api_key']
            self.api_version = config['azure_openai_api_version']
            self.deployment_name = config['azure_deployment_name']
            if not all([self.endpoint, self.api_key, self.api_version, self.deployment_name]):
                raise ValueError("Azure OpenAI configuration is incomplete.")
            self.client = AzureOpenAI(
                api_key=self.api_key,  
                api_version=self.api_version,
                azure_endpoint=self.endpoint
            )
            if whisper_config:
                self.whisperclient = AzureOpenAI(
                    api_key=self.api_key,
                    api_version=self.whisper_config.get('azure_openai_api_version',self.api_version),
                    azure_endpoint=self.endpoint
                )
            logger.info(f"Successfully initialized Azure clients from endpoint {self.endpoint}")
        else:
            self.api_key = config['openai_api_key']
            if not self.api_key:
                raise ValueError("OpenAI API key is missing.")
            self.client = OpenAI(api_key=self.api_key)
            logger.info(f"Successfully initialized OpenAI client")


    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    def create_chat_completion(self, messages, **kwargs):
        if self.use_azure:
            return self.client.chat.completions.create(
                model=kwargs.get('deployment_name', self.deployment_name),
                messages=messages,
                max_tokens=int(kwargs.get('max_tokens', self.config.get('max_tokens',4000))),
                temperature=float(kwargs.get('temperature', self.config.get('temperature', 0.7))),
                top_p=float(kwargs.get('top_p', self.config.get('top_p', 1.0))),
                response_format=kwargs.get('response_format',None)
            )

        else:
            return self.client.chat.completions.create(
                model=kwargs.get('model', self.config['default_model']),
                messages=messages,
                max_tokens=int(kwargs.get('max_tokens', self.config.get('max_tokens',4000))),
                temperature=float(kwargs.get('temperature', self.config.get('temperature', 0.7))),
                top_p=float(kwargs.get('top_p', self.config.get('top_p', 1.0))),
                response_format=kwargs.get('response_format',None)
            )
                
    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    def transcribe_audio(self, audio_file, **kwargs):
        if self.use_azure:
            return self.whisperclient.audio.transcriptions.create(
                file=audio_file,
                model=self.whisper_config['deployment_name'],
                **kwargs
                )
        else:
            return self.client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                **kwargs
                )
           