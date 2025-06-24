from jinja2 import Environment, FileSystemLoader

# Ruta a la carpeta que contiene tu plantilla
template_dir = r"C:\Users\UAH\Desktop\A2rchi\a2rchi\templates"
template_file = "base-compose.yaml"

# Variables para la plantilla
context = {
    # Servicios principales
    "chat_image": "mi_chat_image",
    "chat_tag": "latest",
    "chat_container_name": "chat-prueba",
    "chromadb_image": "chromadb/chroma",
    "chromadb_tag": "latest",
    "chromadb_container_name": "chromadb-prueba",
    "chromadb_port_host": 8000,
    "chat_volume_name": "chat_data",
    "chat_port_host": 5000,
    "chat_port_container": 5000,
    "postgres_container_name": "postgres-prueba",
    "postgres_volume_name": "postgres_data",

    # Opciones de GPU y servicios adicionales
    "use_gpu": False,  # Cambia a True si necesitas GPU
    "include_grafana": False,  # Cambia a True si necesitas Grafana
    "grafana_image": "grafana/grafana",
    "grafana_tag": "latest",
    "grafana_container_name": "grafana-prueba",
    "grafana_port_host": 3000,
    "grafana_volume_name": "grafana_data",

    "include_uploader_service": False,  # Cambia a True si necesitas uploader
    "uploader_image": "mi_uploader_image",
    "uploader_tag": "latest",
    "uploader_port_host": 6000,
    "uploader_port_container": 6000,

    "include_piazza_service": False,  # Cambia a True si necesitas piazza
    "piazza_image": "mi_piazza_image",
    "piazza_tag": "latest",

    "include_cleo_and_mailer": False,  # Cambia a True si necesitas cleo y mailbox
    "cleo_image": "mi_cleo_image",
    "cleo_tag": "latest",
    "mailbox_image": "mi_mailbox_image",
    "mailbox_tag": "latest",
}

# Carga y renderiza la plantilla
env = Environment(loader=FileSystemLoader(template_dir))
template = env.get_template(template_file)
output = template.render(**context)

# Guarda el archivo renderizado como docker-compose.yaml
output_file = r"C:\Users\UAH\Desktop\A2rchi\docker-compose.yaml"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(output)

print(f"Archivo renderizado guardado en: {output_file}")
