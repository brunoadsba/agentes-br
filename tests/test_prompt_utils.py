import unittest
import sys
import os
from unittest.mock import patch

# Adiciona o diretório raiz ao sys.path para permitir importações relativas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.prompt_utils import (
    calculate_token_count, 
    get_model_context_window,
    truncate_text_to_tokens,
    optimize_prompt_for_tokens,
    create_optimized_system_prompt
)

class TestPromptUtils(unittest.TestCase):
    """Testes para o módulo de utilitários de prompts e gerenciamento de tokens."""
    
    def test_calculate_token_count(self):
        """Testa a função de cálculo de tokens."""
        # Cria um texto de teste com 
        text = "Este é um teste de cálculo de tokens. " * 20  # Repetido 20 vezes
        
        # Test com tiktoken indisponível (mockado)
        with patch('core.prompt_utils.TIKTOKEN_AVAILABLE', False):
            tokens = calculate_token_count(text)
            self.assertGreater(tokens, 0)
            self.assertLess(tokens, len(text))  # Tokens devem ser menos que caracteres
        
        # Resultado padrão com texto vazio
        self.assertEqual(calculate_token_count(""), 0)
        
        # Texto longo deve ter mais tokens que texto curto
        short_text = "Texto curto."
        long_text = short_text * 10
        self.assertGreater(
            calculate_token_count(long_text), 
            calculate_token_count(short_text)
        )

    def test_get_model_context_window(self):
        """Testa a função que retorna o tamanho da janela de contexto de um modelo."""
        # Modelos conhecidos devem retornar valores específicos
        self.assertEqual(get_model_context_window("gpt-3.5-turbo"), 16385)
        self.assertEqual(get_model_context_window("gpt-4"), 8192)
        
        # Deve funcionar com maiúsculas/minúsculas misturadas
        self.assertEqual(get_model_context_window("GPT-4"), 8192)
        
        # Deve funcionar com substrings (modelo parcial)
        self.assertEqual(get_model_context_window("modelo-gpt-4-customizado"), 8192)
        
        # Modelo desconhecido deve retornar valor padrão
        self.assertEqual(get_model_context_window("modelo-desconhecido"), 4096)

    def test_truncate_text_to_tokens(self):
        """Testa a função de truncamento de texto baseado em tokens."""
        # Texto de teste longo
        long_text = "Este é um parágrafo de teste.\n\n" * 100
        
        # Trunca para um número específico de tokens
        truncated = truncate_text_to_tokens(long_text, 50)
        
        # Verifica se o texto foi truncado
        self.assertLess(len(truncated), len(long_text))
        
        # Verifica se o número de tokens está próximo ao solicitado
        with patch('core.prompt_utils.TIKTOKEN_AVAILABLE', False):  # Força usar estimativa simples
            tokens = calculate_token_count(truncated)
            # Permitimos uma margem de erro na estimativa
            self.assertLessEqual(tokens, 60)  # Até 20% a mais
            
        # Verifica se o texto não é truncado quando já está abaixo do limite
        short_text = "Texto curto para teste."
        self.assertEqual(
            truncate_text_to_tokens(short_text, 100),
            short_text
        )
        
        # Verifica se o indicador de truncamento está presente
        self.assertIn("[Conteúdo truncado", truncated)
    
    def test_optimize_prompt_for_tokens(self):
        """Testa a função de otimização de prompts."""
        # Cria um prompt de teste com múltiplas seções
        test_prompt = """# Seção Principal
Este é o conteúdo da seção principal.

## Seção Importante
Este é um conteúdo que não deve ser removido.

## Seção Secundária
Este é um conteúdo menos importante que pode ser truncado.

## Outra Seção Importante
Este conteúdo também deve ser preservado.
"""
        
        # Otimiza sem seções prioritárias (deve truncar igualmente)
        with patch('core.prompt_utils.calculate_token_count', return_value=500):
            # Simulamos que o prompt tem 500 tokens
            with patch('core.prompt_utils.truncate_text_to_tokens') as mock_truncate:
                # Testa se truncate_text_to_tokens é chamado como esperado
                optimize_prompt_for_tokens(test_prompt, 300)
                mock_truncate.assert_called_once()
        
        # Otimiza com seções prioritárias
        with patch('core.prompt_utils.calculate_token_count') as mock_count:
            # Configura o mock para retornar valores decrescentes a cada chamada
            mock_count.side_effect = [500, 200, 150, 100, 50, 30, 20, 10]
            
            result = optimize_prompt_for_tokens(
                test_prompt, 
                200, 
                keep_sections=["Importante"]
            )
            
            # Verifica se as seções importantes foram mantidas
            self.assertIn("Seção Importante", result)
            self.assertIn("Outra Seção Importante", result)
    
    def test_create_optimized_system_prompt(self):
        """Testa a função que cria um prompt de sistema otimizado."""
        base_prompt = """# Instruções do Sistema
Siga estas regras importantes.

## Regras
1. Seja conciso
2. Seja claro
3. Seja útil

## Personalidade
Você deve ser amigável e prestativo.

## Contexto
[Será substituído]
"""
        
        context = "Informações de contexto " * 50  # Contexto artificialmente longo
        
        # Testa criação de prompt otimizado
        result = create_optimized_system_prompt(
            base_prompt=base_prompt,
            context=context,
            max_tokens=1000,
            essential_sections=["Regras", "Instruções"]
        )
        
        # Verifica se as seções essenciais foram mantidas
        self.assertIn("# Instruções do Sistema", result)
        self.assertIn("## Regras", result)
        
        # Verifica se o contexto foi incluído
        self.assertIn("## Contexto", result)
        self.assertIn("Informações de contexto", result)

if __name__ == "__main__":
    unittest.main() 