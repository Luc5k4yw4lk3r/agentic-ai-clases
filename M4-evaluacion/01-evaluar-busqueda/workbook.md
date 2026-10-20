# Evaluar un componente: ¿de dónde saca las fuentes el agente?

Material de acompañamiento del lab 01 de M4. Leelo antes de abrir el notebook, tenelo al
lado mientras lo resolvés y volvé a la sección 5 al terminar.

## Antes de empezar (quiz de 5 preguntas)

Respondé antes de leer la teoría. Las respuestas están en el notebook del profesor.

1. **(Repaso M3)** En *function calling*, ¿quién ejecuta la tool cuando el modelo pide llamarla?
   a) El modelo, dentro de OpenAI. b) Tu código Python. c) El navegador.
2. **(Repaso M3)** ¿Qué limita `max_turns=5` en `aisuite`?
   a) La cantidad de resultados que devuelve cada tool. b) La cantidad de vueltas del loop
   modelo → tool → modelo. c) La cantidad de reintentos si la API falla.
3. **(Nuevo)** ¿Por qué conviene evaluar solo el paso de búsqueda en vez de todo el pipeline?
   a) Porque el resto del pipeline no tiene errores. b) Porque es más barato y la señal no se
   mezcla con la aleatoriedad de los pasos siguientes. c) Porque los LLM no se pueden evaluar.
4. **(Nuevo)** "Porcentaje de URLs que caen en dominios confiables" es una evaluación...
   a) Subjetiva, sin ground truth. b) Objetiva, con ground truth por ejemplo.
   c) Objetiva, pero sin ground truth.
5. **(Base Python)** ¿Qué devuelve `"mit.edu" in "summit.edu"`?
   a) `False`, porque son dominios distintos. b) `True`, porque `in` busca substrings.
   c) Da error porque no son listas.

## 1. Teoría breve

### Para qué: encontrar el paso que falla sin correr todo

En M3 armaste un agente de investigación con tres pasos: buscar en la web, reflexionar,
publicar un reporte en HTML. Cuando el reporte sale flojo, la pregunta es *qué paso* falló.
Si la única forma de saberlo es correr el flujo completo y leer el reporte, cada intento
cuesta varias llamadas al modelo, varios minutos y una lectura atenta. Y aunque el paso de
búsqueda mejore, los pasos 2 y 3 son aleatorios: la mejora puede quedar tapada.

### Por qué así: evaluación a nivel de componente

La alternativa es medir **un componente** con una métrica que se calcule con código. Para el
paso de búsqueda la métrica es simple: de todas las URLs que trajo el agente, ¿qué porcentaje
pertenece a dominios que consideramos confiables *para ese tema*?

Esta métrica tiene dos propiedades que la hacen barata y útil:

- Es **objetiva**: la calcula código, no un LLM ni una persona. Corre en milisegundos.
- Tiene **ground truth por ejemplo**: para cada tema definimos de antemano qué dominios cuentan
  como confiables. No es "¿está bien el reporte?", es "¿la URL termina en `arxiv.org`?".

Los dos ejes de evaluación que vio el curso:

| | Con ground truth por ejemplo | Sin ground truth |
|---|---|---|
| **Objetiva (código)** | % de URLs en dominios confiables **(este lab)** | cantidad de URLs, largo del texto |
| **Subjetiva (LLM como juez)** | comparar con un reporte modelo | "¿qué tan claro es el texto?" (rúbrica) |

Las evaluaciones del cuadrante superior izquierdo son las primeras que conviene armar: son
baratas, reproducibles y detectan regresiones. Las de los otros cuadrantes se agregan después.

### Ejemplo práctico

Tema: "agujeros negros". Dominios confiables: `arxiv.org`, `nasa.gov`, `nature.com`. El
agente devuelve 5 URLs; 3 son de esos dominios. Ratio = 0,6. Umbral = 0,4. Resultado: PASS.

Cambiás el prompt del agente para que "busque fuentes más variadas". Volvés a correr: 5 URLs,
1 confiable. Ratio = 0,2. FAIL. Detectaste la regresión en segundos y sin leer nada.

### Lo que el material original hacía mal (y vas a corregir)

El notebook original de DeepLearning.AI tenía la idea correcta pero tres defectos en el código:

1. **Comparación por substring.** Usaba `any(td in domain for td in TOP_DOMAINS)`. Como `in`
   busca substrings, `"mit.edu" in "summit.edu"` da `True`. Cualquier dominio que *contenga*
   un dominio confiable pasaba: `notnature.com`, `arxiv.org.evil.com`.
