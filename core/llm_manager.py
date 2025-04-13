import os
import asyncio
from dotenv import load_dotenv
from itertools import cycle

# Import necessary LLM client libraries
import google.generativeai as genai
from openai import AsyncOpenAI # Added
from groq import AsyncGroq     # Added
from anthropic import AsyncAnthropic # Added

# Use conditional imports for problematic libraries
try:
    from mistralai.client import MistralClient as MistralAICoreClient
    from mistralai.models.chat_completion import ChatMessage
    MISTRAL_AVAILABLE = True
    print("MistralAI library successfully imported")
except ImportError:
    print("MistralAI library not available. Will use stub implementation.")
    MISTRAL_AVAILABLE = False

try:
    from openrouter import AsyncOpenRouter 
    OPENROUTER_AVAILABLE = True
    print("OpenRouter library successfully imported")
except ImportError:
    print("OpenRouter library not available. Will use stub implementation.")
    OPENROUTER_AVAILABLE = False

try:
    import dashscope 
    from dashscope import Generation
    DASHSCOPE_AVAILABLE = True
    print("Dashscope library successfully imported")
except ImportError:
    print("Dashscope library not available. Will use stub implementation.")
    DASHSCOPE_AVAILABLE = False

# Placeholder for actual client initialization and generation logic
class BaseLLMClient:
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        print(f"Initializing client for {self.__class__.__name__} with model {model_name}")

    async def generate(self, prompt: str) -> str:
        # This should be implemented by subclasses to call the specific LLM API
        raise NotImplementedError("Subclasses must implement the generate method.")
        # Example simulation:
        # await asyncio.sleep(0.1) # Simulate API call latency
        # return f"Response from {self.__class__.__name__} ({self.model_name}) for prompt: {prompt[:30]}..."

# --- Concrete Client Implementations (Add one for each LLM) ---

class GeminiClient(BaseLLMClient):
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash", temperature: float = 0.7, top_k: int = 40):
        super().__init__(api_key, model_name)
        # Configure the genai library upon initialization
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            self.temperature = temperature
            self.top_k = top_k
            print(f"Gemini client configured for model {self.model_name}")
        except Exception as e:
            print(f"Error configuring Gemini client: {e}")
            self.model = None # Mark model as unavailable

    async def generate(self, prompt: str) -> str:
        if not self.model:
            return f"Error: Gemini model ({self.model_name}) not initialized."
        print(f"[LLMManager/GeminiClient] Generating content with {self.model_name}...")
        try:
            # Simulate latency
            await asyncio.sleep(0.5)
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=self.temperature,
                    top_k=self.top_k
                )
            )
            return response.text if hasattr(response, 'text') else str(response)
        except Exception as e:
            print(f"Error during Gemini generation ({self.model_name}): {e}")
            return f"Error generating with Gemini: {str(e)}"

class OpenAIClient(BaseLLMClient):
    def __init__(self, api_key: str, model_name: str = "gpt-3.5-turbo", temperature: float = 0.7):
        super().__init__(api_key, model_name)
        try:
            self.client = AsyncOpenAI(api_key=self.api_key)
            self.temperature = temperature
            print(f"OpenAI client configured for model {self.model_name}")
        except Exception as e:
            print(f"Error configuring OpenAI client: {e}")
            self.client = None

    async def generate(self, prompt: str) -> str:
        if not self.client:
            return f"Error: OpenAI client ({self.model_name}) not initialized."
        print(f"[LLMManager/OpenAIClient] Generating content with {self.model_name}...")
        try:
            # Use chat completions endpoint
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
            )
            # Extract the response content
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content or ""
            else:
                return "Error: No response content from OpenAI."
        except Exception as e:
            print(f"Error during OpenAI generation ({self.model_name}): {e}")
            return f"Error generating with OpenAI: {str(e)}"

class GroqClient(BaseLLMClient):
    def __init__(self, api_key: str, model_name: str = "llama3-8b-8192", temperature: float = 0.7):
        super().__init__(api_key, model_name)
        try:
            self.client = AsyncGroq(api_key=self.api_key)
            self.temperature = temperature
            print(f"Groq client configured for model {self.model_name}")
        except Exception as e:
            print(f"Error configuring Groq client: {e}")
            self.client = None

    async def generate(self, prompt: str) -> str:
        if not self.client:
            return f"Error: Groq client ({self.model_name}) not initialized."
        print(f"[LLMManager/GroqClient] Generating content with {self.model_name}...")
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
            )
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content or ""
            else:
                return "Error: No response content from Groq."
        except Exception as e:
            print(f"Error during Groq generation ({self.model_name}): {e}")
            return f"Error generating with Groq: {str(e)}"

