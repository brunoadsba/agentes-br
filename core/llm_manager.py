import os
import asyncio
from dotenv import load_dotenv
from itertools import cycle

# Importa bibliotecas de cliente LLM necessárias e funcionais
import google.generativeai as genai
from openai import AsyncOpenAI # Usado para OpenRouter
from groq import AsyncGroq
# from anthropic import AsyncAnthropic # Mantido comentado, cliente removido

# Removidas importações condicionais para bibliotecas não funcionais/não instaladas

# Classe base para clientes LLM
class BaseLLMClient:
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        # Mensagem em português
        print(f"Inicializando cliente para {self.__class__.__name__} com modelo {model_name}")

    async def generate(self, prompt: str) -> str:
        # Deve ser implementado pelas subclasses para chamar a API LLM específica
        raise NotImplementedError("Subclasses devem implementar o método generate.")

# --- Implementações Concretas de Clientes (Funcionais) ---

class GeminiClient(BaseLLMClient):
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash", temperature: float = 0.7, top_k: int = 40):
        super().__init__(api_key, model_name)
        # Configura a biblioteca genai na inicialização
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            self.temperature = temperature
            self.top_k = top_k
            # Mensagem em português
            print(f"Cliente Gemini configurado para o modelo {self.model_name}")
        except Exception as e:
             # Mensagem em português
            print(f"Erro ao configurar cliente Gemini: {e}")
            self.model = None # Marca modelo como indisponível

    async def generate(self, prompt: str) -> str:
        if not self.model:
             # Mensagem em português
            return f"Erro: Modelo Gemini ({self.model_name}) não inicializado."
        # Mensagem em português
        print(f"[LLMManager/GeminiClient] Gerando conteúdo com {self.model_name}...")
        try:
            # Simula latência (remover ou ajustar se não for mais necessária)
            await asyncio.sleep(0.1)
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=self.temperature,
                    top_k=self.top_k
                )
            )
            return response.text if hasattr(response, 'text') else str(response)
        except Exception as e:
             # Mensagem em português
            print(f"Erro durante geração Gemini ({self.model_name}): {e}")
            return f"Erro ao gerar com Gemini: {str(e)}"

class GroqClient(BaseLLMClient):
    def __init__(self, api_key: str, model_name: str = "llama3-8b-8192", temperature: float = 0.7):
        super().__init__(api_key, model_name)
        try:
            self.client = AsyncGroq(api_key=self.api_key)
            self.temperature = temperature
            # Mensagem em português
            print(f"Cliente Groq configurado para o modelo {self.model_name}")
        except Exception as e:
            # Mensagem em português
            print(f"Erro ao configurar cliente Groq: {e}")
            self.client = None

    async def generate(self, prompt: str) -> str:
        if not self.client:
             # Mensagem em português
            return f"Erro: Cliente Groq ({self.model_name}) não inicializado."
        # Mensagem em português
        print(f"[LLMManager/GroqClient] Gerando conteúdo com {self.model_name}...")
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
            )
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content or ""
            else:
                 # Mensagem em português
                return "Erro: Sem conteúdo na resposta do Groq."
        except Exception as e:
            # Mensagem em português
            print(f"Erro durante geração Groq ({self.model_name}): {e}")
            return f"Erro ao gerar com Groq: {str(e)}"

class OpenRouterClient(BaseLLMClient):
    # OpenRouter usa API compatível com OpenAI
    # Modelo padrão alterado para optimus-alpha
    def __init__(self, api_key: str, model_name: str = "openrouter/optimus-alpha", temperature: float = 0.7):
        super().__init__(api_key, model_name)
        self.temperature = temperature
        try:
            # Usa o cliente AsyncOpenAI configurado para a URL base do OpenRouter
            self.client = AsyncOpenAI(
                 api_key=api_key, # Usa a chave API fornecida (do .env OPENROUTER_API_KEY)
                 base_url="https://openrouter.ai/api/v1"
             )
             # Mensagem em português
            print(f"Cliente OpenRouter (via SDK OpenAI) configurado para o modelo {self.model_name}")
        except Exception as e:
             # Mensagem em português
            print(f"Erro ao configurar cliente OpenRouter (via SDK OpenAI): {e}")
            self.client = None

    async def generate(self, prompt: str) -> str:
        if not self.client:
             # Mensagem em português
            return f"Erro: Cliente OpenRouter (via SDK OpenAI) ({self.model_name}) não inicializado."

        # Mensagem em português
        print(f"[LLMManager/OpenRouterClient (via SDK OpenAI)] Gerando conteúdo com {self.model_name}...")
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
            )
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content or ""
            else:
                 # Mensagem em português
                return "Erro: Sem conteúdo na resposta do OpenRouter."
        except Exception as e:
             # Mensagem em português
            print(f"Erro durante geração OpenRouter (via SDK OpenAI) ({self.model_name}): {e}")
            return f"Erro ao gerar com OpenRouter (via SDK OpenAI): {str(e)}"

