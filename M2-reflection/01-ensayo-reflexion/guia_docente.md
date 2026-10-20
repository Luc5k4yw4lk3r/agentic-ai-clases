# Guía docente — Reflexión sobre un ensayo: borrador → crítica → revisión

## Ficha

| | |
|---|---|
| **Duración** | 60 min dentro de la sesión 1 del módulo (ver `M2-reflection/README.md`) |
| **Prerrequisitos** | Haber corrido `setup/check_env.py`. Saber qué es una función con parámetros por defecto y un f-string. Idealmente, haber hecho al menos una llamada a un LLM por API (si no, la celda `preguntar` lo cubre). |
| **Keys** | `OPENAI_API_KEY`. No usa Tavily. |
| **Archivos** | `notebook_alumno.ipynb`, `workbook.md`, `utils.py`, `tests.py`. Sin `data/`. |
| **Costo estimado** | Por alumno, corriendo el notebook una vez: 1 (preguntar) + 3 (flujo) + 5 (bucle de 2 rondas) + 3 (test con API) = **12 llamadas** a `MODEL_STRONG`, ~1.500 tokens de salida cada una en promedio. Si se repite el bucle con otras consignas, suma 5 por corrida. Para una clase de 20, estimá unas 300 llamadas. |
| **Se evalúa** | Sí (es el graded lab del módulo original). Rúbrica al final. |

## Secuencia sugerida (60 min)

| Minuto | Qué pasa | Quién |
|---|---|---|
| 0–5 | Quiz de apertura. Se responde en voz alta; las preguntas 1 y 2 son repaso de la sesión anterior (API de chat). | Todos |
| 5–15 | Teoría breve en el pizarrón: el diagrama consigna → V1 → crítica → V2. Insistir en "tres prompts, un solo mecanismo". Mostrar un ejemplo humano (cómo corregís un mail importante). | Profesor |
| 15–20 | Live-coding de la celda resuelta `preguntar`. Ejecutarla. Mostrar `type(response)` y navegar `response.choices[0].message.content` en vivo para que vean que no es un string. | Profesor |
| 20–25 | Hueco 1, `generar_borrador`. Dar 3 minutos; es casi copiar `preguntar`. Resolverlo en pantalla si alguien se traba. | Alumnos, luego profesor |
| 25–35 | Huecos 2 y 3, `reflexionar_sobre_borrador` (ellos escriben el prompt). Pedir que lean la crítica que les salió en voz alta. Comparar dos: una genérica y una con problemas concretos. ¿Qué cambió en el prompt? | Alumnos |
| 35–45 | Huecos 4 y 5, `revisar_borrador`. Antes de que lo hagan, preguntar: "¿qué pasa si solo le mando la crítica?". Ejecutar la comparación de versiones. | Alumnos |
| 45–55 | Huecos 6 y 7, `reflexionar_en_bucle`. Es el que exige combinar. Dibujar en el pizarrón las dos listas y una variable `actual`. | Alumnos |
| 55–60 | Correr `run_all`. Leer qué dice cada FALLA. Cierre: "¿qué no puede ver un crítico que solo lee texto?" (puente al lab 02). | Todos |

Si sobra tiempo (grupo rápido), arrancar con la extensión "crítico barato, escritor
fuerte" en vivo.

## Qué hacer en vivo vs. qué dejan corriendo los alumnos

**En vivo (profesor):**
- Las celdas de setup y `preguntar`, mostrando la forma del objeto `response`.
- `generar_borrador` si el grupo se traba.
- La lectura de `run_all`: explicar qué es el `FakeClient` (un objeto que se hace
  pasar por el cliente y registra los prompts) sin entrar en detalles de
  `__globals__`.

**Los alumnos solos:**
- Los prompts de crítica y revisión (son la parte creativa del lab).
- El bucle.
- La prueba del bucle tarda ~1 minuto (5 llamadas); que la lancen y mientras
  piensen la pregunta de cierre.

## Dónde se traban (y qué decir)

1. **Devuelven `response` en vez de `.content`.** Síntoma: la celda de prueba
   imprime un tipo que no es `str`, o el borrador aparece como `ChatCompletion(id=...)`.
   Decir: "la API devuelve un sobre con metadatos; el texto está adentro". Mostrar
   `response.choices[0].message.content` paso a paso en una celda aparte.
2. **Hardcodean el modelo.** Escriben `model="openai:gpt-4.1"` dentro de la
   función. El test lo detecta. Decir: "el modelo lo decide quien llama a la
   función; vos solo lo pasás".
3. **La revisión ignora la crítica.** En `revisar_borrador` arman la instrucción
   solo con el borrador porque "la crítica ya la hizo el modelo". Decir: "cada
   llamada es nueva, el modelo no recuerda la anterior; si no la mandás, no existe".
   Este es el concepto más importante del lab.
4. **El bucle siempre critica V1.** Usan `borrador` (el primero) dentro del `for`
   en vez de una variable que se actualice. El test lo detecta con el mensaje
   "La segunda crítica tiene que criticar V2". Dibujar las listas en el pizarrón.
5. **Confunden `MODEL_STRONG` con `AI_STRONG`.** Pasan `"gpt-4.1"` sin prefijo a
   aisuite y reciben un error de proveedor. Decir: "aisuite necesita saber a quién
   llamar; por eso el prefijo `openai:`".
