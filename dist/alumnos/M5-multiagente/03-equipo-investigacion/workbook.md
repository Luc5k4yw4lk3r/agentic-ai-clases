# Equipo de investigación: planner, executor y tres especialistas

**Módulo 5 · Lab 03.** Un planner arma la lista de pasos; un executor rutea cada paso a un
agente especialista (Research con tools, Writer, Editor) acumulando un historial, hasta que
el último paso produce un informe en Markdown que se guarda en `data/informe.md`.

## Antes de empezar (quiz de 5 preguntas)

1. (Repaso sesión 1) ¿Qué controla el namespace que le pasamos a `exec` en el lab 02?
   a) qué puede hacer el código  b) qué variables ve  c) cuánto tiempo corre
2. (Repaso sesión 1) Ventaja del plan como JSON de tools (lab 01) frente al código como plan
   (lab 02): a) más expresivo  b) catálogo cerrado: el peor caso es `Tool desconocida`  c) más rápido
3. (Nuevo) El executor recibe `{"agente": "agente_research", "tarea": "..."}`. ¿Qué hace?
   a) lo imprime  b) busca la función en `registro_agentes` y la llama con la tarea más el
   historial  c) se lo pasa al planner
4. (Nuevo) El Research recibe tools como funciones Python y `max_turns=6`. ¿Quién ejecuta
   las funciones? a) OpenAI  b) `aisuite`, en tu máquina, hasta 6 vueltas  c) nadie
5. (Base) `historial = [("buscar", "agente_research", "texto")]`; `historial[-1][1]` es:
   a) `"buscar"`  b) `"agente_research"`  c) `"texto"`

## 1. Teoría breve

### Para qué: dividir el trabajo

En M3 un agente hacía todo (buscar, escribir, corregir) con un prompt gigante. Cuando el
informe salía mal, no se sabía qué parte había fallado. Acá cada rol tiene su función, su
prompt y su modelo:

| Agente | Modelo | Tools | Responsabilidad |
|---|---|---|---|
| `agente_planner` | fuerte | no | tema → lista de pasos |
| `agente_research` | barato | arXiv, Tavily, Wikipedia | buscar y resumir con fuentes |
| `agente_writer` | barato | no | redactar |
| `agente_editor` | fuerte | no | criticar y corregir |
| `agente_executor` | barato (ruteo) | no | recorrer el plan, elegir quién, acumular historial |

### Por qué así: un router con memoria

El executor **no investiga ni escribe**. Para cada paso hace tres cosas:

1. Le pregunta a un modelo barato "¿quién hace esto?" y recibe un JSON chico.
2. Valida el JSON (`utils.limpiar_json` + `json.loads` + "¿el agente existe en
   `registro_agentes`?").
3. Arma la tarea "enriquecida" = rol + historial de pasos anteriores + tarea, llama a la
   función elegida y guarda `(paso, agente, salida)`.

El historial es lo que convierte cinco funciones sueltas en un equipo: el Writer del paso 4
lee lo que el Research encontró en los pasos 1 y 2.

```text
tema ──► planner ──► ["Buscar...", "Buscar...", "Redactar...", "Revisar...", "Redactar el informe en Markdown"]
                           │
                           ▼  por cada paso
                     LLM barato ──► {"agente": "agente_research", "tarea": "..."}
                     registro_agentes["agente_research"](rol + historial + tarea) ──► salida
                     historial.append((paso, "agente_research", salida))
                           │
                           ▼
                     historial[-1][2] ──► data/informe.md
```

### Dos decisiones que el original no tomaba bien

- **`eval()` para leer el plan.** El original pedía "una lista de Python" y la leía con
  `eval(...)`. Eso ejecuta lo que el modelo escriba. Acá se pide JSON y se parsea con
  `json.loads` después de `limpiar_json` (que saca las fences ```json). Si no es una lista
  de strings, `ValueError`.
- **Nombres de tools inventados en el prompt.** El original decía `arxiv_tool`,
  `tavily_tool`, `wikipedia_tool`; las funciones se llaman `arxiv_search_tool`,
  `tavily_search_tool`, `wikipedia_search_tool`. El modelo veía dos listas que no coincidían.
  Acá el system prompt usa los nombres reales.

### Costo: diseñarlo, no sufrirlo

Una corrida completa son **15 a 25 llamadas**: 1 del planner + por paso (1 de ruteo + 1 del
agente + hasta 6 vueltas de tools si es Research). Por eso:

- `max_turns=6` en vez de 12.
- En clase, el pipeline completo se corre **una vez**.
- Para desarrollar y depurar se usa `PLAN_CORTO` (3 pasos, 8 a 10 llamadas).

## 2. Ejemplo resuelto

El patrón de todos los agentes es el de `agente_resumidor` (sección 3 del notebook):

```python
def agente_resumidor(texto: str, model: str = AI_CHEAP) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Sos un asistente que resume textos técnicos en UNA oración clara, en español."},
            {"role": "user", "content": texto},
        ],
    )
    return response.choices[0].message.content