2. **URLs duplicadas.** Si el modelo citaba la misma URL dos veces, contaba dos. El total y el
   ratio quedaban inflados.
3. **Puntuación pegada.** `https://nature.com/x.` (con punto final) quedaba con el punto. No
   afecta al dominio pero sí al detalle que ve el usuario.

Además, el helper `print_html` escapaba el HTML, así que las etiquetas `<h3>` aparecían como
texto en pantalla. Nuestro `utils.mostrar_html` no escapa; para texto plano hay un
`utils.mostrar_texto` aparte.

## 2. Ejemplo resuelto

El componente a evaluar ya viene escrito. Fijate que no escribe ni reflexiona: solo busca y
lista. Eso es lo que lo hace evaluable por separado.

```python
def buscar_referencias(tema: str, model: str = AI_CHEAP) -> str:
    hoy = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""Sos una función de investigación. Tenés tres tools: ...
Tarea: encontrá entre 3 y 5 referencias confiables sobre el tema "{tema}".
Devolvé una lista en Markdown con título, fuente y la URL completa.
Hoy es {hoy}."""
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=[research_tools.arxiv_search_tool, research_tools.tavily_search_tool,
               research_tools.wikipedia_search_tool],
        tool_choice="auto",
        max_turns=5,
    )
    return response.choices[0].message.content or ""
```

Salida típica (*ejemplo ilustrativo, varía entre corridas*):

```
- **Black hole imaging with the EHT** (arXiv): https://arxiv.org/abs/2311.01234
- **Black hole** (Wikipedia): https://en.wikipedia.org/wiki/Black_hole
- **NASA: What is a black hole?**: https://science.nasa.gov/universe/black-holes/
- **Sagittarius A* news** (blog): https://www.space.com/sagittarius-a-star-news
```

Aplicando la evaluación con confiables `{arxiv.org, wikipedia.org, nasa.gov}` y umbral 0,4:

```
Estado: PASS — 3 de 4 URLs en dominios confiables (ratio 75%, umbral 40%).
URL                                                 Dominio               Resultado
https://arxiv.org/abs/2311.01234                    arxiv.org             confiable
https://en.wikipedia.org/wiki/Black_hole            en.wikipedia.org      confiable
https://science.nasa.gov/universe/black-holes/      science.nasa.gov      confiable
https://www.space.com/sagittarius-a-star-news       space.com             no confiable
```

Los dos subdominios (`en.wikipedia.org`, `science.nasa.gov`) cuentan como confiables porque
terminan en `.wikipedia.org` y `.nasa.gov`. `space.com` no está en la lista: no confiable.

## 3. Práctica graduada

### Nivel base

Cada ejercicio corresponde a un hueco del notebook. Están en orden de dificultad: el primero
es casi copiar la celda de ejemplo; el último combina las cuatro funciones anteriores.

**3.1 `extraer_urls(texto) -> list[str]`** (tres huecos). Encontrá las URLs con la regex de la
celda de ejemplo, sacales la puntuación final con `rstrip(".,;:!?")` y eliminá duplicados
conservando el orden (usá una lista y `if url not in urls`; un `set` desordena).

**3.2 `dominio_de(url) -> str`** (dos huecos). `urlparse(url).netloc.lower()` te da el host.
Si empieza con `www.`, sacale esas cuatro letras. Nada más: `en.wikipedia.org` queda igual.

**3.3 `es_dominio_confiable(dominio, confiables) -> bool`** (un hueco). Dentro del `for`,
devolvé `True` si `dominio == confiable` o si `dominio.endswith("." + confiable)`. El punto
antes del dominio es lo que evita el bug del original.

**3.4 `evaluar_referencias(texto, confiables, umbral=0.4) -> dict`** (dos huecos). Para cada
URL: dominio y si es confiable. Después el ratio (cuidado con dividir por cero) y `aprobado`,
que requiere `total > 0` **y** `ratio >= umbral`.

Cuando termines 3.1 a 3.4, corré la celda `run_all(...)`: tiene que decir `24/24 tests pasaron`.
Si algo falla, el nombre del test te dice qué función revisar.

**3.5 `correr_evaluacion(casos, repeticiones=1) -> DataFrame`** (dos huecos). Para cada caso y
repetición: llamá a `buscar_referencias`, evaluá, y agregá un dict a `filas` con las claves
`tema`, `repeticion`, `total`, `confiables`, `ratio`, `aprobado`. Esta sí llama a la API:
5 casos son 5 llamadas al modelo más sus tools, 1 a 2 minutos.