6. **f-string con comillas triples y llaves.** Si el borrador tiene `{` el f-string
   no se rompe (son datos), pero si ellos escriben `{}` literales en el prompt sí.
   Pedir que los eviten o los dupliquen `{{ }}`.
7. **Reiniciar el kernel después de editar `.env`.** `load_dotenv` no sobreescribe
   variables ya cargadas.

## Respuestas del quiz de apertura

1. **b.** La API de chat no tiene memoria; todo el contexto viaja en `messages`.
2. **b.** La generación es estocástica. `temperature=0` reduce la variación pero no la elimina.
3. **b.** Sin el borrador no hay qué revisar; sin la crítica no hay guía. Esta es la pregunta que anticipa el error 3 de arriba.
4. **b.** Reflexionar es evaluar un artefacto terminado; en una sola pasada el modelo no procesa su propio texto completo como entrada.
5. **b.** Parámetro con valor por defecto. Aprovechar para decir que `AI_STRONG` se evalúa al definir la función, no al llamarla.

## Soluciones de la extensión opcional (esbozo)

- **Modelos distintos por rol.** Agregar `model_escritor` y `model_critico` a la
  firma de `reflexionar_en_bucle`; pasar el primero a `generar_borrador` y
  `revisar_borrador`, el segundo a `reflexionar_sobre_borrador`. Lo esperable es
  que la crítica del modelo barato sea más genérica ("podría mejorar la
  estructura") y la del fuerte más puntual.
- **Rúbrica.** Pedir en el prompt: "Empezá con cuatro líneas `Criterio: N/5` y
  después la crítica en prosa". Opcional: parsear las puntuaciones con una regex
  simple para graficar la evolución entre rondas.
- **Condición de corte.** En el prompt del crítico: "Si el ensayo no tiene
  problemas de peso, escribí APROBADO en la primera línea". En el bucle:
  `if critica.strip().startswith("APROBADO"): break`. Discutir que el crítico casi
  nunca aprueba en la primera ronda y que eso es un sesgo del patrón.
- **Medir el largo.** `resumen_versiones` está en `utils.py`. Lo habitual es que V2
  sea 10–30 % más larga que V1 porque la crítica pide "agregar ejemplos" y nunca
  "sacar". Buen punto para discutir que "más" no es "mejor".
- **Rol de sistema.** Mover el rol a `{"role": "system", ...}`. En este lab no se
  nota diferencia; conviene explicar que el `system` pesa más cuando hay
  conversación larga y en labs posteriores con tools.

## Rúbrica

Total 10 puntos. Se corrige con `run_all` (4 chequeos sin API + 1 con API) y una
revisión rápida del código.

| Criterio | Puntos | Cómo se verifica |
|---|---|---|
| `generar_borrador` devuelve `str` con el texto del modelo y usa `model` | 2 | Test estructural 1 |
| `reflexionar_sobre_borrador` inyecta el borrador y devuelve `str` | 2 | Test estructural 2 |
| `revisar_borrador` inyecta borrador **y** crítica; la salida es la del modelo | 2 | Test estructural 3 |
| `reflexionar_en_bucle` devuelve el dict correcto y encadena sobre la última versión | 2 | Test estructural 4 |
| Flujo completo corre con la API real; la revisión difiere del borrador | 1 | Test de integración |
| Prompts en español, con rol y criterios concretos; sin nombres de modelo hardcodeados; código legible | 1 | Lectura del código |

Aprobado con 6 o más, siempre que los tres primeros criterios estén completos.

## Diferencias con el lab original de DeepLearning.AI

El original es el graded lab "Reflection in a Research Agent" (`GL-M2`).

| Qué se cambió | Por qué |
|---|---|
| Se agregó la celda resuelta `preguntar` antes del primer hueco | El original arrancaba con tres funciones vacías sin mostrar nunca la forma de la llamada. Para alumnos con poca experiencia, el primer hueco tiene que ser "casi copiar". |
| Se agregó la cuarta función `reflexionar_en_bucle` | El original terminaba en una ronda. El bucle es el paso que exige combinar las tres funciones y es donde se ve que es un patrón, no tres llamadas sueltas. |
| `o4-mini` → `MODEL_STRONG`; `gpt-4o` → `MODEL_STRONG`; nunca hardcodeados | Convención del material (ver `README.md` raíz, "Modelos y fecha de caducidad"). El original tenía los nombres dentro de las firmas. |
| Se sacó `temperature=1.0` | Era el default y agregaba un parámetro para explicar sin beneficio. |
| Prompts traducidos y reescritos en español, con límite de palabras (300–400) | Los alumnos tienen que poder leerlos y editarlos. El límite acorta la espera y el costo. |
| `tests.py` reemplaza a `utils_grading.py` | El original solo chequeaba `isinstance(str)` y `len > 100` llamando a la API. Ahora hay un `FakeClient` que registra el prompt y verifica que `revisar_borrador` reciba la crítica, que `model` no esté hardcodeado y que el bucle encadene bien. Todo sin API. Los tests con API quedan marcados `# requiere API` y solo corren si se pasa `client`. |
| `mostrar_caja` escapa el HTML | El `show_output` original interpolaba el texto crudo; un ensayo con `<` rompía la caja. |
| Se agregaron quiz, workbook, extensión opcional y esta guía | Convenciones del material. |