# --- LLM Manager ---

class LLMManager:
    def __init__(self):
        load_dotenv()
        self.clients = []
        self._client_cycle = None
        self._initialize_clients()
        if self.clients:
            self._client_cycle = cycle(self.clients)
            # Mensagem em português e lista clientes inicializados
            print(f"[LLMManager] Inicializado com {len(self.clients)} clientes: {[c.__class__.__name__ for c in self.clients]}")
        else:
             # Mensagem em português
            print("[LLMManager] Aviso: Nenhum cliente LLM foi inicializado com sucesso.")

    def _initialize_clients(self):
        """Inicializa clientes para os LLMs funcionais com base nas variáveis de ambiente."""
        # Mensagem em português
        print("[LLMManager] Inicializando clientes LLM...")

        # Gemini
        gemini_key = os.getenv("GEMINI_API_KEY")
        gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        if gemini_key:
            try:
                client = GeminiClient(api_key=gemini_key, model_name=gemini_model_name)
                if client.model:
                    self.clients.append(client)
                else:
                    # Mensagem em português
                    print(f"[LLMManager] Falha ao inicializar cliente Gemini para {gemini_model_name}.")
            except Exception as e:
                 # Mensagem em português
                print(f"[LLMManager] Erro ao inicializar cliente Gemini: {e}")
        else:
             # Mensagem em português
            print("[LLMManager] GEMINI_API_KEY não encontrada no .env. Pulando Gemini.")

        # Groq
        groq_key = os.getenv("GROQ_API_KEY")
        groq_model = os.getenv("GROQ_MODEL", "llama3-8b-8192")
        if groq_key:
            try:
                client = GroqClient(api_key=groq_key, model_name=groq_model)
                if client.client:
                    self.clients.append(client)
                else:
                     # Mensagem em português
                    print(f"[LLMManager] Falha ao inicializar cliente Groq para {groq_model}.")
            except Exception as e:
                 # Mensagem em português
                print(f"[LLMManager] Erro ao inicializar cliente Groq: {e}")
        else:
             # Mensagem em português
             print("[LLMManager] GROQ_API_KEY não encontrada. Pulando Groq.")

        # OpenRouter
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        openrouter_model = os.getenv("OPENROUTER_MODEL", "openrouter/optimus-alpha")
        if openrouter_key:
            try:
                client = OpenRouterClient(api_key=openrouter_key, model_name=openrouter_model)
                if client.client:
                    self.clients.append(client)
                    # Mensagem em português
                    print(f"[LLMManager] Cliente OpenRouter (via SDK OpenAI) adicionado para {openrouter_model}.")
                else:
                     # Mensagem em português
                    print(f"[LLMManager] Falha ao inicializar cliente OpenRouter (via SDK OpenAI) para {openrouter_model}.")
            except Exception as e:
                 # Mensagem em português
                print(f"[LLMManager] Erro ao inicializar cliente OpenRouter: {e}")
        else:
             # Mensagem em português
            print("[LLMManager] OPENROUTER_API_KEY não encontrada. Pulando OpenRouter.")

        # Blocos de inicialização removidos para OpenAI, Anthropic, Mistral, Qwen

    async def generate(self, prompt: str) -> str:
        """Seleciona o próximo cliente usando round-robin e gera conteúdo."""
        if not self._client_cycle:
             # Mensagem em português
            return "Erro: Nenhum cliente LLM disponível."

        selected_client = next(self._client_cycle)
        client_name = selected_client.__class__.__name__
        model_name = selected_client.model_name
         # Mensagem em português
        print(f"[LLMManager] Roteando para cliente: {client_name} (Modelo: {model_name})")

        try:
            response = await selected_client.generate(prompt)
            # Verificação básica de mensagens de erro retornadas pelo método generate do cliente
            if isinstance(response, str) and (response.startswith("Erro:") or response.startswith("Aviso:")):
                 # Mensagem em português
                print(f"[LLMManager] Cliente {client_name} retornou um erro/aviso: {response}")
                # Opcionalmente, implementar retentativa com próximo cliente aqui
                # return await self.generate(prompt) # Retentativa imediata simples (pode causar loops)
            return response
        except Exception as e:
             # Mensagem em português
            print(f"[LLMManager] Exceção durante geração com {client_name} ({model_name}): {e}")
            # Opcionalmente: tentar o próximo cliente ou apenas retornar o erro
            return f"Erro ao gerar com {client_name}: {str(e)}"

# Código de teste removido (movido para tests/test_llm_clients.py) 