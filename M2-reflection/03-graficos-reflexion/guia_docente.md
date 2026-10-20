# Guía docente — Gráficos con reflexión multimodal: el modelo mira lo que dibujó

## Ficha

| | |
|---|---|
| **Duración** | 90 min dentro de la sesión 2 del módulo (ver `M2-reflection/README.md`) |
| **Prerrequisitos** | Labs 01 y 02 (patrón de reflexión, feedback externo, pedir JSON y validar). Haber visto una regex alguna vez. Saber qué hace `try/except`. Matplotlib básico no es requisito: el código lo escribe el modelo. |
| **Keys** | `OPENAI_API_KEY`. No usa Tavily. |
| **Archivos** | `notebook_alumno.ipynb`, `workbook.md`, `utils.py`, `data/coffee_sales.csv` (3.636 filas). Los PNG se generan en `data/` y se borran al inicio de cada corrida. |
| **Costo estimado** | Por alumno, una pasada: 1 (V1 guía) + 1 (reflexión con imagen) + 2 (workflow bebidas) = **4 llamadas**. Las dos de reflexión llevan una imagen (~1.000 tokens extra cada una) y son a `MODEL_STRONG`. Barato. Si hacen la extensión de dos rondas o la de darle los datos, +1 o +2 por corrida. |
| **Se evalúa** | No (ungraded en el original). Entregable sugerido al final. |

## Secuencia sugerida (90 min)

| Minuto | Qué pasa | Quién |
|---|---|---|
| 0–5 | Quiz. Las 1 y 2 repasan el lab 02; la 5 (`exec` con namespace) anticipa el hueco 2. | Todos |
| 5–15 | Teoría: el crítico necesita **ver** el resultado. Mostrar dos gráficos (uno con etiquetas pisadas) y preguntar qué le dirían. Dibujar el flujo de cuatro piezas y la tabla "cómo falla cada una". | Profesor |
| 15–25 | Setup y datos. Correr la celda de conteo por trimestre. **Dejar que descubran solos** que Q1 2024 tiene solo marzo (preguntar "¿qué meses tiene cada Q1?"). Plantear la pregunta: ¿la reflexión lo va a notar? Que cada uno anote su apuesta. | Todos |
| 25–30 | Celda resuelta `generar_codigo_grafico`. Mostrar `describir_columnas(df)` y por qué se genera desde el dato. Ejecutar; leer la respuesta V1 en voz alta: ahí están las etiquetas. | Profesor |
| 30–40 | Hueco 1, `extraer_codigo`. Correr la celda de prueba con el caso sin etiquetas. Si alguien escribió `if match:` y devolvió `None`, mostrar qué pasaría tres celdas después (el PNG viejo). | Alumnos |
| 40–50 | Hueco 2, `ejecutar_codigo`. Correr el snippet roto. Explicar `traceback.format_exc()`. Mencionar el sandbox sin profundizar (M3). Ejecutar el V1 real y mostrar el PNG. | Alumnos |
| 50–65 | Huecos 3–5, `reflexionar_sobre_grafico`. Antes, escribir en el pizarrón la estructura del `content` como lista. Ejecutar; leer la crítica. **Volver a la apuesta:** ¿mencionó lo del Q1? Casi nunca. Discutir por qué. | Alumnos, luego todos |
| 65–80 | Huecos 6–7, `correr_workflow`. Correr con la instrucción de bebidas por franja horaria. Comparar V1 y V2 en pantalla. | Alumnos |
| 80–90 | Extensión 1 en vivo si da el tiempo: pegar `conteo.to_markdown()` en el prompt del crítico y volver a correr. Suele detectar el problema. Cierre: "la reflexión ve lo que le mostrás". | Profesor |

## Qué hacer en vivo vs. qué dejan corriendo los alumnos

**En vivo (profesor):**
- La tabla de conteos por trimestre y la pregunta de la apuesta. Es el hilo
  pedagógico del lab.
- La estructura del mensaje multimodal en el pizarrón antes del hueco 3.
- La extensión 1 (darle los datos al crítico) como demostración de cierre, porque
  resuelve la apuesta y deja la moraleja.

