import unittest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import json
import sys
import os
from typing import Optional, Dict, Any, List

# Adicionar o diretório raiz ao path para importar os módulos do projeto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.models import Agent, BaseTool, ContextualMemory
from core.llm_manager import LLMManager
from tools.web_navigator import WebNavigatorTool
from tools.web_interactor import WebInteractorTool

class MockLLMManager:
    """Simulação do LLMManager para testes."""
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.generate_calls = []
    
    async def generate(self, prompt):
        self.generate_calls.append(prompt)
        # Retorna uma resposta predefinida ou um padrão se não encontrar
        # Procura por palavras-chave no prompt
        for key, response in self.responses.items():
            if key.lower() in prompt.lower():
                return response
        return '{"tool_name": "MockTool", "parameters": {"action": "test"}}'

class MockTool(BaseTool):
    """Ferramenta de teste que registra as chamadas e retorna resultados predefinidos."""
    def __init__(self, result="Mock tool executed successfully"):
        self.calls = []
        self.result = result
    
    async def run(self, *args, **kwargs):
        self.calls.append(kwargs)
        return self.result

class TestAgent(unittest.TestCase):
    """Testes para a classe Agent."""
    
    def setUp(self):
        # Configurar respostas do LLM para diferentes prompts
        self.mock_responses = {
            "fill": '{"tool_name": "WebInteractorTool", "parameters": {"action": "fill", "selector": "#test", "value": "test-value"}}',
            "click": '{"tool_name": "WebInteractorTool", "parameters": {"action": "click", "selector": "#btn"}}',
            "navigate": '{"tool_name": "WebNavigatorTool", "parameters": {"url": "https://test.com"}}',
            "none": '{"tool_name": "Nenhuma ferramenta", "parameters": {}}',
            "invalid": 'Texto que não é JSON',
            "invalid_json": '{not_valid_json}'
        }
        
        self.llm_manager = MockLLMManager(self.mock_responses)
        self.mock_tool = MockTool()
        
        # Criar um agente para testes
        self.agent = Agent(
            name="TestAgent",
            role="Agente de teste",
            llm_manager=self.llm_manager,
            tools=[self.mock_tool],
            memory=ContextualMemory()
        )
    
    async def async_test(self, coroutine):
        """Helper para executar testes assíncronos."""
        return await coroutine
    
    def test_agent_init(self):
        """Teste da inicialização do Agent."""
        self.assertEqual(self.agent.name, "TestAgent")
        self.assertEqual(self.agent.role, "Agente de teste")
        self.assertEqual(list(self.agent.tools.keys()), ["MockTool"])
        self.assertIsNotNone(self.agent.memory)
    
    def test_execute_with_valid_tool(self):
        """Teste do método execute com uma ferramenta válida."""
        # Executar o teste async
        result = asyncio.run(self.agent.execute("Faça uma tarefa fill"))
        # Verificar se o LLM foi chamado
        self.assertTrue(len(self.llm_manager.generate_calls) >= 1)
        # Verificar se a ferramenta foi chamada
        self.assertEqual(len(self.mock_tool.calls), 1)
    
    def test_execute_with_no_tool(self):
        """Teste do método execute quando nenhuma ferramenta é necessária."""
        result = asyncio.run(self.agent.execute("Faça uma tarefa none"))
        # Verificar se o LLM foi chamado
        self.assertTrue(len(self.llm_manager.generate_calls) >= 1)
        # Verificar que a ferramenta não foi chamada
        self.assertEqual(len(self.mock_tool.calls), 0)
    
    def test_execute_with_invalid_json(self):
        """Teste do método execute com resposta JSON inválida."""
        result = asyncio.run(self.agent.execute("Faça uma tarefa invalid"))
        # Verificar que a ferramenta não foi chamada
        self.assertEqual(len(self.mock_tool.calls), 0)
        # Verificar que o erro foi registrado
        self.assertIn("Erro", result)
    
    def test_memory_storage(self):
        """Teste do armazenamento na memória."""
        # Executar uma tarefa
        asyncio.run(self.agent.execute("Faça uma tarefa fill"))
        # Verificar se a memória tem o item
        self.assertEqual(len(self.agent.memory.retrieve_individual("TestAgent")), 1)
        self.assertEqual(len(self.agent.memory.retrieve_global()), 1)

class TestWebTools(unittest.TestCase):
    """Testes para as ferramentas Web."""
    
    def setUp(self):
        # Mock para Page do Playwright
        self.mock_page = MagicMock()
        self.mock_page.is_closed.return_value = False
        
        # Mock para Locator
        self.mock_locator = MagicMock()
        self.mock_page.locator.return_value = self.mock_locator
        
        # WebInteractorTool para testes
        self.web_interactor = WebInteractorTool()
    
    async def test_web_interactor_fill(self):
        """Teste da ação fill do WebInteractorTool."""
        # Configurar o mock
        action_json = json.dumps({"action": "fill", "selector": "#test", "value": "test-value"})
        
        # Executar
        result = await self.web_interactor.run(
            page=self.mock_page,
            action_details_json=action_json
        )
        
        # Verificar
        self.mock_page.locator.assert_called_with("#test")
        self.mock_locator.fill.assert_called_once()
        self.assertIn("sucesso", result)
    
    async def test_web_interactor_click(self):
        """Teste da ação click do WebInteractorTool."""
        # Configurar o mock
        action_json = json.dumps({"action": "click", "selector": "#btn"})
        
        # Executar
        result = await self.web_interactor.run(
            page=self.mock_page,
            action_details_json=action_json
        )
        
        # Verificar
        self.mock_page.locator.assert_called_with("#btn")
        self.mock_locator.click.assert_called_once()
        self.assertIn("sucesso", result)
    
    async def test_web_interactor_error_handling(self):
        """Teste do tratamento de erros do WebInteractorTool."""
        # Configurar o mock para lançar exceção
        self.mock_locator.fill.side_effect = Exception("Test error")
        action_json = json.dumps({"action": "fill", "selector": "#test", "value": "test-value"})
        
        # Executar
        result = await self.web_interactor.run(
            page=self.mock_page,
            action_details_json=action_json
        )
        
        # Verificar
        self.assertIn("Erro", result)

    async def test_web_interactor_invalid_json(self):
        """Teste com JSON inválido."""
        # Executar com JSON inválido
        result = await self.web_interactor.run(
            page=self.mock_page,
            action_details_json="{invalid json"
        )
        
        # Verificar
        self.assertIn("Erro", result)
        self.assertIn("Falha ao decodificar JSON", result)

if __name__ == "__main__":
    unittest.main() 