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
        self._initialize_clients()
        if self.clients:
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
        """Seleciona o próximo cliente usando round-robin e gera conteúdo, com retentativa em caso de erros recuperáveis."""
        if not self.clients:
             # Mensagem em português
            return "Erro: Nenhum cliente LLM disponível."

        available_clients = list(self.clients)
        clients_tried_count = 0
        last_error = "Nenhum erro registrado."

        start_index = getattr(self, '_last_client_index', -1) + 1
        if start_index >= len(available_clients):
            start_index = 0

        while clients_tried_count < len(available_clients):
            current_index = (start_index + clients_tried_count) % len(available_clients)
            selected_client = available_clients[current_index]

            client_name = selected_client.__class__.__name__
            model_name = selected_client.model_name
            print(f"[LLMManager] Tentando cliente: {client_name} (Modelo: {model_name}) - Tentativa {clients_tried_count + 1}/{len(available_clients)}")
            clients_tried_count += 1

            try:
                response = await selected_client.generate(prompt)
                is_error_response = isinstance(response, str) and response.startswith("Erro:")
                is_retryable_error = False

                if is_error_response:
                    last_error = response
                    if "403" in response or "Access denied" in response: # Erro específico do Groq/VPN
                        print(f"[LLMManager] Alerta: Erro 403 (Acesso Negado) com {client_name}. Verifique restrições de rede ou desative VPNs se estiver usando uma.")
                        is_retryable_error = True
                    elif "429" in response: # Too Many Requests
                        is_retryable_error = True
                        print(f"[LLMManager] Erro 429 (Limite de Taxa) detectado com {client_name}.")
                    elif any(code in response for code in ["500", "502", "503", "504"]): # Server errors
                        is_retryable_error = True
                        print(f"[LLMManager] Erro de servidor (5xx) detectado com {client_name}.")
                    elif "network error" in response.lower() or "connection error" in response.lower():
                         is_retryable_error = True
                         print(f"[LLMManager] Erro de rede detectado com {client_name}.")

                if not is_error_response:
                    self._last_client_index = current_index
                    print(f"[LLMManager] Sucesso com {client_name} (Modelo: {model_name}).")
                    return response
                elif is_retryable_error:
                    print(f"[LLMManager] Cliente {client_name} falhou com erro recuperável. Tentando próximo cliente...")
                    await asyncio.sleep(0.2)
                    continue
                else:
                    print(f"[LLMManager] Cliente {client_name} retornou erro não recuperável: {response}")
                    last_error = response
                    continue

            except Exception as e:
                last_error = f"Exceção com {client_name}: {type(e).__name__} - {str(e)}"
                print(f"[LLMManager] {last_error}")
                if clients_tried_count < len(available_clients):
                    print(f"[LLMManager] Tentando próximo cliente devido à exceção...")
                    await asyncio.sleep(0.2)
                    continue
                else:
                    print(f"[LLMManager] Exceção ocorreu na última tentativa com {client_name}.")

        final_error_msg = f"Erro: Todos os {len(self.clients)} clientes LLM falharam após tentativas. Último erro registrado: {last_error}"
        print(f"[LLMManager] {final_error_msg}")
        return final_error_msg

# Código de teste removido (movido para tests/test_llm_clients.py) 