**Los alumnos solos:**
- Los tres huecos de parseo/ejecución. Son cortos y la celda de prueba les dice si
  anduvo.
- El workflow con la instrucción de bebidas. Que anoten qué cambió entre V1 y V2.

## Dónde se traban (y qué decir)

1. **`if match:` sin `else`.** El reflejo es copiar el patrón del original: devolver
   `None` o seguir adelante. Síntoma tardío: `TypeError: expected string` en `exec` o
   un PNG viejo. Decir: "si el modelo no mandó código, ¿qué vas a ejecutar? Fallá acá,
   con un mensaje que te diga qué pasó".
2. **`traceback.format_exc()` fuera del `except`.** Devuelve `NoneType: None`. Decir:
   "solo tiene sentido mientras estás manejando la excepción".
3. **`content` como string.** Concatenan el prompt con la data URL en un solo string.
   La API devuelve 400 o el modelo "no ve" la imagen y critica a ciegas. Decir:
   "cuando hay más de un tipo de contenido, `content` es una lista de partes".
4. **Olvidan `{"url": ...}` dentro de `image_url`.** Ponen la data URL directo como
   valor de `image_url`. Error 400 con mensaje poco claro. Mostrar la estructura
   anidada en pantalla.
5. **El código V2 guarda en `chart_v1.png`.** El modelo copió la ruta del código
   original. El prompt ya pide la ruta V2 explícita, pero pasa. Síntoma: V1 y V2
   "iguales". Decir: "mirá la línea `savefig` de la V2".
6. **Esperan que la reflexión detecte lo del Q1.** Se frustran cuando la crítica es
   solo de forma. Es el momento clave: "¿qué vio el modelo? El gráfico y el código.
   ¿Dónde está la información de que falta enero y febrero? En los datos, que no vio".
7. **`plt.show()` en el código generado.** Con backend `Agg` no abre ventana, pero a
   veces emite un warning. Agregar al prompt si molesta.
8. **Rutas relativas.** Si abren Jupyter desde otra carpeta, `data/` no existe y
   `savefig` falla. Pedir que abran desde la carpeta del lab o desde la raíz del
   material con `find_dotenv(usecwd=True)` (ya está).

## Respuestas del quiz de apertura

1. **b.** Feedback externo: el resultado de la ejecución.
2. **b.** Validación explícita. Enlazar con el bug del original en este lab.
3. **b.** El render depende de datos y layout; el código no lo revela. Ejemplo: etiquetas superpuestas.
4. **b.** Delimitar para extraer y para fallar fuerte cuando no hay código.
5. **a.** Namespace controlado. Agregar que `exec` escribe ahí las variables que el código crea; se puede inspeccionar después.

## Soluciones de la extensión opcional (esbozo)

- **Darle los datos al crítico.** En el prompt de `reflexionar_sobre_grafico`, antes
  de "FORMATO DE RESPUESTA": `"Resumen de los datos por año y trimestre:\n{conteo.to_markdown(index=False)}"`.
  Agregar `conteo` como parámetro o calcularlo adentro desde `df`. Con eso, `gpt-4.1`
  casi siempre señala que Q1 2024 solo tiene marzo y la V2 suele agregar una nota al
  título o comparar marzo vs marzo. Moraleja: el diseño del agente incluye decidir qué
  contexto recibe el crítico.
- **Reflexión sobre el error.** `reflexionar_sobre_grafico(ruta_png=None, ...)`: si
  es `None`, `content` tiene solo la parte de texto, y el prompt dice "El código falló
  con este error:\n{traceback}" en lugar de "mirá el gráfico". En `correr_workflow`,
  reemplazar el `return` temprano por esa llamada. Discutir el tope de reintentos.
- **Dos rondas.** Llamar a `reflexionar_sobre_grafico(ruta_v2, ..., codigo_v2, ruta_v3, ...)`
  y ejecutar. Lo habitual: la V3 cambia colores o tipografía sin mejorar de fondo.
  Buen ejemplo de rendimientos decrecientes de la reflexión.