### Extensión opcional

Sin huecos, consignas abiertas. Están al final del notebook ("Si te sobra tiempo"):

1. **Varianza.** `correr_evaluacion(CASOS, repeticiones=3)` y
   `df.groupby("tema")[["ratio", "aprobado"]].agg(["mean", "std"])`. ¿Qué temas cambian de
   PASS a FAIL entre corridas? ¿Cuántas repeticiones necesitarías para confiar en el resultado?
2. **Umbral.** Sin volver a llamar a la API, recalculá `aprobado` para 0.3, 0.5 y 0.7 sobre el
   mismo `df`. ¿Cuál elegirías? ¿Qué pasa con la tasa de aprobados en cada caso?
3. **Un tema nuevo.** Agregá un sexto caso con sus dominios confiables. Anotá cuánto te costó
   decidir la lista: ese es el costo real del ground truth.
4. **Cambiar el componente.** Modificá el prompt de `buscar_referencias` ("Priorizá fuentes
   académicas e institucionales") y volvé a correr. Ahora tenés un número para comparar.
5. **Paréntesis en la URL.** La regex corta en `)`, así que
   `https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)` pierde el `)`.
   Proponé un arreglo que no rompa `(ver https://arxiv.org/abs/1)`.

## 4. Troubleshooting de más a menos frecuente

| Síntoma | Causa | Arreglo |
|---|---|---|
| `run_all` dice `FALTA ... NotImplementedError` | La función todavía tiene el placeholder | Completá el hueco y volvé a ejecutar la celda de la función **antes** de `run_all` |
| `test_confiable_no_confunde_substring` falla | Usaste `in` o `endswith(confiable)` sin el punto | `dominio == confiable or dominio.endswith("." + confiable)` |
| `test_extraer_urls_sin_duplicados_y_en_orden` falla | Usaste `set(...)` para deduplicar | Un set no conserva el orden. Lista + `if url not in urls` |
| `test_extraer_urls_puntuacion_pegada` falla | Falta el `rstrip` | `url.rstrip(".,;:!?")` en el paso 2 |
| `test_evaluar_sin_urls...` falla con `ZeroDivisionError` | Dividiste sin chequear `total == 0` | `if total == 0: ratio = 0.0` |
| `aprobado` es `True` con texto sin URLs y umbral 0 | Falta la condición `total > 0` | `aprobado = total > 0 and ratio >= umbral` |
| `buscar_referencias` devuelve `[Error en la búsqueda: ...]` | Falló el modelo o una tool (red, key, cuota) | Leé el mensaje; si es Tavily, revisá `TAVILY_API_KEY` o dejá que use el fallback a Wikipedia |
| Las referencias son de 2023 aunque pediste "recientes" | No llegó la fecha al prompt | Verificá que `hoy` esté en el f-string; sin fecha el modelo asume su fecha de entrenamiento |
| `utils.mostrar_html` muestra `<h3>` como texto | Estás usando el `print_html` del original o `mostrar_texto` | Usá `utils.mostrar_html` para HTML y `utils.mostrar_texto` para texto plano |

## 5. Para cerrar

### Tres preguntas de reflexión

1. La evaluación dice PASS para un tema pero el reporte final es malo. ¿Qué te dice eso sobre
   dónde está el problema? ¿Qué otra evaluación de componente agregarías?
2. Un dominio confiable para "ensayos clínicos" (`nih.gov`) no lo es para "historia del jazz".
   ¿Qué implica eso para mantener el gold standard cuando el agente se usa con temas nuevos?
3. Corriste 3 repeticiones y un tema aprueba 2 de 3 veces. ¿Es PASS o FAIL? ¿Qué regla
   escribirías para decidirlo?

### Checklist de autoevaluación

- [ ] Puedo explicar con un ejemplo por qué `"mit.edu" in "summit.edu"` era un bug.
- [ ] Sé qué diferencia a una evaluación objetiva de una subjetiva, y a una con ground truth
      por ejemplo de una sin él.
- [ ] Mis cuatro funciones puras pasan los 24 tests.
- [ ] Corrí `correr_evaluacion` sobre los 5 casos y puedo leer la tabla: cuántos aprobaron y
      cuál fue el ratio promedio.
- [ ] Puedo nombrar al menos un cambio en el prompt de `buscar_referencias` y decir cómo
      mediría si mejoró la búsqueda.