class AnthropicClient(BaseLLMClient):
    def __init__(self, api_key: str, model_name: str = "claude-3-haiku-20240307", temperature: float = 0.7, max_tokens: int = 1024):
        super().__init__(api_key, model_name)
        try:
            self.client = AsyncAnthropic(api_key=self.api_key)
            self.temperature = temperature
            self.max_tokens = max_tokens
            print(f"Anthropic client configured for model {self.model_name}")
        except Exception as e:
            print(f"Error configuring Anthropic client: {e}")
            self.client = None

    async def generate(self, prompt: str) -> str:
        if not self.client:
            return f"Error: Anthropic client ({self.model_name}) not initialized."
        print(f"[LLMManager/AnthropicClient] Generating content with {self.model_name}...")
        try:
            # Use messages endpoint
            response = await self.client.messages.create(
                model=self.model_name,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            # Extract the response content (Anthropic returns content in a list)
            if response.content and isinstance(response.content, list) and hasattr(response.content[0], 'text'):
                return response.content[0].text or ""
            else:
                return "Error: No response content from Anthropic."
        except Exception as e:
            print(f"Error during Anthropic generation ({self.model_name}): {e}")
            return f"Error generating with Anthropic: {str(e)}"

class MistralClient(BaseLLMClient):
    def __init__(self, api_key: str, model_name: str = "mistral-large-latest", temperature: float = 0.7):
        super().__init__(api_key, model_name)
        self.temperature = temperature
        
        if not MISTRAL_AVAILABLE:
            print(f"Using STUB MistralClient (library not installed)")
            self.client = None
            return
            
        try:
            # Only try to initialize if library is available
            self.client = MistralAICoreClient(api_key=self.api_key)
            print(f"MistralAI client configured for model {self.model_name}")
        except Exception as e:
            print(f"Error configuring MistralAI client: {e}")
            self.client = None

    async def generate(self, prompt: str) -> str:
        if not MISTRAL_AVAILABLE:
            return f"Warning: MistralAI library not installed. Cannot use {self.model_name}."
            
        if not self.client:
            return f"Error: MistralAI client ({self.model_name}) not initialized."
        
        print(f"[LLMManager/MistralClient] Generating content with {self.model_name}...")
        try:
            # Wrap synchronous call in run_in_executor
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, # Use default executor
                self.client.chat,
                {
                    "model": self.model_name,
                    "messages": [ChatMessage(role="user", content=prompt)],
                    "temperature": self.temperature,
                }
            )
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content or ""
            else:
                return "Error: No response content from MistralAI."
        except Exception as e:
            print(f"Error during MistralAI generation ({self.model_name}): {e}")
            return f"Error generating with MistralAI: {str(e)}"

class OpenRouterClient(BaseLLMClient):
    # OpenRouter often uses OpenAI-compatible structure but routes to various models
    def __init__(self, api_key: str, model_name: str = "openrouter/auto", temperature: float = 0.7):
        super().__init__(api_key, model_name)
        self.temperature = temperature
        
        if not OPENROUTER_AVAILABLE:
            print(f"Using STUB OpenRouterClient (library not installed)")
            self.client = None
            return
            
        try:
            # Use OpenRouter's Async client
            self.client = AsyncOpenRouter(
                 api_key=self.api_key,
                 # base_url="https://openrouter.ai/api/v1" # Optional: if default changes
             )
            print(f"OpenRouter client configured for model {self.model_name}")
        except Exception as e:
            print(f"Error configuring OpenRouter client: {e}")
            self.client = None

    async def generate(self, prompt: str) -> str:
        if not OPENROUTER_AVAILABLE:
            return f"Warning: OpenRouter library not installed. Cannot use {self.model_name}."
            
        if not self.client:
            return f"Error: OpenRouter client ({self.model_name}) not initialized."
            
        print(f"[LLMManager/OpenRouterClient] Generating content with {self.model_name}...")
        try:
            # Use chat completions endpoint, similar to OpenAI
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
            )
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content or ""
            else:
                return "Error: No response content from OpenRouter."
        except Exception as e:
            print(f"Error during OpenRouter generation ({self.model_name}): {e}")
            return f"Error generating with OpenRouter: {str(e)}"

