import re
from jinja2 import Environment, PackageLoader, select_autoescape, ChainableUndefined
from typing import Tuple

import click
import os
import requests
import secrets
import shutil
import subprocess
import yaml
import time
import shlex
import threading

# DEFINITIONS
env = Environment(
    loader=PackageLoader("a2rchi"),
    autoescape=select_autoescape(),
    undefined=ChainableUndefined,
)
A2RCHI_DIR = os.environ.get('A2RCHI_DIR',os.path.join(os.path.expanduser('~'), ".a2rchi"))
BASE_CONFIG_TEMPLATE = "base-config.yaml"
BASE_DOCKERFILE_LOCATION = "dockerfiles"
BASE_GRAFANA_DATASOURCES_TEMPLATE = "grafana/datasources.yaml"
BASE_GRAFANA_DASHBOARDS_TEMPLATE = "grafana/dashboards.yaml"
BASE_GRAFANA_A2RCHI_DEFAULT_DASHBOARDS_TEMPLATE = "grafana/a2rchi-default-dashboard.json"
BASE_GRAFANA_CONFIG_TEMPLATE = "grafana/grafana.ini"
BASE_COMPOSE_TEMPLATE = "base-compose.yaml"
BASE_INIT_SQL_TEMPLATE = "base-init.sql"

class InvalidCommandException(Exception):
    pass

class BashCommandException(Exception):
    pass

def _prepare_secret(a2rchi_name_dir, secret_name, locations_of_secrets):
    """
    Prepares a secret by locating its file in the specified directories, 
    reading its content, and saving it to a target directory.

    The function searches for a secret file named `"{secret_name.lower()}.txt"`
    in the directories provided in `locations_of_secrets`. If multiple files 
    with the same name are found, an error is raised to prevent ambiguity. 
    If no file is found, a `FileNotFoundError` is raised. The secret's content 
    is read from the file and written to the `secrets` subdirectory within 
    `a2rchi_name_dir`.

    Args:
        a2rchi_name_dir (str): The base directory where the `secrets` 
            directory will be created or used.
        secret_name (str): The name of the secret to locate. The function 
            expects a file named `"{secret_name.lower()}.txt"` in the given 
            directories.
        locations_of_secrets (list[str]): A list of directories to search 
            for the secret file.

    Raises:
        ValueError: If multiple files with the secret name are found in the 
            specified directories.
        FileNotFoundError: If no file with the secret name is found in the 
            specified directories.
    
    Example:
        >>> a2rchi_name_dir = "/path/to/a2rchi"
        >>> secret_name = "API_KEY"
        >>> locations_of_secrets = ["/path/to/dir1", "/path/to/dir2"]
        >>> _prepare_secret(a2rchi_name_dir, secret_name, locations_of_secrets)
        Secret for 'API_KEY' prepared at /path/to/a2rchi/secrets/api_key.txt.
    """
    # Ensure the secrets directory exists
    secrets_dir = os.path.join(a2rchi_name_dir, "secrets")
    os.makedirs(secrets_dir, exist_ok=True)

    # Look for the secret file in the specified locations
    secret_filename = f"{secret_name.lower()}.txt"
    found_secrets = []

    for location in locations_of_secrets:
        potential_path = os.path.expanduser(os.path.join(location, secret_filename))
        if os.path.isfile(potential_path):
            found_secrets.append(potential_path)

    # Check for multiple occurrences of the secret
    if len(found_secrets) > 1:
        raise ValueError(
            f"Error: Multiple secret files found for '{secret_name}' in locations: {found_secrets}"
        )
    elif len(found_secrets) == 0:
        raise FileNotFoundError(
            f"Error: No secret file found for '{secret_name}' in the specified locations."
        )

    # Read the secret from the found file
    secret_file_path = found_secrets[0]
    with open(secret_file_path, 'r') as secret_file:
        secret_value = secret_file.read().strip()

    # Write the secret to the target directory
    target_secret_path = os.path.join(secrets_dir, secret_filename)
    with open(target_secret_path, 'w') as target_file:
        target_file.write(secret_value)

