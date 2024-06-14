# Welcome to pixify-discbot

## Introduction
Enhance your Discord server with discbot.py, a versatile chatbot that integrates local and remote AI models for engaging conversations. Whether you're using OpenAI, Mistral, or other supported APIs, discbot.py offers seamless interaction with advanced language models directly from your server. Or run local open models with any local api like GPT4All or LM Studio with http://localhost:5000/v1

<p align="center">
  <img src="https://github.com/PixifyAI/pixify-discbot/blob/main/discbot.png?raw=true"">
</p>

## Key Features
### Interactive Chat System
Initiate and continue conversations by mentioning @discbot, allowing for threaded replies and seamless interaction across your server.

Key functionalities include:
- Continuation of ongoing conversations
- Rewinding conversations by replying to previous messages
- Direct inquiries by mentioning @discbot in any server message

### Versatile Model Support
Choose from a variety of AI models:
- Remote models via OpenAI API, Mistral API, and more
- Local models like ollama, oobabooga, Jan, LM Studio, and others compatible with OpenAI APIs

### Additional Capabilities
- Supports image attachments when using a vision model (like gpt-4o, claude-3, llava, etc.)
- Supports text file attachments (.txt, .py, .c, etc.)
- Customizable system prompt (he is set with a little attitude default)
- DM for private access (no @ required)
- User identity aware (OpenAI API only)
- Streamed responses (turns green when complete, automatically splits into separate messages when too long)
- Displays helpful user warnings when appropriate (like "Only using last 20 messages" when the customizable message limit is exceeded)
- Caches message data in a size-managed (no memory leaks) and mutex-protected (no race conditions) global dictionary to maximize efficiency and minimize Discord API calls
- bot messages chat on 30 min loop with list of responses for help and info of how to msg the bot
- error handling
- Fully asynchronous
- 1 Python file, ~300 lines of code

## Installation Instructions
To get started, follow these steps:

1. Install Python and clone this repository:

`git clone https://github.com/PixifyAI/pixify-discbot`



2. Install Python dependencies:

`pip install -U -r requirements.txt`



3. Configure environment variables:

- Create a copy of "env.example" save it as ".env" and set up the following variables:


| Variable              | Instructions |
| --------------------- | ------------ |
| **DISCORD_BOT_TOKEN** | Create a new Discord bot at(https://discord.com/developers/applications) and generate a token under the "Bot" tab. Also enable "MESSAGE CONTENT INTENT". |
| **DISCORD_CLIENT_ID** | Found under the "OAuth2" tab of the Discord bot you just made. |
| **DISCORD_STATUS_MESSAGE** | Set a custom message that displays on the bot's Discord profile. **Max 128 characters.** |
| **LLM** | For [LiteLLM supported providers](https://docs.litellm.ai/docs/providers) ([OpenAI API](https://docs.litellm.ai/docs/providers/openai), [Mistral API](https://docs.litellm.ai/docs/providers/mistral), [ollama](https://docs.litellm.ai/docs/providers/ollama), etc.), follow the LiteLLM instructions for its model name formatting.<br /><br />For local models ([oobabooga](https://github.com/oobabooga/text-generation-webui), [Jan](https://jan.ai), [LM Studio](https://lmstudio.ai), etc.), set to `local/openai/model` (or `local/openai/vision-model` if using a vision model). Some setups will instead require `local/openai/<MODEL_NAME>` where <MODEL_NAME> is the exact name of the model you're using. |
| **LLM_SETTINGS** | Extra API parameters for your LLM, separated by commas. **Supports string, integer and float values.**<br />(Default: `max_tokens=1024, temperature=1.0`) |
| **LLM_SYSTEM_PROMPT** | Write anything you want to customize the bot's behavior! |
| **LOCAL_SERVER_URL** | The URL of your local API server. **Only applicable when "LLM" starts with `local/`.**<br />(Default: `http://localhost:5000/v1`) |
| **ALLOWED_CHANNEL_IDS** | Discord channel IDs where the bot can send messages, separated by commas. **Leave blank to allow all channels.** |
| **ALLOWED_ROLE_IDS** | Discord role IDs that can use the bot, separated by commas. **Leave blank to allow everyone. Specifying at least one role also disables DMs.** |
| **MAX_TEXT** | The maximum amount of text allowed in a single message, including text from file attachments.<br />(Default: `100,000`) |
| **MAX_IMAGES** | The maximum number of image attachments allowed in a single message. **Only applicable when using a vision model.**<br />(Default: `5`) |
| **MAX_MESSAGES** | The maximum number of messages allowed in a reply chain.<br />(Default: `20`) |
| **OPENAI_API_KEY** | **Only required if you choose a model from OpenAI API.** Generate an OpenAI API key at [platform.openai.com/account/api-keys](https://platform.openai.com/account/api-keys). You must also add a payment method to your OpenAI account at [platform.openai.com/account/billing/payment-methods](https://platform.openai.com/account/billing/payment-methods).|
| **MISTRAL_API_KEY** | **Only required if you choose a model from Mistral API.** Generate a Mistral API key at [console.mistral.ai/api-keys](https://console.mistral.ai/api-keys). You must also add a payment method to your Mistral account at [console.mistral.ai/billing](https://console.mistral.ai/billing).|

> **OPENAI_API_KEY** and **MISTRAL_API_KEY** are provided as examples. Add more as needed for other [LiteLLM supported providers](https://docs.litellm.ai/docs/providers).


4. Start the bot:
`python discbot.py`



5. The invite URL will be printed in the console for adding the bot to your server.



## Contributions
Contributions and pull requests are welcome to enhance discbot.py and its capabilities.

Thank you for using discbot.py to enrich your Discord experience!