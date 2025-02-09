# Using LM Studio for Local LLMs with Deepseek‑r1‑distill‑qwen‑7b

This folder contains information and configurations to run your Local YouTube AI Helper using a locally hosted language model via [LM Studio](https://lmstudio.ai). In this configuration, you will use the **deepseek‑r1‑distill‑qwen‑7b** model served by LM Studio instead of relying on cloud services.

## 1. Prerequisites

1. **Install LM Studio:**
   - Visit the [LM Studio website](https://lmstudio.ai) for installation instructions.
   - Follow the installation steps to set up LM Studio on your local machine.
   - Ensure that LM Studio is running—for example, by executing its executable and making sure that server is running [help](https://lmstudio.ai/docs/api)

2. **Download and Configure the Model:**
   - Verify that the **deepseek‑r1‑distill‑qwen‑7b** model is available in your LM Studio installation.
   - Follow LM Studio’s documentation to download and load the model files. You may need to add a configuration for this model within LM Studio.
   - Confirm that LM Studio is serving the model at a local endpoint. (For these instructions, we assume the endpoint is `http://localhost:1234/v1`; adjust if your setup differs.)

## 2. Configuration

1. **Environment Settings:**
   - In your project’s environment file (e.g. `local.env`), add or update the following entries so that requests are directed to your LM Studio instance:
     ```env
     USE_AZURE_OPENAI=false
     OPENAI_API_KEY=lm_studio
     OPENAI_BASE_URL=http://localhost:1234/v1
     DEFAULT_MODEL=deepseek-r1-distill-qwen-7b
     ```
   - (Adjust the `OPENAI_BASE_URL` if your LM Studio instance is running on a different port or address.)

2. **LLM Configuration File:**
   - Update the file `configurations/deepseek/llm_config.txt` with the following settings:
     ```config
     default_model=deepseek-r1-distill-qwen-7b
     openai_api_key=lm_studio
     openai_base_url=http://localhost:1234/v1
     max_tokens=16000
     temperature=0.7 
     ```
   - These settings ensure that all API requests from the Local YouTube AI Helper are sent to your LM Studio instance where the deepseek model will process them.

## 3. Running the System

- **Start LM Studio:**  
  Launch LM Studio and verify that it is running and serving the **deepseek‑r1‑distill‑qwen-7b** model at the endpoint specified in your configuration.

- **Run Your Application:**  
  Start the Local YouTube AI Helper as you normally would (for example, using `python main.py ...`). The helper will load its settings from `llm_config.txt` and forward requests to LM Studio, which will use the deepseek model for processing.

## 4. Troubleshooting & Tips

- **Connection Issues:**  
  If you encounter connection errors, ensure that LM Studio is running and that the `OPENAI_BASE_URL` in both your `local.env` and `llm_config.txt` files correctly reflects the address and port of your LM Studio instance.

- **Model Loading:**  
  Verify that the **deepseek‑r1‑distill‑qwen‑7b** model has been properly downloaded and loaded by LM Studio. Check the LM Studio logs for any errors during model initialization.

- **Performance Considerations:**  
  Ensure your hardware meets the requirements for running the deepseek model. You may need to adjust model parameters or allocate additional resources if performance issues arise.

- **Further Assistance:**  
  Refer to the [LM Studio documentation](https://lmstudio.ai/docs) for additional guidance on configuring endpoints, managing models, and troubleshooting common issues.

## 5. Summary

By following these steps—installing LM Studio, updating your environment and LM configuration files, and launching the Local YouTube AI Helper—you will be able to process requests locally using the **deepseek‑r1‑distill‑qwen‑7b** model without relying on external cloud services.
