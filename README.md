# Asesor Pedagógico Inteligente — Proyecto Final Profundización I (IA)

**Universidad de Manizales — Facultad de Ciencias e Ingeniería**  
Plataforma web inteligente para la evaluación verificable, retroalimentación argumentada y fortalecimiento de competencias en Inteligencia Artificial (Cohortes 1 y 2).

---

## Funcionalidades implementadas
1. **Entrada de información por laboratorio:** Descripción, objetivos, temáticas de IA, rúbrica versionada y solución del estudiante.
2. **Portafolio académico (Cohortes 1 y 2):** Entregas organizadas por cohorte, estudiante y laboratorio (PDF legible + ZIP o repositorio GitHub + media opcional + versión exacta de rúbrica preservada).
3. **Gestión y validación estricta de rúbricas:** Creación manual o interpretación desde texto/PDF con detección de inconsistencias (ponderaciones deben sumar **100 %**) y versionamiento inmutable.
4. **Evaluación inteligente verificable:** Integración multimodal con **Google Gemini API** (configurable también con Groq, OpenRouter u Ollama local), validación estricta con **Pydantic**, cálculo determinista de la nota (`0.0–5.0`) en el **backend**, verificación objetiva en **Sandbox aislado** (AST + Ruff + Pytest sin acceso a red) y flujo de **revisión, ajuste y aprobación docente** con auditoría.
5. **Informe integrado del aprendizaje:** Consolidado de Cohortes 1 y 2 con evolución gráfica, competencias, brechas, plan personalizado de fortalecimiento y **descarga en PDF**.
6. **Mapa mental interactivo de competencias en IA:** Navegación con zoom/paneo (React Flow), inspector de nodo (laboratorios, evidencias, dominio y profundización) y **descarga en PNG, SVG y JSON**.
7. **Presentación del proyecto y equipo:** Abstract, stack, bitácora de ingeniería aumentada por IA y tarjetas del equipo desarrollador.

---

## 1. Cómo ejecutar en tu computador (Local)

### Backend (FastAPI)
1. Copia el archivo de variables de entorno:
   ```powershell
   Copy-Item backend\.env.example backend\.env
   ```
2. *(Recomendado)* Abre `backend\.env` y pega tu **`GEMINI_API_KEY`** gratuita de [Google AI Studio](https://aistudio.google.com/apikey). *(Si no la pones todavía, la app igual funciona en modo demostración con el sandbox real).*
3. Inicia el servidor backend:
   ```powershell
   cd backend
   .\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
   ```
   Documentación interactiva Swagger disponible en: `http://127.0.0.1:8000/docs`

### Frontend (React + Vite)
En otra terminal:
```powershell
cd frontend
npm run dev
```
Abre: `http://localhost:5173`

### Cuentas de demostración precargadas
- **Estudiante:** `estudiante@umanizales.edu.co` / `Estudiante123!`
- **Docente:** `docente@umanizales.edu.co` / `Docente123!`

### Ejecutar pruebas automatizadas del Backend
```powershell
cd backend
.\.venv\Scripts\pytest.exe -v
```

---

## 2. Personalizar el Equipo Desarrollador
Edita el archivo `frontend/src/data/team.json` con los **nombres reales, roles y enlaces/fotos** de los integrantes de tu equipo (puedes colocar imágenes dentro de `frontend/public/` y referenciarlas como `./foto1.jpg`).

---

## 3. Guía de Despliegue Gratis (GitHub Pages + Render + Supabase)

### Paso A — Base de Datos y Archivos en Supabase (Gratis)
1. Crea un proyecto gratis en [supabase.com](https://supabase.com).
2. En **Project Settings → Database**, copia la cadena de conexión **PostgreSQL (URI)** (`DATABASE_URL`).
3. En **Storage**, crea un bucket privado llamado `submissions`.
4. En **Project Settings → API**, copia `Project URL` (`SUPABASE_URL`) y `service_role` key (`SUPABASE_SERVICE_KEY`).

### Paso B — Backend en Render (Gratis)
1. Sube este proyecto a un repositorio en tu cuenta de **GitHub**.
2. Entra a [render.com](https://render.com) → **New → Blueprint** y conecta tu repositorio (detectará automáticamente `render.yaml`).
3. Rellena las variables de entorno solicitadas:
   - `DATABASE_URL` (de Supabase)
   - `GEMINI_API_KEY` (de Google AI Studio)
   - `SUPABASE_URL` y `SUPABASE_SERVICE_KEY`
   - `CORS_ORIGINS` (la URL de tu GitHub Pages, ej. `https://tu-usuario.github.io`)
4. Al terminar el despliegue, copia la URL pública de tu backend (ej. `https://asesor-pedagogico-ia-api.onrender.com`).

### Paso C — Frontend en GitHub Pages (Automático)
1. En tu repositorio de GitHub ve a **Settings → Pages** y en *Source* elige **GitHub Actions**.
2. Ve a **Settings → Secrets and variables → Actions → Variables** y crea una nueva variable:
   - Name: `VITE_API_URL`
   - Value: `https://tu-backend-en-render.onrender.com` *(sin barra al final)*
3. Haz un `git push` a `main` (o ejecuta manualmente el workflow *Deploy Frontend to GitHub Pages* en la pestaña **Actions**).
4. En ~1 minuto tendrás tu **enlace web público y funcional** listo para la socialización.