- **Rúbrica visual.** Pedir el JSON con `{"feedback": ..., "legibilidad": N, "fidelidad": N, "honestidad": N}`.
  Validar que los tres sean enteros entre 1 y 5. Graficar la evolución V1→V2→V3.
- **Modelo barato para criticar.** `gpt-4.1-mini` ve imágenes. La crítica suele ser
  más genérica ("mejorar colores") y a veces no respeta el formato de dos partes, lo
  que hace saltar las validaciones. Buen ejemplo de para qué sirven.

## Rúbrica

El lab no se evalúa con nota. Entregable sugerido: el notebook corrido con el
workflow de bebidas por franja horaria, las imágenes V1 y V2 visibles, y una celda
markdown con (a) qué criticó el modelo, (b) si la V2 lo resolvió, (c) la respuesta a
la pregunta del Q1 2024 y qué habría que darle al crítico para que lo detecte.

## Diferencias con el lab original de DeepLearning.AI

El original es el ungraded lab "Chart Generation" (`M2_UGL_1`).

| Qué se cambió | Por qué |
|---|---|
| `extraer_codigo` levanta `ValueError` si no hay etiquetas | El original hacía `if match: ... exec(...)` y después mostraba el PNG sin verificar que se hubiera regenerado. Cuando el modelo olvidaba las etiquetas, el notebook mostraba el gráfico de la corrida anterior como si fuera el nuevo. |
| `ejecutar_codigo` captura la excepción y devuelve el traceback como string | El original llamaba `exec` a secas: un error del código generado cortaba el notebook. Ahora el error es un dato que el flujo puede usar. |
| Descripción de columnas generada desde el DataFrame real (`utils.describir_columnas`) | El prompt original decía `date (M/D/YY)` cuando el CSV trae `YYYY-MM-DD`, y la descripción no coincidía con las columnas derivadas por `load_and_prepare_data`. El modelo generaba código con parseos de fecha incorrectos. |
| `cargar_datos` parsea la fecha con `format="%Y-%m-%d"` y `errors="raise"` | El original usaba `errors="coerce"`: una fecha mal parseada se convertía en `NaT` en silencio y desaparecía de los conteos. |
| Solo SDK `openai`; se eliminó `anthropic` y la rama `if "claude" in model` | El material usa un solo proveedor. El original tenía dos clientes, dos helpers de imagen y un `get_response` con ramas por nombre de modelo; nada de eso aporta al concepto. |
| `chat.completions` con `content` como lista (`text` + `image_url`) en vez de `responses.create` | Es la misma API que usaron en los labs 01 y 02 (aisuite la imita); el mensaje multimodal se arma a mano para que vean la estructura. |
| `o4-mini` → `MODEL_STRONG`; `gpt-4o-mini` → `MODEL_CHEAP` | Convención del material. |
| Se borran los PNG al inicio (`utils.borrar_pngs`) | Elimina de raíz el síntoma del bug 1: nunca puede mostrarse una imagen vieja. |
| Celda de conteo por año y trimestre y la "apuesta" sobre el Q1 2024 | El dataset arranca en marzo de 2024, así que la comparación "Q1 vs Q1" del original era engañosa y el lab no lo mencionaba. Ahora es el hilo pedagógico: qué puede y qué no puede ver el crítico. |
| `extraer_json` busca solo antes de `<execute_python>` | El fallback del original (`re.search(r"\{.*?\}", content)`) podía agarrar un diccionario del código Python en vez del JSON de feedback. |
| Backend `Agg` explícito, `dpi=150` en vez de 300 | Sin ventanas en servidores sin display; archivos más chicos para la data URL (menos tokens). |
| Imágenes de la carpeta original (`pipeline.png`, `M2-UGL-2.png`, charts de ejemplo) no se copiaron | Son material con marca o salidas de corridas ajenas. El diagrama está en Mermaid. |
| Textos en español, quiz, workbook, extensión y esta guía | Convenciones del material. |