def _validate_config(config, required_fields):
    """
    a function to validate presence of required fields in nested dictionaries
    """
    for field in required_fields:
        keys = field.split('.')
        value = config
        for key in keys:
            if key not in value:
                raise ValueError(f"Missing required field: '{field}' in the configuration")
            value = value[key]  # Drill down into nested dictionaries


def _run_bash_command(command_str: str, verbose=False) -> Tuple[str, str]:
    """Run a shell command and stream output in real-time, capturing stdout and stderr."""
    command_str_lst = shlex.split(command_str)
    process = subprocess.Popen(
        command_str_lst,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1  # line-buffered
    )

    stdout_lines = []
    stderr_lines = []

    def _read_stream(stream, collector, stream_name):
        for line in iter(stream.readline, ''):
            collector.append(line)
            if verbose:
                _print_msg(f"{line}")  # keep formatting tight
        stream.close()

    # start threads for non-blocking reads
    stdout_thread = threading.Thread(target=_read_stream, args=(process.stdout, stdout_lines, "stdout"))
    stderr_thread = threading.Thread(target=_read_stream, args=(process.stderr, stderr_lines, "stderr"))
    stdout_thread.start()
    stderr_thread.start()

    # wait for command to finish
    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        stdout_thread.join()
        stderr_thread.join()
        raise

    return ''.join(stdout_lines), ''.join(stderr_lines)

def _create_volume(volume_name, podman=False):
    # root podman or docker
    if podman:
        ls_volumes = "podman volume ls"
        create_volume = f"podman volume create {volume_name}"
    else:
        ls_volumes = "docker volume ls"
        create_volume = f"docker volume create --name {volume_name}"

    # first, check to see if volume already exists
    stdout, stderr = _run_bash_command(ls_volumes)
    if stderr:
        raise BashCommandException(stderr)

    for line in stdout.split("\n"):
        # return early if the volume exists
        if volume_name in line:
            _print_msg(f"Volume '{volume_name}' already exists. No action needed.")
            return

    # otherwise, create the volume
    _print_msg(f"Creating volume: {volume_name}")
    _, stderr = _run_bash_command(create_volume)
    if stderr:
        raise BashCommandException(stderr)


def _read_prompts(a2rchi_config):
    # initialize variables
    main_prompt, condense_prompt, summary_prompt = None, None, None

    # read prompts and return them
    with open(a2rchi_config['main_prompt'], 'r') as f:
        main_prompt = f.read()

    with open(a2rchi_config['condense_prompt'], 'r') as f:
        condense_prompt = f.read()

    with open(a2rchi_config['summary_prompt'], 'r') as f:
        summary_prompt = f.read()

    return main_prompt, condense_prompt, summary_prompt


def _print_msg(msg):
    print(f"[a2rchi]>> {msg}")


@click.group()
def cli():
    pass


@click.command()
@click.option('--name', type=str, default=None, help="Name of the a2rchi deployment.")
@click.option('--grafana', '-g', 'include_grafana', type=bool, default=False, help="Boolean to add Grafana dashboard in deployment.")
@click.option('--document-uploader', '-du', 'include_uploader_service', type=bool, default=False, help="Boolean to add service for admins to upload data")
@click.option('--cleo-and-mailer', '-cm', 'include_cleo_and_mailer', type=bool, default=False, help="Boolean to add service for a2rchi interface with cleo and a mailer")
@click.option('--a2rchi-config', '-f', 'a2rchi_config_filepath', type=str, default=None, help="Path to compose file.")
@click.option('--podman', '-p', 'use_podman', type=bool, default=False, help="Boolean to use podman instead of docker.")
@click.option('--gpu', 'use_gpu', type=bool, default=False, help="Boolean to use GPU for a2rchi. Current support for podman to do this.")
@click.option('--tag', '-t', 'image_tag', type=str, default=2000, help="Tag for the collection of images you will create to build chat, chroma, and any other specified services")

