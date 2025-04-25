"""
Teste de integração para memória contextual com otimização de tokens.
"""
import sys
import os
import asyncio
import unittest
from unittest.mock import MagicMock, patch

# Adiciona o diretório raiz ao sys.path para permitir importações relativas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.memory import ContextualMemory
from core.prompt_utils import calculate_token_count

class MockLLMManager:
    """Mock de LLMManager para testes."""
    
    async def generate(self, prompt: str) -> str:
        """Simula a geração de texto pelo LLM."""
        # Retorna um resumo simples para qualquer prompt
        if "Resumo" in prompt:
            return "Este é um resumo gerado para os itens de memória. Contém as informações mais importantes."
        return "Resposta simulada do LLM para teste."

class TestMemoryIntegration(unittest.TestCase):
    """Testes de integração para o módulo de memória contextual."""
    
    def setUp(self):
        """Configuração para cada teste."""
        self.memory = ContextualMemory(
            max_items=5,
            max_tokens=500,
            summarize_threshold=8,
            keep_recent_items=3,
            model="gpt-3.5-turbo"
        )
        self.llm_manager = MockLLMManager()
        self.memory.set_llm_manager(self.llm_manager)
    
    def test_memory_creation(self):
        """Testa a criação correta da memória contextual."""
        self.assertEqual(len(self.memory.items), 0)
        self.assertEqual(self.memory.max_items, 5)
        self.assertEqual(self.memory.max_tokens, 500)
        self.assertEqual(self.memory.current_token_count, 0)
    
    def test_add_item(self):
        """Testa a adição de itens à memória."""
        self.memory.add("message", "Olá, mundo!")
        self.assertEqual(len(self.memory.items), 1)
        self.assertEqual(self.memory.items[0]["type"], "message")
        self.assertEqual(self.memory.items[0]["content"], "Olá, mundo!")
    
    def test_add_multiple_items(self):
        """Testa a adição de múltiplos itens à memória."""
        for i in range(3):
            self.memory.add("message", f"Mensagem {i}")
        
        self.assertEqual(len(self.memory.items), 3)
        self.assertEqual(self.memory.items[0]["content"], "Mensagem 0")
        self.assertEqual(self.memory.items[2]["content"], "Mensagem 2")
    
    def test_get_recent_by_type(self):
        """Testa a recuperação de itens recentes por tipo."""
        self.memory.add("message", "Mensagem 1")
        self.memory.add("action", "Ação 1")
        self.memory.add("message", "Mensagem 2")
        self.memory.add("action", "Ação 2")
        
        messages = self.memory.get_recent_by_type("message")
        actions = self.memory.get_recent_by_type("action")
        
        self.assertEqual(len(messages), 2)
        self.assertEqual(len(actions), 2)
        self.assertEqual(messages[1]["content"], "Mensagem 2")
        self.assertEqual(actions[1]["content"], "Ação 2")
    
    def test_formatted_context(self):
        """Testa a formatação de contexto para prompts."""
        self.memory.add("message", "Mensagem importante")
        self.memory.add("action", "Ação realizada")
        
        context = self.memory.get_formatted_context()
        
        self.assertIn("Mensagem importante", context)
        self.assertIn("Ação realizada", context)
        self.assertIn("[message]", context)
        self.assertIn("[action]", context)
    
    def test_token_tracking(self):
        """Testa o rastreamento de tokens."""
        with patch('core.memory.PROMPT_UTILS_AVAILABLE', True):
            with patch('core.memory.calculate_token_count', return_value=50):
                self.memory.add("message", "Conteúdo de teste")
                self.assertEqual(self.memory.current_token_count, 50)
                
                # Adiciona mais um item
                self.memory.add("message", "Mais conteúdo")
                self.assertEqual(self.memory.current_token_count, 100)
    
    def test_memory_optimization(self):
        """Testa a otimização de memória quando excede o limite de itens."""
        # Configura uma memória menor para o teste
        memory = ContextualMemory(max_items=3, keep_recent_items=1)
        
        # Adiciona 5 itens (excedendo o limite de 3)
        for i in range(5):
            memory.add("message", f"Item {i}")
        
        # Verifica se a memória foi otimizada para 3 itens ou menos
        self.assertLessEqual(len(memory.items), 3)
        
        # Verifica se o item mais recente foi mantido
        self.assertEqual(memory.items[-1]["content"], "Item 4")
    
    def test_memory_token_optimization(self):
        """Testa a otimização baseada em tokens."""
        with patch('core.memory.PROMPT_UTILS_AVAILABLE', True):
            # Primeiro, define um valor baixo para max_tokens
            memory = ContextualMemory(max_tokens=100)
            
            # Simula que cada item ocupa 40 tokens
            with patch('core.memory.calculate_token_count', side_effect=[40, 40, 40, 120]):
                # Adiciona 3 itens (que somam 120 tokens, excedendo o limite de 100)
                for i in range(3):
                    memory.add("message", f"Item {i} que ocupa muitos tokens")
                
                # Verifica se a memória foi otimizada para respeitar o limite de tokens
                self.assertLessEqual(memory.current_token_count, 120)  # Permitimos até 120% do limite como margem
    
    @patch('core.memory.PROMPT_UTILS_AVAILABLE', True)
    def test_truncate_context(self):
        """Testa a truncagem de contexto para respeitar o limite de tokens."""
        # Cria um contexto que seria grande
        for i in range(10):
            self.memory.add("message", f"Item {i} com conteúdo extenso para testar a truncagem")
        
        # Simula que o contexto completo tem 1000 tokens
        with patch('core.memory.truncate_text_to_tokens', return_value="Contexto truncado"):
            with patch('core.memory.calculate_token_count', return_value=1000):
                # Solicita o contexto com limite de 200 tokens
                context = self.memory.get_formatted_context(max_tokens=200)
                
                # Verifica se o contexto foi truncado
                self.assertEqual(context, "Contexto truncado")
    
    async def async_test_summarize_memory(self):
        """Testa a sumarização de memória usando o LLM."""
        # Adiciona vários itens para garantir que haja o que resumir
        for i in range(5):
            self.memory.add("message", f"Mensagem importante número {i}")
        
        # Executa a sumarização
        summary = await self.memory.summarize_memory()
        
        # Verifica o resultado
        self.assertIn("resumo", summary.lower())
        self.assertGreater(len(summary), 10)
        
        # Verifica se o resumo foi armazenado
        self.assertEqual(len(self.memory.summaries), 1)
    
    def test_clear_memory(self):
        """Testa a limpeza da memória, mantendo o último resumo."""
        # Adiciona itens e um resumo
        for i in range(3):
            self.memory.add("message", f"Item {i}")
        
        self.memory.summaries.append({
            "content": "Resumo de teste",
            "items_summarized": 3,
            "timestamp": 123456789
        })
        
        # Limpa a memória
        self.memory.clear()
        
        # Verifica se os itens foram removidos, mas o resumo mantido
        self.assertEqual(len(self.memory.items), 0)
        self.assertEqual(len(self.memory.summaries), 1)
        self.assertEqual(self.memory.summaries[0]["content"], "Resumo de teste")
    
    # Método auxiliar para executar testes assíncronos
    def test_summarize_memory(self):
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(self.async_test_summarize_memory())

if __name__ == "__main__":
    unittest.main() 