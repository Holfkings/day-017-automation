# FileFlow — Automatización de archivos por reglas

**FileFlow** es un motor de automatización para carpetas. Define reglas
declarativas una vez y FileFlow se encarga del trabajo repetitivo:
organizar descargas, enrutar facturas entrantes, archivar por fecha,
renombrar lotes o disparar comandos externos cuando aparece un archivo
concretо. Pensado para desplegarse como un servicio discreto en un
servidor o en la máquina de un cliente.

## Características

- **Reglas declarativas** en JSON (o YAML si `pyyaml` está presente).
- **Criterios de coincidencia**: extensión, expresión regular sobre el
  nombre, prefijo MIME, tamaño y antigüedad del archivo. Combinables
  con `match`, `match_any` y `match_all`.
- **Acciones**: mover, copiar, renombrar y ejecutar comandos externos.
- **Plantillas** en destinos y nombres: `{year}`, `{month}`, `{day}`,
  `{date}`, `{timestamp}`, `{name}`, `{ext}`, `{path}`.
- **Modo simulación (`--dry-run`)** para validar antes de tocar nada.
- **Auditoría y reversión**: cada ejecución genera un manifiesto que
  permite deshacerla con `fileflow undo`.
- **Modo vigilancia (`watch`)** con estabilización de archivos para no
  actuar sobre escrituras a medias.
- **Cero dependencias** salvo la biblioteca estándar de Python (>=3.8).

## Instalación

```bash
git clone https://github.com/Holfkings/day-017-automation.git
cd day-017-automation
pip install -e .
```

## Uso rápido

Genera una configuración de ejemplo y ejecútala en seco:

```bash
fileflow init --output mi-config.json --name "Organizar Descargas"
fileflow run mi-config.json --dry-run
fileflow run mi-config.json --manifest ultima-ejecucion.json
```

Vigilar una carpeta de forma continua:

```bash
fileflow watch mi-config.json --interval 30
```

Revertir la última ejecución:

```bash
fileflow undo ultima-ejecucion.json
```

## Formato de configuración

```json
{
  "source": "~/Downloads",
  "recursive": false,
  "rules": [
    {
      "name": "Imágenes a Fotos",
      "match_any": [
        { "extension": [".jpg", ".png", ".webp"] }
      ],
      "action": {
        "type": "move",
        "target": "~/Downloads/Organizado/Imágenes/{year}/{month}",
        "rename": "{date}_{name}"
      }
    }
  ]
}
```

Configuraciones listas para adaptar se incluyen en [`configs/`](configs):
`downloads-organizer.json` y `inbox-processor.json`.

## Ejemplos de clientes reales

- **Orden de Descargas**: clasifica imágenes, documentos, hojas de
  cálculo y vídeos en subcarpetas, y mueve instaladores antiguos a
  reciclaje.
- **Mesа de facturas**: enruta PDF de proveedores a carpetas por año y
  mes, y copia comprobantes a una bandeja de revisión.

## Pruebas

```bash
pip install pytest
pytest
```

La suite cubre el motor de reglas, la ejecución de acciones, la
deduplicación, el manifiesto y la reversión, además de la CLI.

## Licencia

MIT — Holfkings.