def create(
    name, 
    include_grafana, 
    include_uploader_service, 
    include_cleo_and_mailer,
    a2rchi_config_filepath,
    use_podman,
    use_gpu,
    image_tag
):
    """
    Create an instance of a RAG system with the specified name. By default,
    this command will create the following services:

    1. A chat interface (for users to communicate with the agent)
    2. A ChromaDB vector store (for storing relevant document chunks)
    3. A Postgres database (for storing the conversation history)

    Users may also include additional services, such as a Grafana dashboard
    (for monitoring LLM and system performance).
    """
    # parse and clean command arguments
    if name is not None:
        name = name.strip()
    else:
        raise InvalidCommandException(
            f"Please provide a name for the deployment using the --name flag."
        )

    if a2rchi_config_filepath is not None:
        a2rchi_config_filepath = a2rchi_config_filepath.strip()

    # create temporary directory for template files
    a2rchi_name_dir = os.path.join(A2RCHI_DIR, f"a2rchi-{name}")
    os.makedirs(a2rchi_name_dir, exist_ok=True)

    # initialize dictionary of template variables for docker compose file
    tag = image_tag
    compose_template_vars = {
        "chat_image": f"chat-{name}",
        "chat_tag": tag,
        "chat_container_name": f"chat-{name}",
        "chromadb_image": f"chromadb-{name}",
        "chromadb_tag": tag,
        "chromadb_container_name": f"chromadb-{name}",
        "postgres_container_name": f"postgres-{name}",
    }

    # tell compose whether to look for gpus or not
    compose_template_vars["use_gpu"] = use_gpu

    # piazza compose vars
    compose_template_vars["piazza_tag"] = tag

    # create docker volumes; these commands will no-op if they already exist
    _print_msg("Creating volumes")
    _create_volume(f"a2rchi-{name}", podman=use_podman)
    _create_volume(f"a2rchi-pg-{name}", podman=use_podman)
    compose_template_vars["chat_volume_name"] = f"a2rchi-{name}"
    compose_template_vars["postgres_volume_name"] = f"a2rchi-pg-{name}"

    # Define required fields in user configuration of A2rchi
    required_fields = [
        'name', 
        'global.TRAINED_ON',
        'chains.input_lists', 
        'chains.prompts.CONDENSING_PROMPT', 'chains.prompts.MAIN_PROMPT', 'chains.prompts.SUMMARY_PROMPT',
        'chains.chain.MODEL_NAME', 'chains.chain.CONDENSE_MODEL_NAME', 'chains.chain.SUMMARY_MODEL_NAME'
    ]
    # load user configuration of A2rchi
    with open(a2rchi_config_filepath, 'r') as f:
        a2rchi_config = yaml.load(f, Loader=yaml.FullLoader)
        _validate_config(a2rchi_config, required_fields=required_fields)
        a2rchi_config["postgres_hostname"] = compose_template_vars["postgres_container_name"]
        if "collection_name" not in a2rchi_config:
            a2rchi_config["collection_name"] = f"collection_{name}"

    locations_of_secrets = a2rchi_config["locations_of_secrets"]

    # fetch or generate grafana password
    grafana_pg_password = os.environ.get("GRAFANA_PG_PASSWORD", secrets.token_hex(8))

    # if deployment includes grafana, create docker volume and template deployment files
    compose_template_vars["include_grafana"] = include_grafana
    if include_grafana:
        _create_volume(f"a2rchi-grafana-{name}", podman=use_podman)

        _print_msg("Preparing Grafana")
        # add grafana to compose and SQL init
        compose_template_vars["include_grafana"] = include_grafana
        compose_template_vars["grafana_volume_name"] = f"a2rchi-grafana-{name}"
        compose_template_vars["grafana_image"] = f"grafana-{name}"
        compose_template_vars["grafana_tag"] = tag
        compose_template_vars["grafana_container_name"] = f"grafana-{name}"

        # template grafana datasources file to include postgres pw for grafana
        grafana_datasources_template = env.get_template(BASE_GRAFANA_DATASOURCES_TEMPLATE)
        grafana_datasources = grafana_datasources_template.render({"grafana_pg_password": grafana_pg_password})

        # write complete datasources file to folder
        os.makedirs(os.path.join(a2rchi_name_dir, "grafana"), exist_ok=True)
        with open(os.path.join(a2rchi_name_dir, "grafana", "datasources.yaml"), 'w') as f:
            #yaml.dump(grafana_datasources, f)
            f.write(grafana_datasources)

        # copy dashboards.yaml, a2rchi-default-dashboards.json, grafana.ini to grafana dir
        grafana_dashboards_template = env.get_template(BASE_GRAFANA_DASHBOARDS_TEMPLATE)
        grafana_dashboards = grafana_dashboards_template.render()
        with open(os.path.join(a2rchi_name_dir, "grafana", "dashboards.yaml"), 'w') as f:
            # yaml.dump(grafana_dashboards, f)
            f.write(grafana_dashboards)

        a2rchi_dashboards_template = env.get_template(BASE_GRAFANA_A2RCHI_DEFAULT_DASHBOARDS_TEMPLATE)
        a2rchi_dashboards = a2rchi_dashboards_template.render()
        with open(os.path.join(a2rchi_name_dir, "grafana", "a2rchi-default-dashboard.json"), 'w') as f:
            # json.dump(a2rchi_dashboards, f)
            f.write(a2rchi_dashboards)

        grafana_config_template = env.get_template(BASE_GRAFANA_CONFIG_TEMPLATE)
        grafana_config = grafana_config_template.render()
        with open(os.path.join(a2rchi_name_dir, "grafana", "grafana.ini"), 'w') as f:
            f.write(grafana_config)

        # Extract ports from configuration and add to compose_template_vars #TODO: remove default values from cli_main.py
        # Grafana service ports
        grafana_port_host = a2rchi_config.get('interfaces', {}).get('grafana', {}).get('EXTERNAL_PORT', 3000)
        compose_template_vars['grafana_port_host'] = grafana_port_host

    compose_template_vars["include_uploader_service"] = include_uploader_service
    if include_uploader_service:
         _print_msg("Preparing Uploader Service")

         # Add uploader service to compose
         compose_template_vars["include_uploader_service"] = include_uploader_service
         compose_template_vars["uploader_image"] = f"uploader-{name}"
         compose_template_vars["uploader_tag"] = tag

         # Extract ports from configuration and add to compose_template_vars #TODO: remove default values from cli_main.py
         # Uploader service ports
         uploader_port_host = a2rchi_config.get('interfaces', {}).get('uploader_app', {}).get('EXTERNAL_PORT', 5003)
         uploader_port_container = a2rchi_config.get('interfaces', {}).get('uploader_app', {}).get('PORT', 5001)
         compose_template_vars['uploader_port_host'] = uploader_port_host
         compose_template_vars['uploader_port_container'] = uploader_port_container

         _prepare_secret(a2rchi_name_dir, "flask_uploader_app_secret_key", locations_of_secrets)
         _prepare_secret(a2rchi_name_dir, "uploader_salt", locations_of_secrets)

    compose_template_vars["include_cleo_and_mailer"] = include_cleo_and_mailer
    if include_cleo_and_mailer:
        _print_msg("Preparing Cleo and Emailer Service")

        # Add uploader service to compose
        compose_template_vars["include_cleo_and_mailer"] = include_cleo_and_mailer
        compose_template_vars["cleo_image"] = f"cleo-{name}"
        compose_template_vars["cleo_tag"] = tag
        compose_template_vars["mailbox_image"] = f"mailbox-{name}"
        compose_template_vars["mailbox_tag"] = tag

        _prepare_secret(a2rchi_name_dir, "imap_user", locations_of_secrets)
        _prepare_secret(a2rchi_name_dir, "imap_pw", locations_of_secrets)
        _prepare_secret(a2rchi_name_dir, "cleo_url", locations_of_secrets)
        _prepare_secret(a2rchi_name_dir, "cleo_user", locations_of_secrets)
        _prepare_secret(a2rchi_name_dir, "cleo_pw", locations_of_secrets)
        _prepare_secret(a2rchi_name_dir, "cleo_project", locations_of_secrets)
        _prepare_secret(a2rchi_name_dir, "sender_server", locations_of_secrets)
        _prepare_secret(a2rchi_name_dir, "sender_port", locations_of_secrets)
        _prepare_secret(a2rchi_name_dir, "sender_replyto", locations_of_secrets)
        _prepare_secret(a2rchi_name_dir, "sender_user", locations_of_secrets)
        _prepare_secret(a2rchi_name_dir, "sender_pw", locations_of_secrets)


    _print_msg("Preparing Postgres")
    # prepare init.sql for postgres initialization
    init_sql_template = env.get_template(BASE_INIT_SQL_TEMPLATE)
    init_sql = init_sql_template.render({
        "include_grafana": include_grafana,
        "grafana_pg_password": grafana_pg_password if include_grafana else "",
    })
    with open(os.path.join(a2rchi_name_dir, "init.sql"), 'w') as f:
        f.write(init_sql)
    
    # Prepare secrets
    _prepare_secret(a2rchi_name_dir, "openai_api_key", locations_of_secrets)
    _prepare_secret(a2rchi_name_dir, "anthropic_api_key", locations_of_secrets)
    _prepare_secret(a2rchi_name_dir, "hf_token", locations_of_secrets)
    _prepare_secret(a2rchi_name_dir, "pg_password", locations_of_secrets)


    # copy prompts
    shutil.copyfile(a2rchi_config["chains"]["prompts"]["MAIN_PROMPT"], os.path.join(a2rchi_name_dir, "main.prompt"))
    shutil.copyfile(a2rchi_config["chains"]["prompts"]["CONDENSING_PROMPT"], os.path.join(a2rchi_name_dir, "condense.prompt"))
    shutil.copyfile(a2rchi_config["chains"]["prompts"]["SUMMARY_PROMPT"], os.path.join(a2rchi_name_dir, "summary.prompt"))

    # copy input lists
    weblists_path = os.path.join(a2rchi_name_dir, "weblists")
    os.makedirs(weblists_path, exist_ok=True)
    for web_input_list in a2rchi_config["chains"]["input_lists"]:
        shutil.copyfile(web_input_list, os.path.join(weblists_path, os.path.basename(web_input_list)))

    # load and render config template
    config_template = env.get_template(BASE_CONFIG_TEMPLATE)
    config = config_template.render(**a2rchi_config)

    # write final templated configuration
    with open(os.path.join(a2rchi_name_dir, "config.yaml"), 'w') as f:
        f.write(config)

    # Extract ports from configuration and add to compose_template_vars #TODO: remove default values from cli_main.py
    # Chat service ports
    chat_port_host = a2rchi_config.get('interfaces', {}).get('chat_app', {}).get('EXTERNAL_PORT', 7861)
    chat_port_container = a2rchi_config.get('interfaces', {}).get('chat_app', {}).get('PORT', 7861)
    compose_template_vars['chat_port_host'] = chat_port_host
    compose_template_vars['chat_port_container'] = chat_port_container
    # ChromaDB service ports
    chromadb_port_host = a2rchi_config.get('utils', {}).get('data_manager', {}).get('chromadb_external_port', 8000)
    compose_template_vars['chromadb_port_host'] = chromadb_port_host
    # Postgres service ports are never externally exposed, so they don't need to be managed!

    # load compose template
    _print_msg("Preparing Compose")
    compose_template = env.get_template(BASE_COMPOSE_TEMPLATE)
    compose = compose_template.render({**compose_template_vars})
    with open(os.path.join(a2rchi_name_dir, "compose.yaml"), 'w') as f:
        # yaml.dump(compose, f)
        f.write(compose)

    # copy over the code into the a2rchi dir
    shutil.copytree("a2rchi", os.path.join(a2rchi_name_dir, "a2rchi_code"))
    shutil.copyfile("pyproject.toml", os.path.join(a2rchi_name_dir, "pyproject.toml"))
    shutil.copyfile("requirements.txt", os.path.join(a2rchi_name_dir, "requirements.txt"))
    shutil.copyfile("LICENSE", os.path.join(a2rchi_name_dir, "LICENSE"))

    # create a2rchi system using docker
    if use_podman:
        compose_up = f"podman compose -f {os.path.join(a2rchi_name_dir, 'compose.yaml')} up -d --build --force-recreate --always-recreate-deps"
    else:
        compose_up = f"docker compose -f {os.path.join(a2rchi_name_dir, 'compose.yaml')} up -d --build --force-recreate --always-recreate-deps"
    _print_msg("Starting compose")
    stdout, stderr = _run_bash_command(compose_up, verbose=True)