```

Un plan típico del planner para el tema del lab (*ejemplo ilustrativo, varía entre corridas*):

```json
["Buscar en arXiv papers fundacionales y recientes sobre el ensemble Kalman filter aplicado a pronóstico de series de tiempo",
 "Buscar en Wikipedia la definición del ensemble Kalman filter y sus diferencias con el filtro de Kalman clásico",
 "Redactar un borrador de informe con introducción, fundamentos, aplicaciones y limitaciones, citando las fuentes",
 "Revisar el borrador: claridad, estructura y afirmaciones sin fuente",
 "Redactar el informe completo en formato Markdown incorporando las correcciones"]
```

Y el log del executor para ese plan (*ilustrativo*):

```text
[1/5] agente_research  ←  Buscar en arXiv papers fundacionales y recientes sobre el ensemble Kalman filter...
  tools usadas: 2
      → 1840 caracteres
[2/5] agente_research  ←  Buscar en Wikipedia la definición del ensemble Kalman filter y sus diferencias...
  tools usadas: 1
      → 1210 caracteres
[3/5] agente_writer  ←  Redactar un borrador de informe con introducción, fundamentos, aplicaciones...
      → 3900 caracteres
[4/5] agente_editor  ←  Revisar el borrador: claridad, estructura y afirmaciones sin fuente
      → 1100 caracteres
[5/5] agente_writer  ←  Redactar el informe completo en formato Markdown incorporando las correcciones
      → 4300 caracteres