class QwenClient(BaseLLMClient):
    # Using Alibaba Dashscope SDK
    def __init__(self, api_key: str, model_name: str = "qwen-turbo", temperature: float = 0.7):
        super().__init__(api_key, model_name)
        self.temperature = temperature
        
        if not DASHSCOPE_AVAILABLE:
            print(f"Using STUB QwenClient (library not installed)")
            self.client_initialized = False
            return
            
        try:
            dashscope.api_key = self.api_key
            # No specific client object needed for basic generation with dashscope?
            # Check if the API key is valid (optional, might require a test call)
            print(f"Dashscope (Qwen) client configured for model {self.model_name}")
            self.client_initialized = True # Mark as initialized if api_key is set
        except Exception as e:
            print(f"Error configuring Dashscope/Qwen client: {e}")
            self.client_initialized = False

    async def generate(self, prompt: str) -> str:
        if not DASHSCOPE_AVAILABLE:
            return f"Warning: Dashscope library not installed. Cannot use {self.model_name}."
            
        if not self.client_initialized:
            return f"Error: Dashscope/Qwen client ({self.model_name}) not initialized."
            
        print(f"[LLMManager/QwenClient] Generating content with {self.model_name}...")
        try:
            # Use Generation.call method
            # Dashscope SDK might be synchronous, use run_in_executor
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                Generation.call,
                {
                     "model": self.model_name,
                     "prompt": prompt, # Dashscope might use 'prompt' directly for basic models
                     # "messages":[{"role": "user", "content": prompt}], # Or messages for chat models
                     "temperature": self.temperature
                }
            )

            # Check response structure based on Dashscope documentation
            if response.status_code == 200 and response.output and response.output.text:
                return response.output.text
            else:
                 error_msg = response.message if hasattr(response, 'message') else "Unknown error"
                 print(f"Dashscope API Error: Code {response.status_code}, Message: {error_msg}")
                 return f"Error: No valid response content from Dashscope/Qwen. Status: {response.status_code}"
        except Exception as e:
            print(f"Error during Dashscope/Qwen generation ({self.model_name}): {e}")
            return f"Error generating with Dashscope/Qwen: {str(e)}"

# --- LLM Manager ---