@click.command()
@click.option('--name', type=str, default=None, help="Name of the a2rchi deployment.")
@click.option('--podman', '-p', 'use_podman', type=bool, default=False, help="Boolean to use podman instead of docker.")
def delete(name, use_podman):
    """
    Delete instance of RAG system with the specified name.
    """
    # parse and clean command arguments
    if name is not None:
        name = name.strip()
    else:
        raise InvalidCommandException(
            f"Please provide a name for the deployment using the --name flag."
        )

    # stop compose
    a2rchi_name_dir = os.path.join(A2RCHI_DIR, f"a2rchi-{name}")
    if use_podman:
        compose_down = f"podman compose -f {os.path.join(a2rchi_name_dir, 'compose.yaml')} down"
    else:
        compose_down = f"docker compose -f {os.path.join(a2rchi_name_dir, 'compose.yaml')} down"
    _print_msg("Stopping compose")
    _run_bash_command(compose_down)

    # remove files in a2rchi directory
    _print_msg("Removing files in a2rchi directory")
    _run_bash_command(f"rm -r {a2rchi_name_dir}")


@click.command()
@click.option('--name', type=str, default=None, help="Name of the a2rchi deployment.")
@click.option('--a2rchi-config', '-f', 'a2rchi_config_filepath', type=str, default=None, help="Path to compose file.")
def update(name, a2rchi_config_filepath): #TODO: not sure if this works anymore, or if we actually need it
    """
    Update instance of RAG system with the specified name using a new configuration.
    """
    # parse and clean command arguments
    if name is not None:
        name = name.strip()
    else:
        raise InvalidCommandException(
            f"Please provide a name for the deployment using the --name flag."
        )

    if a2rchi_config_filepath is not None:
        a2rchi_config_filepath = a2rchi_config_filepath.strip()

    # load user configuration of A2rchi
    with open(a2rchi_config_filepath, 'r') as f:
        a2rchi_config = yaml.load(f, Loader=yaml.FullLoader)
        a2rchi_config["postgres_hostname"] = f"postgres-{name}"
        if "collection_name" not in a2rchi_config:
            a2rchi_config["collection_name"] = f"collection_{name}"

    # load and render config template
    config_template = env.get_template(BASE_CONFIG_TEMPLATE)
    config = config_template.render(**a2rchi_config)

    # write final templated configuration to keep consistent w/state of container
    a2rchi_name_dir = os.path.join(A2RCHI_DIR, f"a2rchi-{name}")
    a2rchi_config_rendered_fp = os.path.join(a2rchi_name_dir, "config.yaml")
    with open(a2rchi_config_rendered_fp, 'w') as f:
        f.write(config)

    # copy prompts to keep consistent w/state of container
    shutil.copyfile(a2rchi_config["main_prompt"], os.path.join(a2rchi_name_dir, "main.prompt"))
    shutil.copyfile(a2rchi_config["condense_prompt"], os.path.join(a2rchi_name_dir, "condense.prompt"))
    shutil.copyfile(a2rchi_config["summary_prompt"], os.path.join(a2rchi_name_dir, "summary.prompt"))

    _print_msg("Updating config")

    # read prompts
    main_prompt, condense_prompt, summary_prompt = _read_prompts(a2rchi_config)

    # get config containing hostname and port for chat service
    config_dict = yaml.load(config, Loader=yaml.FullLoader)
    chat_config = config_dict['interfaces']['chat_app']

    resp = requests.post(
        f"http://{chat_config['HOSTNAME']}:{chat_config['EXTERNAL_PORT']}/api/update_config",
        json={
            "config": config,
            "main_prompt": main_prompt,
            "condense_prompt": condense_prompt,
            "summary_prompt": summary_prompt,
        }
    )
    _print_msg(resp.json()['response'])


def main():
    """
    Entrypoint for a2rchi cli tool implemented using Click.
    """
    # cli.add_command(help)
    cli.add_command(create)
    cli.add_command(delete)
    cli.add_command(update)
    cli()
