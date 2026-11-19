# Bitácora de Ingeniería de Software Aumentada por IA y Justificación de Modelos

## 1. Herramientas de IA utilizadas en el ciclo de desarrollo
| Etapa del ciclo de vida | Herramienta / Asistente | Aporte principal | Validación y decisiones humanas |
| :--- | :--- | :--- | :--- |
| Análisis de requisitos | Antigravity / Gemini | Descomposición del documento del caso de uso en las 7 funcionalidades obligatorias y 6 condiciones técnicas. | Definición de roles (`student` y `teacher`) y priorización de arquitectura gratuita y mantenible. |
| Diseño de arquitectura | Antigravity / Gemini | Propuesta de separación Frontend estático (GitHub Pages) + Backend FastAPI (Render) + Supabase (PostgreSQL/Storage). | Validación de que ninguna clave API ni cálculo de calificaciones quede expuesto en el cliente. |
| Implementación Backend y Sandbox | Antigravity | Creación de modelos SQLAlchemy, contratos Pydantic v2, análisis AST/Ruff/Pytest y aislamiento de red en sandbox. | Restricción estricta de suma de ponderaciones = 100 %, versionamiento inmutable de rúbricas y cálculo determinista de notas (`0.0–5.0`) solo en backend. |
| Interfaz y Visualización | Antigravity | Construcción de páginas React + Tailwind, gráficas Recharts y mapa mental interactivo con React Flow exportable. | Uso de `HashRouter` y `base: './'` para despliegue limpio en GitHub Pages sin errores 404. |
| Pruebas y depuración | Antigravity / Pytest | Diseño de pruebas unitarias para rúbricas, cálculo de notas, bloqueo de red en sandbox y generación de PDF. | Corrección de bloqueo de sockets en `sitecustomize.py` para no interferir con plugins internos de Pytest. |

---

## 2. Justificación de Modelos de IA, Requisitos, Limitaciones y Costos

| Proveedor | Modelo por defecto | Multimodal | Costo | Requisitos | Limitaciones documentadas |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **Google Gemini API (Principal)** | `gemini-3.5-flash-lite` | Sí (Texto, PDF, imágenes/diagramas) | **Gratis** en Google AI Studio (sin tarjeta) | `GEMINI_API_KEY` | Cuotas por minuto/día; en el nivel gratuito los prompts pueden usarse para mejora del servicio (en producción institucional se migraría a plan pago con privacidad garantizada). |
| **Groq Cloud (Respaldo Nube)** | `llama-3.3-70b-versatile` | No (solo texto/código) | **Gratis** (sin tarjeta) | `OPENAI_COMPAT_API_KEY` | Límite estricto de tokens por minuto (TPM). |
| **OpenRouter (Respaldo Multi-modelo)** | `meta-llama/llama-3.3-70b-instruct:free` | Según modelo | **Gratis** (~50 req/día en modelos `:free`) | `OPENAI_COMPAT_API_KEY` | Disponibilidad variable de proveedores terceros. |
| **Ollama (Local)** | `qwen2.5-coder:7b` | Según modelo | **\$0** (100 % local y privado) | 8–16 GB RAM / GPU local | Requiere máquina propia encendida y accesible para el backend. |

## 3. Arquitectura de Confiabilidad y Seguridad del Sandbox
1. **Salidas estructuradas:** Todo modelo invocado debe cumplir estrictamente el esquema Pydantic `EvaluationAIResponse` (criterios, evidencias concretas, nivel, justificación y competencias).
2. **Nota determinista en Backend:** La función `calculate_weighted_grade()` en `backend/app/services/evaluator.py` calcula $\sum (\text{peso}_i / 100) \times (\text{ratio}_i \times 5.0)$ garantizando reproducibilidad matemática.
3. **Verificación técnica aislada:** `backend/app/services/sandbox.py` ejecuta:
   - Validación de sintaxis Python (`ast.parse`).
   - Análisis estático (`ruff check`).
   - Pruebas unitarias (`pytest`) en un directorio temporal efímero, variables de entorno limpias, límite de tiempo (`SANDBOX_TIMEOUT_SECONDS`), límites de memoria/CPU en Linux (`resource.setrlimit`) y **bloqueo de red por defecto** (`sitecustomize.py` bloqueando `socket.connect` y `getaddrinfo`, más modo opcional Docker `--network none --read-only`).
4. **Supervisión docente y trazabilidad:** Cada evaluación se guarda inicialmente como `pending_review` junto con la versión exacta de la rúbrica, el modelo utilizado, el resultado del sandbox y un log de auditoría (`evaluation_audit_logs`) que registra cada ajuste y aprobación docente.