class LLMManager:
    def __init__(self):
        load_dotenv()
        self.clients = []
        self._client_cycle = None
        self._initialize_clients()
        if self.clients:
            self._client_cycle = cycle(self.clients)
            print(f"[LLMManager] Initialized with {len(self.clients)} clients.")
        else:
            print("[LLMManager] Warning: No LLM clients were successfully initialized.")

    def _initialize_clients(self):
        """Initializes clients for all configured LLMs based on environment variables."""
        print("[LLMManager] Initializing LLM clients...")

        # Gemini
        gemini_key = os.getenv("GEMINI_API_KEY")
        gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash") # Default model
        if gemini_key:
            try:
                client = GeminiClient(api_key=gemini_key, model_name=gemini_model_name)
                if client.model: # Check if initialization was successful
                    self.clients.append(client)
                else:
                    print(f"[LLMManager] Failed to initialize Gemini client for {gemini_model_name}.")
            except Exception as e:
                print(f"[LLMManager] Error initializing Gemini client: {e}")
        else:
            print("[LLMManager] GEMINI_API_KEY not found in .env. Skipping Gemini.")

        # OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        openai_model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo") # Default model
        if openai_key:
            try:
                client = OpenAIClient(api_key=openai_key, model_name=openai_model)
                if client.client: # Check if AsyncOpenAI client was initialized
                    self.clients.append(client)
                else:
                    print(f"[LLMManager] Failed to initialize OpenAI client for {openai_model}.")
            except Exception as e:
                print(f"[LLMManager] Error initializing OpenAI client: {e}")
        else:
            print("[LLMManager] OPENAI_API_KEY not found. Skipping OpenAI.")

        # Groq
        groq_key = os.getenv("GROQ_API_KEY")
        groq_model = os.getenv("GROQ_MODEL", "llama3-8b-8192") # Default model
        if groq_key:
            try:
                client = GroqClient(api_key=groq_key, model_name=groq_model)
                if client.client: # Check if AsyncGroq client was initialized
                    self.clients.append(client)
                else:
                    print(f"[LLMManager] Failed to initialize Groq client for {groq_model}.")
            except Exception as e:
                print(f"[LLMManager] Error initializing Groq client: {e}")
        else:
            print("[LLMManager] GROQ_API_KEY not found. Skipping Groq.")

        # Anthropic (Claude)
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307") # Default model
        if anthropic_key:
            try:
                client = AnthropicClient(api_key=anthropic_key, model_name=anthropic_model)
                if client.client: # Check if AsyncAnthropic client was initialized
                    self.clients.append(client)
                else:
                    print(f"[LLMManager] Failed to initialize Anthropic client for {anthropic_model}.")
            except Exception as e:
                print(f"[LLMManager] Error initializing Anthropic client: {e}")
        else:
             print("[LLMManager] ANTHROPIC_API_KEY not found. Skipping Anthropic.")

        # MistralAI
        mistral_key = os.getenv("MISTRAL_API_KEY")
        mistral_model = os.getenv("MISTRAL_MODEL", "mistral-large-latest") # Default model
        if mistral_key:
            try:
                client = MistralClient(api_key=mistral_key, model_name=mistral_model)
                # Check if lib available and client initialized
                if MISTRAL_AVAILABLE and client.client:
                    self.clients.append(client)
                    print(f"[LLMManager] MistralAI client added for {mistral_model}.")
                else:
                    print(f"[LLMManager] MistralAI client not added. Library available: {MISTRAL_AVAILABLE}")
            except Exception as e:
                print(f"[LLMManager] Error initializing MistralAI client: {e}")
        else:
            print("[LLMManager] MISTRAL_API_KEY not found. Skipping MistralAI.")

        # OpenRouter
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        openrouter_model = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
        if openrouter_key:
            try:
                client = OpenRouterClient(api_key=openrouter_key, model_name=openrouter_model)
                # Check if lib available and client initialized
                if OPENROUTER_AVAILABLE and client.client:
                    self.clients.append(client)
                    print(f"[LLMManager] OpenRouter client added for {openrouter_model}.")
                else:
                    print(f"[LLMManager] OpenRouter client not added. Library available: {OPENROUTER_AVAILABLE}")
            except Exception as e:
                print(f"[LLMManager] Error initializing OpenRouter client: {e}")
        else:
            print("[LLMManager] OPENROUTER_API_KEY not found. Skipping OpenRouter.")

        # Qwen (Dashscope)
        qwen_key = os.getenv("DASHSCOPE_API_KEY") 
        qwen_model = os.getenv("QWEN_MODEL", "qwen-turbo") # Default model
        if qwen_key:
            try:
                client = QwenClient(api_key=qwen_key, model_name=qwen_model)
                # Check if lib available and client initialized
                if DASHSCOPE_AVAILABLE and client.client_initialized:
                    self.clients.append(client)
                    print(f"[LLMManager] Qwen/Dashscope client added for {qwen_model}.")
                else:
                    print(f"[LLMManager] Qwen/Dashscope client not added. Library available: {DASHSCOPE_AVAILABLE}")
            except Exception as e:
                print(f"[LLMManager] Error initializing Qwen/Dashscope client: {e}")
        else:
            print("[LLMManager] DASHSCOPE_API_KEY not found. Skipping Qwen/Dashscope.")

    async def generate(self, prompt: str) -> str:
        """Selects the next client using round-robin and generates content."""
        if not self._client_cycle:
            return "Error: No LLM clients available."

        selected_client = next(self._client_cycle)
        client_name = selected_client.__class__.__name__
        model_name = selected_client.model_name
        print(f"[LLMManager] Routing to client: {client_name} (Model: {model_name})")

        try:
            response = await selected_client.generate(prompt)
            return response
        except Exception as e:
            print(f"[LLMManager] Error during generation with {client_name} ({model_name}): {e}")
            # Optionally: try the next client or just return the error
            return f"Error generating with {client_name}: {str(e)}"

# Example usage (for testing the manager directly)
async def test_manager():
    manager = LLMManager()
    if not manager.clients:
        print("No clients to test.")
        return

    prompts = ["Hello!", "Tell me a joke.", "What is the capital of France?"]
    for i, prompt in enumerate(prompts):
        print(f"--- Request {i+1} ---")
        response = await manager.generate(prompt)
        print(f"Prompt: {prompt}")
        print(f"Response: {response}")

if __name__ == "__main__":
    asyncio.run(test_manager()) 