# ⚡ PublishFlow

> **AI-Powered Multi-Platform Content Generator & Auto-Publisher**

**PublishFlow** es un motor de automatización impulsado por la **API de Gemini** y **Streamlit** que permite crear y publicar contenido para múltiples redes sociales a partir de una **URL (sitio web, perfil de Instagram, etc.)** o un tema general.

---

### 🌟 Características Principales
* 🌐 **Análisis Automático de Fuentes:** Introduce la dirección web o perfil de tu marca y la IA extraerá los puntos clave para generar el contenido.
* 📲 **Formato Multired:** Genera publicaciones optimizadas para **Instagram, LinkedIn, X (Twitter) y Facebook** de forma simultánea.
* ✍️ **Copywriting Inteligente:** Redacción con la API de Gemini (`gemini-2.5-flash`), incluyendo tono adaptado, emojis y hashtags específicos.
* 🖼️ **Generación de Imágenes con IA:** Ilustraciones digitales a medida generadas en tiempo real para acompañar cada post.
* 🎛️ **Dashboard Interactivo:** Revisa, edita las publicaciones y descarga el material visual desde la interfaz de Streamlit.
* 🔄 **Automatización Gratuita:** Programación de posts recurrentes sin servidor usando **GitHub Actions**.

---

### 🛠️ Estructura del Proyecto

```text
PublishFlow/
├── .github/
│   └── workflows/
│       └── auto_publish.yml    # Tarea automática diaria con GitHub Actions
├── app.py                      # Interfaz visual interactiva en Streamlit
├── publisher.py                # Lógica del motor (Gemini API + Scraping + Publicación)
├── requirements.txt            # Dependencias del proyecto
└── README.md                   # Documentación principal
