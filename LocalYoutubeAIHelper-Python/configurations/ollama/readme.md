# Using Ollama for Local LLMs

This folder contains information and configurations to run **local, free models** via [**Ollama**](https://ollama.com). By integrating Ollama, you can have a local Large Language Model running on your machine, which the `LocalYoutubeAIHelper-Python` app can connect to using an OpenAI-compatible interface.

## 1. Prerequisites

1. **Ollama Installation**  
   - [Official Installation Instructions](htts://ollama.com)  
   - After installing, confirm Ollama is accessible:  
     ```bash
     ollama run llama2
     ```
   - (Replace `llama2` with any model you have already pulled, or skip if you haven’t downloaded a model yet.)

2. **Your Desired Model**  
   - Ollama can pull various Llama2 or other open-licensed models. Example:
     ```bash
     ollama pull llama2
     ```
     or
     ```bash
     ollama pull llama2-7b
     ```
   - See [Ollama’s list of models](https://ollama.com/search) for more options.

## 2. Setting Up a Custom Context Size

Ollama has a simple mechanism to **extend or configure** a model’s context window (or other parameters) by creating a custom “model file.”

### 2.1. Example Model File

Suppose you want to **increase the context size** for the `phi4` model. Create a `.model` file (e.g., `phi42.model`) with the following contents:

```txt
FROM phi4
PARAMETER num_ctx 8192
```

- `FROM phi4` means “base this new model on `phi4` that’s already pulled by Ollama.”
- `PARAMETER num_ctx 8192` sets the maximum context size to 8192 tokens. Adjust as you prefer, but ensure your system can handle the increased memory usage.

Then create this new model in Ollama:

```bash
ollama create phi42 -f phi42.model
```

Ollama will save it locally under the name `phi42`.  
Now you can **run** it:
```bash
ollama run phi42
```

## 3. Using Your Custom Ollama Model with `LocalYoutubeAIHelper-Python`

### 3.1. Configuring `openai_api_key` and `openai_base_url`

In your project’s `.env` or `local.env`, make sure you **do not** set `USE_AZURE_OPENAI=true`. Instead, you only define your `OPENAI_API_KEY` with **any placeholder** (Ollama doesn’t require a real API key, but your environment might check if it’s non-empty).

Additionally, you will need to set the `openai_base_url` to Ollama’s endpoint. By default, Ollama runs on `http://localhost:11411`.

Example snippet in `local.env`:
```env
# Local usage for Ollama
USE_AZURE_OPENAI=false
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11411/v1
DEFAULT_MODEL=phi42
```

Alternatively, you can set the model name and base URL in configuration folder directly:

F.e. `configurations\ollama\llm_config.txt`:

```config
default_model=llama32-2
openai_api_key=ollama
openai_base_url=http://localhost:11434/v1
max_tokens=36000
```

- `default_model=llama32-2` tells the code to send requests to your custom model named “llama32-2”

### 3.2. Verifying the Ollama Connection

1. **Start Ollama** (if not already running in the background).
2. Run any command in your `LocalYoutubeAIHelper-Python` (for example, `python main.py ...`) that calls `OpenAI(api_key, base_url=...)`.
3. The request should pass through to Ollama. Monitor your Ollama logs/terminal to see if it’s processing prompts.


## 4. Common Issues

- **“Could not connect to base URL”**  
  Make sure Ollama is running on `localhost:11411`. If you changed Ollama’s default port, adjust `OPENAI_BASE_URL`.
- **Model not found**  
  Pull or create your model first (`ollama pull <model>` or `ollama create <alias> -f <model.file>`).
- **Out of memory**  
  Larger context sizes or bigger model weights need more RAM/GPU memory. Try reducing `num_ctx` or using a smaller model.

## 5. More Resources

- [Ollama GitHub Repository](https://github.com/ollama/ollama)  
- [USing Ollama with OpenAI-Compatible Endpoint](https://ollama.com/blog/openai-compatibility)  

## 6. Context Window Sizes

Note the biggest support context window size for some open source models available on ollama.com:

| Model Name | Context Window Size |
|------------|---------------------|
| PHI4       | 16,384 tokens  (16K)|
| LLaMA3.2   | 128K                |

