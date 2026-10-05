# 📣 PublishFlow — Agencia de marketing con IA

PublishFlow es una aplicación web hecha con **Streamlit** y **Gemini** que funciona como una agencia de marketing completa. Le das un encargo (qué quieres promocionar, a quién y en qué redes) y un equipo de seis especialistas prepara la estrategia, los textos, las imágenes y el guion de vídeo, publica en las redes conectadas y deja listo para descargar el contenido de las que se suben a mano.

Está pensada para promocionar las webs propias **AdeskCharts** (plataforma de trading con IA) y **SoundSnip Studio PRO** (herramientas de audio para DJs y productores), aunque admite cualquier otra marca.

---

## 👥 El equipo

| Empleado | Puesto | Qué hace | Color |
|---|---|---|---|
| **Elena Navarro Ruiz** | Directora de Estrategia | Analiza el producto y decide mercados, público, redes, mejores horarios y plan de 7 días. | Lila |
| **Marcos Vidal Herrera** | Copywriter Senior | Escribe los textos de cada red respetando su límite de caracteres, con variante B, título y hashtags. En blogs y newsletter escribe artículos de 300 a 500 palabras. | Cian |
| **Lucía Ortega Blanco** | Directora Creativa | Adapta las fotos al formato de cada red con el color de marca, el logo y un gancho, y escribe el guion de un vídeo vertical de 30 segundos. | Rosa |
| **Daniel Soto Morales** | Community Manager | Publica con un clic en las redes conectadas y prepara las descargas del resto. | Ámbar |
| **Sara Méndez Castillo** | Analista de Resultados | Registra lo publicado, genera enlaces con seguimiento (UTM) por red y redacta informes a partir de las métricas. | Verde |
| **Javier Romero Gil** | Ojeador de Talento | Busca creadores y profesionales para colaborar como afiliados o embajadores, los puntúa y redacta el primer mensaje. | Azul |

Las fotos del equipo son retratos generados con IA de personas que no existen.

---

## 🗂️ Pestañas de la aplicación

1. **🏢 Oficina**: tarjetas del equipo con foto, cargo, función y estado de trabajo, y resumen de la campaña en curso.
2. **📋 Nuevo encargo**: el briefing. Marca, descripción, enlace de destino, objetivo, oferta, mercado, público, fotos o capturas, logo, color de marca y redes de la campaña.
3. **📦 Entregas**: el trabajo de cada especialista, firmado con su foto.
   - Plan de campaña de Elena (público, mercados, redes con horarios y frecuencia, plan de 7 días).
   - Textos de Marcos, todos editables, con contador de caracteres.
   - Piezas visuales y guion de vídeo de Lucía.
4. **📤 Publicación**: cada red con su imagen, texto listo para copiar y mejor horario.
   - Redes conectadas: botón **Publicar**.
   - Resto: botones para **descargar imagen y texto** y **marcar como publicada**.
   - Botón **Descargar todo (ZIP)** con todas las imágenes, textos, guion y estrategia.
5. **📈 Resultados**: registro de publicaciones, enlaces con seguimiento por red, tabla de métricas (alcance, clics, visitas, suscriptores) e informe de Sara.
6. **🤝 Talento**: buscador de colaboradores.
   - Fuentes: YouTube (API oficial), Bluesky (API pública) y un agente Gemini con Google para Instagram, TikTok y webs.
   - Filtros por nicho, tamaño de audiencia, país e idioma.
   - Puntuación de afinidad del 1 al 10, lista de seguimiento (Encontrado → Contactado → Respondió → Colaborando), descarga en CSV y mensaje de contacto personalizado.
7. **🔌 Conexiones**: panel para conectar cada red. Desplegable con estado, guía paso a paso de qué datos hacen falta y dónde conseguirlos, botón **Probar y guardar** y tabla con el estado de todas las redes.

---

## 🌐 Redes

### Publicación directa (13)

| Red | Datos que pide |
|---|---|
| Telegram | Token del bot y canal |
| Bluesky | Usuario y contraseña de app |
| Facebook | ID y token de la página |
| Instagram | ID de la cuenta profesional (necesita Facebook conectado) |
| Threads | ID de usuario y token (necesita Facebook conectado) |
| LinkedIn | Token de acceso (perfil personal; las páginas de empresa requieren aprobación aparte) |
| Pinterest | Token y ID del tablero |
| Discord | URL del webhook |
| Mastodon | Servidor y token |
| Blogger (Google) | ID del blog, Client ID, Client secret y refresh token |
| WordPress | Dirección de la web, usuario y contraseña de aplicación |
| Dev.to | Clave de API |
| Newsletter (Brevo) | Clave de API, remitente verificado e ID de la lista |

Instagram y Threads solo aceptan imágenes alojadas en internet, por eso la app las sube primero como foto oculta a la página de Facebook.

### Subida manual con descarga (9)

| Red | Motivo |
|---|---|
| X (Twitter) | Su API para publicar es de pago |
| TikTok | Exige auditoría para publicar por API |
| YouTube Shorts | Necesita vídeo; la agencia entrega imagen y guion |
| WhatsApp | Los canales no tienen API |
| Reddit | Las comunidades castigan la autopromoción automática |
| Tumblr | Conexión más compleja, pendiente |
| Medium | Ya no da acceso nuevo a su API |
| Hashnode | Pendiente |
| Perfil de Empresa de Google | Requiere aprobación y suele exigir atención presencial |