Informe guardado en data/informe.md (4300 caracteres)
```

Lo que **sí** es determinístico: `len(historial) == len(pasos)`, cada elemento es una tupla
de tres strings, y `historial[-1][1]` es `"agente_writer"` si el último paso dice "redactar".

## 3. Práctica graduada

### Nivel base (uno a uno con los huecos del notebook)

1. **Planner, llamada.** En `agente_planner`, llamá al modelo con el `prompt` como único
   mensaje `user` y guardá `response.choices[0].message.content`.
2. **Planner, parseo.** `json.loads(utils.limpiar_json(contenido))`; validá lista no vacía
   de strings no vacíos; `ValueError` si no. Probalo con `TEMA` (1 llamada al modelo fuerte).
3. **Research, llamada con tools.** Pasá `tools=[las tres funciones]` y `max_turns=max_turns`.
   Fijate que el system prompt ya nombra las tools con sus nombres reales.
4. **Research, lectura.** Contá los mensajes de rol `"tool"` en
   `response.choices[0].intermediate_messages`, imprimí `tools usadas: N`, devolvé el
   contenido (o un aviso si es `None`).
5. **Writer.** System de redactor + user con la tarea. Modelo barato.
6. **Editor.** System de editor + user con la tarea. Modelo fuerte.
7. **Executor, ruteo.** Llamá al modelo con `prompt_ruteo`, parseá con
   `json.loads(utils.limpiar_json(...))`, validá `agente in registro_agentes` y `tarea` no
   vacía.
8. **Executor, despacho.** Armá la tarea enriquecida con `armar_contexto(historial)`, imprimí
   el log, llamá `registro_agentes[agente](tarea_enriquecida)` y agregá la tupla al historial.
   Probalo con `PLAN_CORTO` (no con el plan completo).

Al terminar, **antes** de la corrida completa:

```python
from tests import run_all
run_all(agente_planner, agente_executor, registro_agentes, namespace=globals())
```

Los tests usan un cliente simulado: no gastan ninguna llamada.

### Extensión opcional

- **Contar llamadas.** Envolvé `client.chat.completions.create` con una función que
  incremente un contador global y corré `PLAN_CORTO`. Anotá: total, cuántas de ruteo,
  cuántas de Research (mirá `tools usadas`). Compará con la estimación de la sección 1.
- **Cuarto agente.** `agente_verificador(tarea)` recibe el informe y el historial en la
  tarea y chequea que cada URL del informe aparezca en alguna salida de Research. Sumalo a
  `registro_agentes`, al prompt del planner y al de ruteo.
- **Ruteo sin LLM.** Reemplazá la llamada de ruteo por reglas: "buscar" → research,
  "revisar"/"criticar" → editor, resto → writer. Corré los dos ruteos sobre el mismo plan y
  compará. ¿Dónde se equivoca el de reglas? ¿Compensa la llamada que ahorra?
- **Historial acotado.** Pasá solo las últimas dos salidas en `armar_contexto`. Medí
  caracteres enviados y leé el informe: ¿perdió fuentes?
- **Plan en inglés.** Cambiá el prompt del planner para que los pasos de búsqueda incluyan
  la query en inglés entre comillas. ¿Mejoran las fuentes del Research?

## 4. Troubleshooting de más a menos frecuente

| Síntoma | Causa | Arreglo |
|---|---|---|
| `ValueError: El planner tenía que devolver una lista JSON no vacía y devolvió: '{"plan": [...` | El modelo envolvió la lista en un objeto | Reforzá "ÚNICAMENTE una lista JSON de strings". Como alternativa, aceptá el dict y tomá su única lista. |
| `JSONDecodeError` al rutear | El modelo agregó texto o fences que `limpiar_json` no sacó (raro) | Imprimí `response.choices[0].message.content` crudo y mirá qué vino. |
| `ValueError: El router eligió un agente desconocido: 'research_agent'` | El modelo tradujo el nombre al inglés | Está bien que falle: el nombre es un contrato. Agregá al prompt de ruteo "copiá el nombre exactamente". |
| `tools usadas: 0` y el Research responde sin fuentes | La tarea no pedía buscar, o el modelo decidió que ya sabía | Pedí explícito en la tarea "usá al menos una tool". Verificá que `tools=` esté pasado y que `max_turns` no sea 0. |
| El Research devuelve `None` / el aviso de "agotó turnos" | 6 vueltas se fueron en tool calls sin respuesta final | Subí `max_turns` a 8 para ese paso o pedí "máximo 3 búsquedas" en la tarea. |
| `AVISO: sin TAVILY_API_KEY` | No está la key en `.env` | No es un error: `tavily_search_tool` cae a Wikipedia y lo marca en `source`. |
| El informe final está envuelto en ```markdown | El Writer puso fences | Ya se contempla con `utils.quitar_fences` antes de guardar. |
| `ProxyError` / `ConnectionError` en las tools | Sin red o proxy corporativo | Las tools levantan la excepción; aisuite la devuelve al modelo como resultado de la tool. Probá la red con la celda de la sección 2. |

## 5. Para cerrar

**Tres preguntas de reflexión**

1. El executor le pregunta a un LLM quién hace cada paso. ¿Por qué no le pedimos al planner
   que ya devuelva `{"agente": ..., "tarea": ...}` por paso? ¿Qué se gana y qué se pierde?
2. El Editor no tiene tools. ¿Debería tenerlas para verificar fuentes? ¿Qué costo tendría?
3. ¿Qué parte de este pipeline evaluarías primero con una evaluación por componente (M4)
   y con qué métrica?

**Checklist de autoevaluación**

- [ ] Puedo dibujar el flujo tema → planner → executor → agentes → historial → informe.
- [ ] Mi planner parsea con `json.loads` y rechaza lo que no es lista de strings.
- [ ] Mi Research pasa las tres funciones como tools, con `max_turns=6`, y el system prompt
      las nombra con sus nombres reales.
- [ ] Mi executor devuelve `(paso, agente, salida)` por paso y pasa el historial al siguiente.
- [ ] `run_all(...)` pasa los 13 tests sin gastar llamadas, y `data/informe.md` existe.
