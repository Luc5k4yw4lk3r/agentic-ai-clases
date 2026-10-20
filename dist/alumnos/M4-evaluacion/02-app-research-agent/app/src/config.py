"""Configuración de modelos de la app. Los nombres salen del .env, nunca del código.

[Adaptación clase] El original tenía "openai:o4-mini" (planner) y "openai:gpt-4.1-mini"
(agentes) escritos a mano en cada función. Acá se leen de MODEL_CHEAP / MODEL_STRONG, igual
que en los notebooks del material, y se les agrega el prefijo "openai:" que usa aisuite.
"""
import os

from dotenv import load_dotenv

load_dotenv()

MODEL_CHEAP = os.getenv("MODEL_CHEAP", "gpt-4.1-mini")   # research, writer, editor
MODEL_STRONG = os.getenv("MODEL_STRONG", "gpt-4.1")      # planner (el original usaba un modelo de razonamiento)

AI_CHEAP = f"openai:{MODEL_CHEAP}"
AI_STRONG = f"openai:{MODEL_STRONG}"