---

## 🛠️ Estructura del proyecto

```
publishflow/
├── .streamlit/
│   └── config.toml              # Tema oscuro neón morado
├── fotos/                       # Fotos del equipo (también vale assets/ o la raíz)
│   ├── estrategia.jpg           # Elena
│   ├── copy.jpg                 # Marcos
│   ├── creativa.jpg             # Lucía
│   ├── community.jpg            # Daniel
│   ├── analista.jpg             # Sara
│   └── talento.jpg              # Javier
├── app.py                       # Interfaz: pestañas, diseño y flujo de trabajo
├── motor.py                     # Equipo, IA, piezas visuales, conectores y descargas
├── buscador_colaboradores.py    # Buscador de colaboradores (pestaña Talento)
├── requirements.txt
└── README.md
```

### requirements.txt

```
streamlit
google-genai
requests
beautifulsoup4
pillow
pandas
markdown
```

### .streamlit/config.toml

```toml
[theme]
base = "dark"
primaryColor = "#C084FC"
backgroundColor = "#0B0614"
secondaryBackgroundColor = "#1A1030"
textColor = "#EDE7FF"
font = "sans serif"
```

---

## 🔑 Secrets de Streamlit

Se configuran en Streamlit Cloud: tu app → **⋮ → Settings → Secrets**.

**Imprescindible:**

```toml
GEMINI_API_KEY = "..."
```

**Recomendado (protege la app con contraseña):**

```toml
APP_PASSWORD = "..."
```

**Opcional:**

```toml
YOUTUBE_API_KEY = "..."   # Para buscar canales en la pestaña Talento
```

**Conexiones de redes:** se pueden rellenar desde la pestaña 🔌 Conexiones. Lo que se conecta ahí se pierde al reiniciar la app, así que el propio panel genera el bloque de texto para pegarlo en los Secrets y dejarlo guardado. Las claves posibles son:

```toml
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
BLUESKY_HANDLE, BLUESKY_APP_PASSWORD
FB_PAGE_ID, FB_PAGE_TOKEN, FB_GRAPH_VERSION
IG_USER_ID
THREADS_USER_ID, THREADS_TOKEN
LINKEDIN_TOKEN, LINKEDIN_URN, LINKEDIN_VERSION
PINTEREST_TOKEN, PINTEREST_BOARD_ID
DISCORD_WEBHOOK_URL
MASTODON_URL, MASTODON_TOKEN
BLOGGER_BLOG_ID, BLOGGER_CLIENT_ID, BLOGGER_CLIENT_SECRET, BLOGGER_REFRESH_TOKEN
WP_URL, WP_USER, WP_APP_PASSWORD
DEVTO_API_KEY
BREVO_API_KEY, BREVO_SENDER_NAME, BREVO_SENDER_EMAIL, BREVO_LIST_ID
```

---

## ▶️ Cómo se usa

1. **Conecta tus redes** en 🔌 Conexiones (empezar por Telegram, que se hace en unos minutos).
2. **Haz un encargo** en 📋 Nuevo encargo: elige marca, describe el producto, sube capturas y logo, y marca las redes.
3. Pulsa **Encargar campaña al equipo** y espera a que cada especialista termine.
4. **Revisa y edita** el trabajo en 📦 Entregas.
5. **Publica** en 📤 Publicación a la hora que recomienda Elena; descarga lo que se sube a mano.
6. **Mide** en 📈 Resultados: apunta las métricas y pide el informe a Sara.
7. **Busca colaboradores** en 🤝 Talento y envíales el mensaje tú mismo, en tu nombre o el de tu marca.

---

## 🎨 Diseño

- Tema oscuro con neón morado, fondo con focos de luz lila, rosa y cian.
- Cada empleado tiene su color: borde, brillo y halo de la foto, cargo y firma.
- Pestañas grandes con forma de carpeta; cada una se ilumina en su color.
- Botones con degradado violeta-fucsia, campos de texto con brillo cian al escribir.
- Adaptado a móvil.

---

## ⚠️ Limitaciones actuales

- **Sin base de datos**: la campaña, el registro y las conexiones hechas desde el panel se pierden al recargar la página. Conviene descargar el ZIP y guardar las conexiones en los Secrets.
- **Sin programación automática**: se publica con un clic a la hora recomendada; Streamlit Cloud no puede publicar solo a una hora concreta.
- **Conexiones no probadas con cuentas reales**: cada red se prueba al conectarla con el botón *Probar y guardar*.
- **Resultados del agente IA en Talento**: pueden contener errores; hay que abrir el enlace y comprobar la cuenta antes de contactar.
- Los mensajes a creadores se envían a mano: automatizar mensajes directos va contra las normas de las redes.

---

## 🚀 Próximos pasos

1. **Base de datos (Supabase)** para guardar campañas, conexiones, registro y colaboradores.
2. **Programación automática** con GitHub Actions para publicar a la hora recomendada.
3. **Vídeo vertical automático** a partir de las fotos (MoviePy) para Reels, Shorts y TikTok.
4. **Aprobación desde el móvil por Telegram** antes de publicar.
5. **Métricas automáticas** desde las APIs de cada red para los informes de Sara.
6. **De GitHub a publicación**: posts de "novedad" automáticos cuando se actualizan AdeskCharts o SoundSnip.
