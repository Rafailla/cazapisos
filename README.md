# cazapisos

Agente que revisa a diario (y bajo demanda) varias plataformas de venta de pisos
de bancos/servicers, guarda los anuncios nuevos que cumplan los filtros
configurados en Supabase, y avisa por email cuando hay novedades.

La configuración (plataformas, filtros de búsqueda, destinatarios de alertas)
vive en Supabase, no en el código. Ver [CLAUDE.md](CLAUDE.md) para el diseño
completo.

## Estructura

```
scraper/
  main.py            # punto de entrada
  config.py          # carga de variables de entorno
  db.py               # cliente Supabase y acceso a datos
  requirements.txt
```

## Cómo correrlo en local

1. Crea un entorno virtual e instala dependencias:

   ```
   cd scraper
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Copia `.env.example` a `.env` en la raíz del repo y rellena las credenciales
   de Supabase (`SUPABASE_URL`, `SUPABASE_KEY` — la publishable key es
   suficiente, RLS está desactivado a propósito):

   ```
   copy ..\.env.example ..\.env
   ```

3. Ejecuta:

   ```
   python main.py
   ```

   Debería imprimir algo como `5 plataformas activas, 2 perfiles de filtro
   activos` sin errores.

## Estado

Este es el scaffolding inicial: valida la conexión a Supabase y expone las
funciones de acceso a datos (`get_active_platforms`, `get_active_filters`,
`get_active_recipients`). Todavía no hay lógica de scraping ni de envío de
email — eso llega en prompts posteriores.
