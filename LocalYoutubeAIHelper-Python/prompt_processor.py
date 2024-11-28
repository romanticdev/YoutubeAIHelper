import os
import json
import re
import openai
import concurrent.futures
from utilities import setup_logging, load_file_content, load_variable_content, save_file_content, ensure_directory_exists
from config import CONFIG

logger = setup_logging()

class PromptProcessor:
    def __init__(self, config):
        """
        Initializes the PromptProcessor with configuration settings.

        Args:
            config (dict): General configuration settings.
        """
        self.config = config
        self.prompts_folder = config.get('prompts_folder', 'prompts')
        self.openai_api_key = config.get('openai_api_key')
        self.client = openai.OpenAI(api_key=self.openai_api_key)

    def process_prompts_on_transcripts(self, folders):
        """
        Processes prompts on transcriptions in the specified folders.

        Args:
            folders (list): List of folder paths containing transcriptions.
        """
        for folder in folders:
            if not os.path.exists(folder):
                logger.error(f"Folder not found: {folder}")
                continue

            logger.info(f"Processing prompts in folder: {folder}")

            # Load transcription files
            transcribed_files = self._load_transcription_files(folder)

            # Find all prompt files
            prompt_files = self._get_prompt_files()
            if not prompt_files:
                logger.error(f"No prompt files found in folder: {self.prompts_folder}")
                return

            generated_files = []
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(self._process_single_prompt, prompt_file, transcribed_files, folder)
                    for prompt_file in prompt_files
                ]
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        generated_files.append(result)

            # Substitute variables in generated files
            self._substitute_variables_in_files(folder, generated_files)

    def _load_transcription_files(self, folder):
        """
        Loads transcription files (SRT, TXT, and LLMSRT) from the specified folder.

        Args:
            folder (str): Path to the folder.

        Returns:
            dict: Dictionary containing paths to transcription files.
        """
        base_path = os.path.join(folder, 'transcript')
        return {
            'txt': f"{base_path}.txt" if os.path.exists(f"{base_path}.txt") else None,
            'srt': f"{base_path}.srt" if os.path.exists(f"{base_path}.srt") else None,
            'llmsrt': f"{base_path}.llmsrt" if os.path.exists(f"{base_path}.llmsrt") else None,
        }

    def _get_prompt_files(self):
        """
        Retrieves all prompt files from the prompts folder.

        Returns:
            list: List of prompt file paths.
        """
        if not os.path.exists(self.prompts_folder):
            return []
        return [
            os.path.join(self.prompts_folder, f)
            for f in os.listdir(self.prompts_folder)
            if f.endswith('.txt') or f.endswith('.srt')
        ]

    def _process_single_prompt(self, prompt_file, transcribed_files, folder):
        """
        Processes a single prompt on the transcriptions.

        Args:
            prompt_file (str): Path to the prompt file.
            transcribed_files (dict): Paths to transcription files.
            folder (str): Folder where generated files will be saved.
        """
        prompt_name = os.path.splitext(os.path.basename(prompt_file))[0]
        prompt_content = load_file_content(prompt_file)

        # Determine the appropriate transcription file to use
        if prompt_file.endswith('.srt'):
            transcription_file = transcribed_files.get('llmsrt')
        else:
            transcription_file = transcribed_files.get('txt')

        if not transcription_file:
            logger.error(f"Transcription file not found for prompt: {prompt_file}")
            return

        # Prepare messages for OpenAI API
        transcription_content = load_file_content(transcription_file)
        messages = [
            {"role": "system", "content": prompt_content},
            {"role": "user", "content": transcription_content},
        ]

        # Check for the presence of a corresponding JSON schema file
        schema_file = os.path.join(os.path.dirname(prompt_file), f"{prompt_name}.schema.json")
        if os.path.exists(schema_file):
            # Load the JSON schema
            schema = json.loads(load_file_content(schema_file))
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": f"{prompt_name}_response",
                    "schema": schema,
                    "strict": True
                }
            }
            output_extension = '.prompt.json'
        else:
            response_format = None
            output_extension = '.prompt.txt'

        # Generate and save response
        generated_file = self._generate_and_save_response(
            messages=messages,
            response_format=response_format,
            output_extension=output_extension,
            folder=folder,
            prompt_name=prompt_name
        )

        return generated_file

    def _generate_and_save_response(self, messages, response_format, output_extension, folder, prompt_name):
        """
        Generates a response using OpenAI's API and saves it to a file.

        Args:
            messages (list): List of messages for the API.
            response_format (dict): Format specification for the response.
            output_extension (str): File extension for the output file.
            folder (str): Folder to save the generated response.
            prompt_name (str): Name of the prompt.

        Returns:
            str: Path to the saved response file.
        """
        try:
            # Generate the response using the OpenAI API
            response = self.client.chat.completions.create(
                model=self.config['default_model'],
                messages=messages,
                temperature=float(self.config.get('temperature', 0.7)),
                max_tokens=int(self.config.get('max_tokens',4000)),
                top_p=float(self.config.get('top_p', 1.0)),
                response_format=response_format
            )

            assistant_content = response.choices[0].message.content

            # Ensure unique output filename
            output_filename = f"{prompt_name}{output_extension}"
            output_file = os.path.join(folder, output_filename)
            file_number = 1
            while os.path.exists(output_file):
                file_number += 1
                output_filename = f"{prompt_name}.{file_number}{output_extension}"
                output_file = os.path.join(folder, output_filename)

            # Save the assistant's response
            with open(output_file, 'w', encoding='utf-8') as f:
                if '.json' in output_extension:
                    output_data = json.loads(assistant_content)
                    json.dump(output_data, f, indent=4)
                else:
                    f.write(assistant_content)

            logger.info(f"Saved response to: {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"Error processing prompt '{prompt_name}': {e}")
            return None

    def _substitute_variables_in_files(self, folder, generated_files):
        """
        Substitutes placeholders in generated files with corresponding values.

        Args:
            folder (str): Folder containing the files.
            generated_files (list): List of generated file paths.
        """
        for file_path in generated_files:
            content = load_file_content(file_path)
            updated = False

            # Find and replace variables like {{variable}}
            for variable in re.findall(r'{{(.*?)}}', content):
                replacement = load_variable_content(variable,folder)
                if replacement:
                    content = content.replace(f"{{{{{variable}}}}}", replacement)
                    updated = True

            if updated:
                save_file_content(file_path, content)
                logger.info(f"Updated variables in: {file_path}")
